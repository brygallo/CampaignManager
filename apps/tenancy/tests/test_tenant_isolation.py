"""Tenant-isolation tests.

These tests verify that data written under one tenant schema is NOT
visible from another. They depend on the real django-tenants engine
(SQL ``SET search_path``), so they must be run under
``--ds=core.settings.test`` rather than the default
``core.settings.test_e2e`` used by the rest of the suite.

The ``tenant`` fixture defined in the project's root ``conftest.py``
creates a throwaway ``Tenant`` + ``Domain`` row and yields it inside a
``schema_context``.

Run with::

    pipenv run pytest apps/tenancy/tests/test_tenant_isolation.py \\
        --ds=core.settings.test -m tenant
"""
from __future__ import annotations

import pytest
from django.db import connection
from django_tenants.utils import get_public_schema_name, schema_context

from apps.tenancy.models import Domain, Tenant

pytestmark = [pytest.mark.tenant, pytest.mark.django_db(transaction=True)]


def _make_tenant(*, schema_name: str, slug: str, name: str) -> Tenant:
    """Create a real PostgreSQL schema-backed tenant.

    ``Tenant.auto_create_schema`` is True, so ``Tenant.objects.create``
    runs ``CREATE SCHEMA`` and applies ``TENANT_APPS`` migrations.
    """
    tenant = Tenant.objects.create(schema_name=schema_name, slug=slug, name=name)
    Domain.objects.create(domain=f"{slug}.localhost", tenant=tenant, is_primary=True)
    return tenant


@pytest.fixture
def two_tenants(db):
    """Spin up two distinct tenants and clean them up at the end."""
    public = get_public_schema_name()
    t1 = _make_tenant(schema_name="iso_one", slug="iso-one", name="Iso One")
    t2 = _make_tenant(schema_name="iso_two", slug="iso-two", name="Iso Two")

    yield t1, t2

    if getattr(connection, "schema_name", None) != public:
        connection.set_schema_to_public()
    Tenant.objects.filter(pk__in=[t1.pk, t2.pk]).delete()


def test_two_tenants_get_independent_user_tables(two_tenants):
    """Each tenant's ``User`` table starts empty even when the other has rows."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    t1, t2 = two_tenants

    with schema_context(t1.schema_name):
        User.objects.create_user(username="alice", email="a@a.com", password="x")
        assert User.objects.count() == 1
        assert User.objects.filter(username="alice").exists()

    with schema_context(t2.schema_name):
        # The user above must NOT show up here.
        assert User.objects.count() == 0
        assert not User.objects.filter(username="alice").exists()


def test_two_tenants_get_independent_campaign_tables(two_tenants):
    """Campaigns created in tenant A are invisible from tenant B."""
    from apps.campaigns.tests.factories import CampaignFactory

    t1, t2 = two_tenants

    with schema_context(t1.schema_name):
        CampaignFactory(name="Campaign A")
        from apps.campaigns.models import Campaign

        assert Campaign.objects.filter(name="Campaign A").count() == 1

    with schema_context(t2.schema_name):
        from apps.campaigns.models import Campaign

        # The Campaign table in tenant 2 should be empty.
        assert Campaign.objects.filter(name="Campaign A").count() == 0
        assert Campaign.objects.count() == 0


def test_tenants_share_public_schema_models(two_tenants):
    """``Tenant`` itself lives in the public schema and is shared."""
    t1, t2 = two_tenants
    # Both tenants must be visible from either schema, because they're
    # SHARED_APP rows.
    with schema_context(t1.schema_name):
        assert Tenant.objects.filter(slug__in=["iso-one", "iso-two"]).count() == 2
    with schema_context(t2.schema_name):
        assert Tenant.objects.filter(slug__in=["iso-one", "iso-two"]).count() == 2


def test_session_data_is_scoped_per_tenant(two_tenants):
    """``Session`` rows live inside each tenant schema (TENANT_APP)."""
    from django.contrib.sessions.models import Session
    from django.utils import timezone
    from datetime import timedelta

    t1, t2 = two_tenants

    expire = timezone.now() + timedelta(days=1)
    with schema_context(t1.schema_name):
        Session.objects.create(
            session_key="abc123",
            session_data="x",
            expire_date=expire,
        )
        assert Session.objects.filter(session_key="abc123").exists()

    with schema_context(t2.schema_name):
        assert not Session.objects.filter(session_key="abc123").exists()
