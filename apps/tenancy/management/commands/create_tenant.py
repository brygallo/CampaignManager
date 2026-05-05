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
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django_tenants.utils import schema_context


SAFE_NAME_CHARS = set("abcdefghijklmnopqrstuvwxyz0123456789_")


def _normalize_schema_name(slug: str) -> str:
    name = slug.lower().replace("-", "_")
    if not name or not all(c in SAFE_NAME_CHARS for c in name):
        raise CommandError(
            f"Invalid schema name derived from slug: {name!r}. "
            "Use only lowercase letters, digits, hyphens, and underscores."
        )
    if name[0].isdigit():
        raise CommandError(f"Schema name cannot start with a digit: {name!r}.")
    return name


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
        from apps.tenancy.models import Domain, Tenant, TenantBranding

        slug = opts["slug"]
        name = opts["name"]
        schema_name = _normalize_schema_name(slug)

        if Tenant.objects.filter(slug=slug).exists():
            raise CommandError(f"Tenant slug {slug!r} is already taken.")
        if Tenant.objects.filter(schema_name=schema_name).exists():
            raise CommandError(f"Schema name {schema_name!r} is already taken.")

        self.stdout.write(f"Creating tenant {slug!r} (schema={schema_name}) ...")
        tenant = Tenant(
            schema_name=schema_name,
            slug=slug,
            name=name,
            is_active=True,
        )
        tenant.save()  # auto_create_schema=True -> creates schema + migrates

        if opts.get("domain"):
            Domain.objects.create(domain=opts["domain"], tenant=tenant, is_primary=True)
            self.stdout.write(f"  Domain attached: {opts['domain']}")

        TenantBranding.objects.create(
            tenant=tenant, brand_name=opts.get("brand_name") or name
        )

        if opts.get("owner_username"):
            if not opts.get("owner_email") or not opts.get("owner_password"):
                raise CommandError(
                    "--owner-username requires --owner-email and --owner-password."
                )
            with schema_context(schema_name):
                User = get_user_model()
                User.objects.create_superuser(
                    username=opts["owner_username"],
                    email=opts["owner_email"],
                    password=opts["owner_password"],
                )
            self.stdout.write(f"  Owner created in {schema_name}: {opts['owner_username']}")

        self.stdout.write(self.style.SUCCESS(f"\nTenant '{slug}' is ready."))
        if opts.get("domain"):
            self.stdout.write(f"  Subdomain/host: https://{opts['domain']}/")
        self.stdout.write(f"  Path mode:      https://<root>/{slug}/")
