"""Storage helpers for tenant-aware media paths."""
from django.core.files.storage import FileSystemStorage
from django_tenants.utils import get_public_schema_name


class TenantFileSystemStorage(FileSystemStorage):
    """Prefix tenant uploads with the active schema to avoid cross-tenant paths."""

    def get_available_name(self, name, max_length=None):
        return super().get_available_name(self._tenant_name(name), max_length=max_length)

    def _tenant_name(self, name):
        from django.db import connection

        schema_name = getattr(connection, "schema_name", None)
        if not schema_name or schema_name == get_public_schema_name():
            return name
        if name.startswith(f"tenants/{schema_name}/"):
            return name
        return f"tenants/{schema_name}/{name}"
