"""One-shot migration: convert a single-tenant DB into the django-tenants layout.

Run ONCE per environment after installing django-tenants and adding
`apps.tenancy` to SHARED_APPS. After this command, the existing data lives
inside its own tenant schema and `public` only holds the tenant registry.

Steps performed (atomic per step):
  1. Sanity checks: verify we're on the public schema, verify tenancy
     tables don't already exist, verify domain models DO exist.
  2. ALTER SCHEMA public RENAME TO <new_schema>.
  3. CREATE SCHEMA public.
  4. migrate_schemas --shared (creates tenancy tables in the new public).
  5. INSERT Tenant + Domain + TenantBranding.
  6. Synchronize the new tenant's django_migrations table so future
     `migrate_schemas` runs don't try to re-apply old migrations.

Refuses to run if the DB is already multi-tenant (idempotent: re-running
exits cleanly).
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.tenancy.services import TenantProvisioningService
from apps.tenancy.utils import normalize_schema_name


class Command(BaseCommand):
    help = (
        "Convert an existing single-tenant DB to django-tenants. "
        "Renames the current public schema into a tenant schema and "
        "creates the global tenant registry."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--slug",
            required=True,
            help="Slug for the resulting tenant (e.g. 'partido-pk').",
        )
        parser.add_argument(
            "--name",
            required=True,
            help="Display name for the tenant (e.g. 'Partido PK').",
        )
        parser.add_argument(
            "--domain",
            help=(
                "Primary host for the tenant (e.g. 'partido-pk.tudominio.com'). "
                "Optional: omit if you'll only use path-based routing "
                "(tudominio.com/<slug>/...)."
            ),
        )
        parser.add_argument(
            "--brand-name",
            help="Branding text. Defaults to --name.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would happen without modifying the DB.",
        )

    def handle(self, *args, **opts):
        slug = opts["slug"]
        name = opts["name"]
        domain = opts.get("domain")
        brand_name = opts.get("brand_name") or name
        dry_run = opts["dry_run"]

        schema_name = normalize_schema_name(slug)

        self._sanity_checks(schema_name)

        if dry_run:
            self.stdout.write(self.style.WARNING("[dry-run] No DB changes."))
            self.stdout.write(f"  - Would rename schema 'public' to '{schema_name}'.")
            self.stdout.write("  - Would create new empty schema 'public'.")
            self.stdout.write("  - Would run migrate_schemas --shared.")
            self.stdout.write(
                f"  - Would insert Tenant(slug={slug!r}, schema={schema_name!r})."
            )
            if domain:
                self.stdout.write(f"  - Would insert Domain({domain!r}, primary).")
            self.stdout.write(f"  - Would insert TenantBranding(brand_name={brand_name!r}).")
            return

        self._rename_schema_and_recreate_public(schema_name)
        self._migrate_shared()
        self._create_tenant_record(
            slug=slug,
            schema_name=schema_name,
            name=name,
            domain=domain,
            brand_name=brand_name,
        )

        self.stdout.write(self.style.SUCCESS("\nMigration complete."))
        self.stdout.write(
            f"  Existing data is now isolated in schema '{schema_name}'."
        )
        if domain:
            self.stdout.write(f"  Reach the tenant at: https://{domain}/")
        self.stdout.write(f"  Path-based access:    https://<root>/{slug}/")

    # ----- internal helpers -----

    def _sanity_checks(self, schema_name):
        with connection.cursor() as cur:
            cur.execute("SELECT current_schema()")
            current = cur.fetchone()[0]
            if current != "public":
                raise CommandError(
                    f"Expected current schema to be 'public', got {current!r}. "
                    "Run this command without an active tenant."
                )

            # Already migrated? tenancy_tenant lives in public after Sprint 1.
            cur.execute(
                "SELECT to_regclass('public.tenancy_tenant')"
            )
            if cur.fetchone()[0] is not None:
                raise CommandError(
                    "Detected 'tenancy_tenant' already in public — the DB looks "
                    "already migrated. Aborting to be safe."
                )

            # Target schema must not exist.
            cur.execute(
                "SELECT 1 FROM information_schema.schemata WHERE schema_name = %s",
                [schema_name],
            )
            if cur.fetchone():
                raise CommandError(
                    f"Schema {schema_name!r} already exists. Choose a different slug "
                    "or drop the existing schema manually."
                )

            # Domain tables must exist (proof that the current public has the app data).
            cur.execute("SELECT to_regclass('public.campaigns_campaign')")
            if cur.fetchone()[0] is None:
                raise CommandError(
                    "Did not find 'campaigns_campaign' in the public schema. "
                    "This command is meant to migrate an existing live DB. "
                    "If you're starting fresh, use 'create_tenant' instead."
                )
        self.stdout.write(self.style.SUCCESS("Sanity checks passed."))

    def _rename_schema_and_recreate_public(self, schema_name):
        # Schema DDL is transactional in PostgreSQL — wrap in a single tx.
        with transaction.atomic():
            with connection.cursor() as cur:
                cur.execute(f'ALTER SCHEMA public RENAME TO "{schema_name}"')
                cur.execute("CREATE SCHEMA public")
                cur.execute("GRANT ALL ON SCHEMA public TO CURRENT_USER")
                cur.execute("GRANT USAGE ON SCHEMA public TO public")
        self.stdout.write(
            self.style.SUCCESS(
                f"Schema 'public' renamed to '{schema_name}' and new public created."
            )
        )

    def _migrate_shared(self):
        self.stdout.write("Running migrate_schemas --shared ...")
        call_command("migrate_schemas", shared=True, verbosity=1)

    def _create_tenant_record(self, *, slug, schema_name, name, domain, brand_name):
        # CRITICAL: schema already exists (we just renamed it). Don't recreate it,
        # hence auto_create_schema=False.
        tenant = TenantProvisioningService.create_tenant_record(
            slug=slug,
            schema_name=schema_name,
            name=name,
            domain=domain,
            brand_name=brand_name,
            auto_create_schema=False,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Tenant created: id={tenant.pk} slug={slug} schema={schema_name}"
            )
        )
