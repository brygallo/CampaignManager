"""Project-level migration command for public + tenant schemas."""
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Run django-tenants migrations for public and tenant schemas."

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            action="append",
            dest="schemas",
            help=(
                "Tenant schema to migrate. Can be passed multiple times. "
                "Defaults to all tenants."
            ),
        )
        parser.add_argument(
            "--skip-public",
            action="store_true",
            help="Do not migrate the public schema.",
        )
        parser.add_argument(
            "--skip-tenants",
            action="store_true",
            help="Do not migrate tenant schemas.",
        )
        parser.add_argument(
            "--sync-menus",
            action="store_true",
            help="Run sync_tenant_menus after successful tenant migrations.",
        )
        parser.add_argument(
            "--noinput",
            action="store_true",
            help="Do not prompt for input.",
        )
        parser.add_argument(
            "--fake",
            action="store_true",
            help="Mark migrations as run without running them.",
        )
        parser.add_argument(
            "--fake-initial",
            action="store_true",
            help="Fake initial migrations if tables already exist.",
        )
        parser.add_argument(
            "--plan",
            action="store_true",
            help="Show migration plan without applying migrations.",
        )
        parser.add_argument(
            "--check",
            action="store_true",
            dest="check_unapplied",
            help="Exit non-zero if unapplied migrations exist.",
        )

    def handle(self, *args, **options):
        from apps.tenancy.models import Tenant

        schemas = options.get("schemas") or []
        if schemas:
            existing = set(Tenant.objects.values_list("schema_name", flat=True))
            missing = sorted(set(schemas) - existing)
            if missing:
                raise CommandError(f"Unknown tenant schema(s): {', '.join(missing)}")

        migrate_options = {
            "interactive": not options["noinput"],
            "fake": options["fake"],
            "fake_initial": options["fake_initial"],
            "plan": options["plan"],
            "check_unapplied": options["check_unapplied"],
        }

        if not options["skip_public"]:
            self.stdout.write(self.style.NOTICE("Migrating public schema..."))
            call_command("migrate_schemas", shared=True, **migrate_options)

        if not options["skip_tenants"]:
            if schemas:
                for schema_name in schemas:
                    self.stdout.write(
                        self.style.NOTICE(f"Migrating tenant schema {schema_name}...")
                    )
                    call_command(
                        "migrate_schemas",
                        tenant=True,
                        schema_name=schema_name,
                        **migrate_options,
                    )
            else:
                self.stdout.write(self.style.NOTICE("Migrating all tenant schemas..."))
                call_command("migrate_schemas", tenant=True, **migrate_options)

        if options["sync_menus"] and not options["plan"] and not options["check_unapplied"]:
            sync_args = ["sync_tenant_menus"]
            for schema_name in schemas:
                sync_args.extend(["--schema", schema_name])
            self.stdout.write(self.style.NOTICE("Syncing tenant menus..."))
            call_command(*sync_args)
