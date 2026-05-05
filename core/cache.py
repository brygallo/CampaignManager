"""Cache helpers that keep keys isolated per tenant schema.

Without a tenant-aware key function, two tenants hitting the same view
(or the same Select2 widget) would share the same Redis entries and read
each other's data. ``tenant_cache_key`` is wired in via
``CACHES['default']['KEY_FUNCTION']`` so every cache write/read is
silently scoped to the active PostgreSQL schema.
"""
from django.db import connection


def tenant_cache_key(key, key_prefix, version):
    schema = getattr(connection, "schema_name", "public") or "public"
    return f"{schema}:{key_prefix}:{version}:{key}"
