"""Project-wide pytest configuration.

The test settings (`core.settings.test`) flatten the django-tenants split:
all apps run inside the public schema so existing Django TestCase fixtures
keep working without spinning a fresh schema per test. Tests that exercise
true tenant isolation should be marked with ``@pytest.mark.tenant`` and use
the ``tenant`` fixture below to get a schema_context.
"""
from __future__ import annotations

import pytest
from django.db import connection


@pytest.fixture
def tenant(db):
    """Create a throwaway tenant + domain and yield its schema name.

    The fixture is opt-in (depends on ``db``) and only useful for the
    handful of tests that must verify cross-tenant isolation. Default
    tests can ignore it.
    """
    from django_tenants.utils import schema_context

    from apps.tenancy.models import Domain, Tenant

    tenant = Tenant.objects.create(
        schema_name="test_tenant",
        slug="test-tenant",
        name="Test Tenant",
    )
    Domain.objects.create(domain="test-tenant.localhost", tenant=tenant, is_primary=True)

    with schema_context(tenant.schema_name):
        yield tenant

    # Cleanup: schema is dropped automatically because the test DB is
    # destroyed at session end, but be explicit if running with --reuse-db.
    if getattr(connection, "schema_name", None) != "public":
        connection.set_schema_to_public()
    Tenant.objects.filter(pk=tenant.pk).delete()
