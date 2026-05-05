"""Build the SuperAdmin menu inside tenant schemas."""
import yaml
from django.db import transaction
from django.core.management.base import BaseCommand, CommandError
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

        menu_data = self._load_menu(options["menu_file"])
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
                self.stdout.write(
                    self.style.SUCCESS(
                        f"{schema_name}: synced {Menu.objects.count()} menu rows"
                    )
                )

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
