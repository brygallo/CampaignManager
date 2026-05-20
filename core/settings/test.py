"""Test settings."""
from .base import *  # noqa: F401,F403

DEBUG = False
SECRET_KEY = "test-secret-key"  # noqa: S105

DATABASES["default"]["ENGINE"] = "django_tenants.postgresql_backend"  # noqa: F405
DATABASES["default"]["TEST"] = {  # noqa: F405
    "NAME": env("TEST_DATABASE_NAME", default="test_campaignmanager"),  # noqa: F405
}
# When running pytest from the host (e.g. Playwright suite needs a host-side
# `live_server`), DATABASE_URL still points to the docker service name. Allow
# overriding the host explicitly via TEST_DATABASE_HOST without touching .env.
DATABASES["default"]["HOST"] = env("TEST_DATABASE_HOST", default=DATABASES["default"].get("HOST") or "localhost")  # noqa: F405

# Existing Django TestCase tests are not tenant-aware yet, so run their schema
# in public while keeping the django-tenants PostgreSQL backend active.
SHARED_APPS = INSTALLED_APPS  # noqa: F405
TENANT_APPS = ["django.contrib.contenttypes"]

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    },
}

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Tests must not depend on a live MinIO/S3 server: route uploads to disk.
STORAGES = {  # noqa: F405
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]
