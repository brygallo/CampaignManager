"""Pure helpers for the tenancy app.

Mirrors sim's ``utils.py`` convention — small, reusable, side-effect-free
functions. ``normalize_schema_name`` was duplicated verbatim across the
``create_tenant`` and ``migrate_to_multitenant`` management commands; it lives
here now as the single source of truth.
"""
from django.core.management.base import CommandError

from apps.tenancy.constants import SAFE_SCHEMA_NAME_CHARS


def normalize_schema_name(slug: str) -> str:
    """Convert a tenant slug to a valid PostgreSQL schema name.

    Raises ``CommandError`` when the derived name is empty, contains characters
    outside ``SAFE_SCHEMA_NAME_CHARS``, or starts with a digit.
    """
    name = slug.lower().replace("-", "_")
    if not name or not all(c in SAFE_SCHEMA_NAME_CHARS for c in name):
        raise CommandError(
            f"Invalid schema name derived from slug: {name!r}. "
            "Use only lowercase letters, digits, hyphens, and underscores."
        )
    if name[0].isdigit():
        raise CommandError(f"Schema name cannot start with a digit: {name!r}.")
    return name
