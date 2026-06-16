"""Create a brand-new tenant (party) in an empty schema.

Use this for new partidos signing up after the platform is already running
multi-tenant. For migrating an existing single-tenant DB, use
`migrate_to_multitenant` instead.

Steps:
  1. Validate slug is unique.
  2. Create the Tenant row with auto_create_schema=True (django-tenants
     creates the PostgreSQL schema and runs all TENANT_APPS migrations
     inside it as a side effect of save()).
  3. Create primary Domain if --domain given.
  4. Create TenantBranding.
  5. Optionally create an owner superuser inside the new schema.
"""
from django.core.management.base import BaseCommand, CommandError

from apps.tenancy.services import TenantProvisioningService
from apps.tenancy.utils import normalize_schema_name


class Command(BaseCommand):
    help = "Create a new tenant (party) and provision its PostgreSQL schema."

    def add_arguments(self, parser):
        parser.add_argument("--slug", required=True, help="URL-friendly id (also schema basis).")
        parser.add_argument("--name", required=True, help="Display name.")
        parser.add_argument("--domain", help="Primary host (subdomain or custom domain). Optional.")
        parser.add_argument("--brand-name", help="Branding text. Defaults to --name.")
        parser.add_argument("--owner-username", help="If provided, create a superuser inside the new schema.")
        parser.add_argument("--owner-email", help="Email for the owner superuser.")
        parser.add_argument("--owner-password", help="Password for the owner superuser.")

    def handle(self, *args, **opts):
        from apps.tenancy.models import Tenant

        slug = opts["slug"]
        name = opts["name"]
        schema_name = normalize_schema_name(slug)

        if Tenant.objects.filter(slug=slug).exists():
            raise CommandError(f"Tenant slug {slug!r} is already taken.")
        if Tenant.objects.filter(schema_name=schema_name).exists():
            raise CommandError(f"Schema name {schema_name!r} is already taken.")

        self.stdout.write(f"Creating tenant {slug!r} (schema={schema_name}) ...")
        # auto_create_schema=True -> creates the schema + runs tenant migrations.
        TenantProvisioningService.create_tenant_record(
            slug=slug,
            schema_name=schema_name,
            name=name,
            domain=opts.get("domain"),
            brand_name=opts.get("brand_name"),
        )

        if opts.get("domain"):
            self.stdout.write(f"  Domain attached: {opts['domain']}")

        if opts.get("owner_username"):
            if not opts.get("owner_email") or not opts.get("owner_password"):
                raise CommandError(
                    "--owner-username requires --owner-email and --owner-password."
                )
            TenantProvisioningService.create_owner_superuser(
                schema_name=schema_name,
                username=opts["owner_username"],
                email=opts["owner_email"],
                password=opts["owner_password"],
            )
            self.stdout.write(f"  Owner created in {schema_name}: {opts['owner_username']}")

        self.stdout.write(self.style.SUCCESS(f"\nTenant '{slug}' is ready."))
        if opts.get("domain"):
            self.stdout.write(f"  Subdomain/host: https://{opts['domain']}/")
        self.stdout.write(f"  Path mode:      https://<root>/{slug}/")
