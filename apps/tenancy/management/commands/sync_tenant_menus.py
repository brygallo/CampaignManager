"""Build the SuperAdmin menu inside tenant schemas."""
import yaml
from django.db import transaction
from django.core.management.base import BaseCommand, CommandError
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
        menu_data, icons = self._extract_icons(raw_menu)
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
                self.stdout.write(
                    self.style.SUCCESS(
                        f"{schema_name}: synced {Menu.objects.count()} menu rows"
                    )
                )

    def _extract_icons(self, node, parent_path=""):
        """Strip ``icon`` keys from the menu tree and collect them by route."""
        icons = {}
        if not isinstance(node, dict):
            return node, icons
        cleaned = {}
        for key, value in node.items():
            if key == "icon":
                continue
            path = f"{parent_path}/{slugify(key)}" if parent_path else slugify(key)
            if isinstance(value, dict):
                if isinstance(value.get("icon"), str):
                    icons[path] = value["icon"]
                sub_cleaned, sub_icons = self._extract_icons(value, path)
                cleaned[key] = sub_cleaned
                icons.update(sub_icons)
            else:
                cleaned[key] = value
        return cleaned, icons

    def _apply_icons(self, Menu, icons):
        if not icons:
            return
        for menu in Menu.objects.all():
            icon = icons.get(menu.route)
            if icon and menu.icon_class != icon:
                menu.icon_class = icon
                menu.save(update_fields=["icon_class"])

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
