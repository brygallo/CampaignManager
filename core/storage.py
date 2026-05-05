"""Storage helpers for tenant-aware media paths."""
from django.core.files.storage import FileSystemStorage
from django_tenants.utils import get_public_schema_name


class TenantFileSystemStorage(FileSystemStorage):
    """Prefix tenant uploads with the active schema to avoid cross-tenant paths.

    All tenant-owned files end up under ``MEDIA_ROOT/tenants/<schema>/...``.
    Files written from the public schema (e.g. ``TenantBranding`` logos
    edited from the global super-admin) bypass the prefix and rely on the
    field's ``upload_to`` to produce a stable path. Use
    :class:`PublicFileSystemStorage` explicitly on those fields so the path
    is identical regardless of which schema the writer is in.
    """

    def get_available_name(self, name, max_length=None):
        return super().get_available_name(self._tenant_name(name), max_length=max_length)

    def _save(self, name, content):
        return super()._save(self._tenant_name(name), content)

    def url(self, name):
        return super().url(self._tenant_name(name))

    def _tenant_name(self, name):
        from django.db import connection

        schema_name = getattr(connection, "schema_name", None)
        if not schema_name or schema_name == get_public_schema_name():
            return name
        if name.startswith(f"tenants/{schema_name}/"):
            return name
        return f"tenants/{schema_name}/{name}"


class PublicFileSystemStorage(FileSystemStorage):
    """Storage that never applies the tenant prefix.

    Used for assets owned by the ``public`` schema (currently
    ``TenantBranding.logo`` / ``.favicon``). Forces a stable path so the
    same file is reachable whether the writer is on ``public`` or inside
    a tenant schema.
    """
