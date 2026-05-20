"""Storage helpers for tenant-aware media and shared static paths."""
from urllib.parse import quote

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django_tenants.utils import get_public_schema_name
from storages.backends.s3boto3 import S3Boto3Storage


class TenantS3Storage(S3Boto3Storage):
    """S3-compatible backend that namespaces uploads under ``tenants/<schema>/``.

    Mirrors the behavior of the previous ``TenantFileSystemStorage``: every
    object written from inside a tenant schema is prefixed so two parties
    cannot reach each other's files even if they share the same bucket.
    Writes from the public schema (e.g. the global super-admin) skip the
    prefix; use :class:`PublicFileSystemStorage` for assets that must live
    at a stable, schema-agnostic path on the local filesystem instead.
    """

    file_overwrite = False

    def get_available_name(self, name, max_length=None):
        return super().get_available_name(self._tenant_name(name), max_length=max_length)

    def _save(self, name, content):
        return super()._save(self._tenant_name(name), content)

    def url(self, name, *args, **kwargs):
        return super().url(self._tenant_name(name), *args, **kwargs)

    def _tenant_name(self, name):
        from django.db import connection

        schema_name = getattr(connection, "schema_name", None)
        if not schema_name or schema_name == get_public_schema_name():
            return name
        if name.startswith(f"tenants/{schema_name}/"):
            return name
        return f"tenants/{schema_name}/{name}"


class StaticS3Storage(S3Boto3Storage):
    """Shared static asset storage in the S3-compatible bucket."""

    location = "static"
    default_acl = None
    file_overwrite = True
    querystring_auth = False

    def url(self, name, *args, **kwargs):
        public_base = (getattr(settings, "AWS_S3_PUBLIC_URL", "") or "").rstrip("/")
        if public_base:
            bucket = settings.AWS_STORAGE_BUCKET_NAME.strip("/")
            path = quote(str(name).lstrip("/"), safe="/")
            return f"{public_base}/{bucket}/{self.location}/{path}"
        return super().url(name, *args, **kwargs)


class PublicFileSystemStorage(FileSystemStorage):
    """Storage that never applies the tenant prefix.

    Used for assets owned by the ``public`` schema (currently
    ``TenantBranding.logo`` / ``.favicon``). Forces a stable path so the
    same file is reachable whether the writer is on ``public`` or inside
    a tenant schema.
    """
