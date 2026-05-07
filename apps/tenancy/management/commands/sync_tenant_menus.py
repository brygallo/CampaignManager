"""Build the SuperAdmin menu inside tenant schemas.

Extends the upstream `superadmin.build_menu` to also support raw URL entries
in `menu.yaml`. Two extra keys are recognized on a leaf entry:

    Mapa:
      url_name: field_surveys:map      # reversed at sync time
      icon: map

    External:
      url: https://example.com/help    # used verbatim
      icon: file
"""
import yaml
from django.db import transaction
from django.core.management.base import BaseCommand, CommandError
from django.urls import NoReverseMatch, reverse
from django.utils.text import slugify
from django_tenants.utils import schema_context
from superadmin.management.commands.base import build_menu


class Command(BaseCommand):
    help = "Rebuild superadmin actions and menu from menu.yaml in tenant schemas."

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            action="append",
            dest="schemas",
            help=(
                "Tenant schema to sync. Can be passed multiple times. "
                "Defaults to all active tenants."
            ),
        )
        parser.add_argument(
            "--include-inactive",
            action="store_true",
            help="Include inactive tenants when --schema is not provided.",
        )
        parser.add_argument(
            "--include-public",
            action="store_true",
            help="Also rebuild the base menu in the public schema.",
        )
        parser.add_argument(
            "--menu-file",
            default="menu.yaml",
            help="Path to the menu YAML file. Defaults to menu.yaml.",
        )

    def handle(self, *args, **options):
        from apps.tenancy.models import Tenant
        from superadmin.models import Action, Menu

        raw_menu = self._load_menu(options["menu_file"])
        menu_data, icons, url_entries = self._extract_extras(raw_menu)
        schemas = self._get_schemas(Tenant, options)

        if options["include_public"]:
            schemas.insert(0, "public")

        if not schemas:
            self.stdout.write(self.style.WARNING("No tenant schemas to sync."))
            return

        for schema_name in schemas:
            with schema_context(schema_name):
                with transaction.atomic():
                    Menu.objects.all().delete()
                    Action.objects.all().delete()
                    build_menu(menu_data)
                    self._apply_icons(Menu, icons)
                    self._add_url_entries(Menu, Action, url_entries)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"{schema_name}: synced {Menu.objects.count()} menu rows"
                    )
                )

    def _extract_extras(self, node, parent_path=""):
        """Strip ``icon`` keys, collect URL entries, return cleaned tree.

        Returns ``(cleaned_data, icons_by_route, url_entries)`` where
        ``url_entries`` is a list of ``{name, parent_path, url, url_name,
        icon, sequence}`` dicts to be rebuilt as ``Menu`` rows after
        ``build_menu`` runs.
        """
        icons = {}
        url_entries = []
        if not isinstance(node, dict):
            return node, icons, url_entries

        cleaned = {}
        for key, value in node.items():
            if key == "icon":
                continue
            path = f"{parent_path}/{slugify(key)}" if parent_path else slugify(key)

            if isinstance(value, dict) and ("url" in value or "url_name" in value):
                # URL leaf — pulled out of the tree entirely; recreated later.
                url_entries.append(
                    {
                        "name": key,
                        "parent_path": parent_path,
                        "path": path,
                        "url": value.get("url"),
                        "url_name": value.get("url_name"),
                        "icon": value.get("icon"),
                    }
                )
                continue

            if isinstance(value, dict):
                if isinstance(value.get("icon"), str):
                    icons[path] = value["icon"]
                sub_cleaned, sub_icons, sub_urls = self._extract_extras(value, path)
                cleaned[key] = sub_cleaned
                icons.update(sub_icons)
                url_entries.extend(sub_urls)
            else:
                cleaned[key] = value
        return cleaned, icons, url_entries

    def _apply_icons(self, Menu, icons):
        if not icons:
            return
        for menu in Menu.objects.all():
            icon = icons.get(menu.route)
            if icon and menu.icon_class != icon:
                menu.icon_class = icon
                menu.save(update_fields=["icon_class"])

    def _add_url_entries(self, Menu, Action, url_entries):
        """Create ``Menu`` rows for entries that point at custom URLs.

        ``Menu.action`` is required and ``Menu.get_url`` returns
        ``f"/{self.route}"`` for non-MODEL actions, so we attach an
        existing CLASSVIEW action and store the resolved path in ``route``.
        """
        if not url_entries:
            return

        stub_action = (
            Action.objects.filter(to=Action.ToChoices.CLASSVIEW).first()
            or Action.objects.first()
        )
        if stub_action is None:
            self.stdout.write(self.style.WARNING(
                "  (no Action available for URL entries — skipped)"
            ))
            return

        for entry in url_entries:
            parent = None
            if entry["parent_path"]:
                parent = Menu.objects.filter(route=entry["parent_path"]).first()

            url = entry["url"]
            if not url and entry["url_name"]:
                try:
                    url = reverse(entry["url_name"])
                except NoReverseMatch:
                    self.stdout.write(self.style.WARNING(
                        f"  url_name {entry['url_name']!r} no resuelve — saltando '{entry['name']}'"
                    ))
                    continue

            # ``Menu.get_url`` for non-MODEL actions returns f"/{self.route}".
            # The Menu pre_save signal will normally re-derive route from the
            # name + parent slug, but post_save's ``update_route`` walk runs
            # afterwards and stomps it again. We pin the explicit URL by
            # setting it AFTER creation with a queryset update (skips signals).
            route_path = url.lstrip("/") if url and url.startswith("/") else (url or "")

            sequence = Menu.objects.filter(parent=parent).count() + 1

            menu = Menu.objects.create(
                parent=parent,
                name=entry["name"].capitalize(),
                action=stub_action,
                is_group=False,
                sequence=sequence,
                icon_class=entry.get("icon") or "",
            )
            # Bypass save() so the pre/post_save route signals don't override
            # the absolute URL we want.
            Menu.objects.filter(pk=menu.pk).update(route=route_path)

    def _load_menu(self, menu_file):
        try:
            with open(menu_file) as file_obj:
                return yaml.load(file_obj, Loader=yaml.FullLoader)
        except FileNotFoundError as exc:
            raise CommandError(f"Menu file not found: {menu_file}") from exc
        except yaml.parser.ParserError as exc:
            raise CommandError(
                f"Invalid YAML in {menu_file}: {exc.context} - {exc.problem}"
            ) from exc

    def _get_schemas(self, Tenant, options):
        requested = options.get("schemas") or []
        if requested:
            existing = set(Tenant.objects.values_list("schema_name", flat=True))
            missing = sorted(set(requested) - existing)
            if missing:
                raise CommandError(f"Unknown tenant schema(s): {', '.join(missing)}")
            return requested

        queryset = Tenant.objects.all()
        if not options["include_inactive"]:
            queryset = queryset.filter(is_active=True)
        return list(queryset.order_by("schema_name").values_list("schema_name", flat=True))
