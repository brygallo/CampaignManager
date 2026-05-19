"""Factory Boy factories for the tenancy app.

NOTE: ``TenantFactory`` creates a real PostgreSQL schema (``auto_create_schema=True``).
Use sparingly — it's slow. Prefer the project-wide ``tenant`` pytest fixture
when a single throwaway tenant is enough.
"""
from __future__ import annotations

import factory

from apps.tenancy.models import Domain, Tenant


class TenantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Tenant
        django_get_or_create = ("schema_name",)

    schema_name = factory.Sequence(lambda n: f"tenant_{n}")
    slug = factory.Sequence(lambda n: f"tenant-{n}")
    name = factory.Sequence(lambda n: f"Tenant {n}")
    is_active = True


class DomainFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Domain

    tenant = factory.SubFactory(TenantFactory)
    domain = factory.LazyAttribute(lambda obj: f"{obj.tenant.slug}.localhost")
    is_primary = True
