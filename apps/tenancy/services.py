"""Business operations (side effects) for tenant provisioning.

Keeps the management commands thin: ``create_tenant`` and
``migrate_to_multitenant`` delegate the actual Tenant / Domain / Branding /
owner creation to these class methods. Mirrors sim's ``services.py`` pattern
(``OvertimeService``, ``ProcedureService``, ...): stateless classes with
``@classmethod`` operations that orchestrate the DB.
"""
from django.contrib.auth import get_user_model
from django_tenants.utils import schema_context


class TenantProvisioningService:
    @classmethod
    def create_tenant_record(
        cls,
        *,
        slug,
        schema_name,
        name,
        domain=None,
        brand_name=None,
        auto_create_schema=True,
    ):
        """Insert the Tenant row plus its primary Domain and Branding.

        With ``auto_create_schema=True`` (default), saving the Tenant triggers
        django-tenants to create the PostgreSQL schema and run all TENANT_APPS
        migrations inside it. Callers migrating an already-existing schema (the
        renamed ``public``) must pass ``auto_create_schema=False`` so the schema
        is not recreated. Returns the created Tenant.
        """
        # Imported here so Django finishes app loading before we touch the model.
        from apps.tenancy.models import Domain, Tenant, TenantBranding

        tenant = Tenant(
            schema_name=schema_name,
            slug=slug,
            name=name,
            is_active=True,
        )
        tenant.auto_create_schema = auto_create_schema
        tenant.save()

        if domain:
            Domain.objects.create(domain=domain, tenant=tenant, is_primary=True)

        TenantBranding.objects.create(
            tenant=tenant, brand_name=brand_name or name
        )
        return tenant

    @classmethod
    def create_owner_superuser(cls, *, schema_name, username, email, password):
        """Create a superuser inside the tenant's own schema."""
        with schema_context(schema_name):
            User = get_user_model()
            User.objects.create_superuser(
                username=username,
                email=email,
                password=password,
            )
