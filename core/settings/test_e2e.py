"""Settings for the Playwright E2E suite.

The default ``core.settings.test`` keeps the ``django_tenants.postgresql_backend``
engine so existing ``TestCase`` fixtures keep working. That engine plays badly
with pytest-django's ``transactional_db`` fixture (implied by ``live_server``):
``flush`` between tests re-runs ``migrate_schemas`` which then trips over
``contenttypes.0002_remove_content_type_name`` in the public schema.

The E2E suite doesn't need tenant routing — tenants are exercised via the
explicit ``tenant`` fixture / ``@pytest.mark.tenant`` markers — so we drop
the tenant engine entirely here and use the stock PostgreSQL backend.
"""
from .test import *  # noqa: F401,F403

# Disable django-tenants entirely for E2E tests. Without it, every migration
# runs once against the public schema using Django's default machinery and
# ``transactional_db`` can TRUNCATE freely between tests.
DATABASES["default"]["ENGINE"] = "django.db.backends.postgresql"  # noqa: F405

# ``django_tenants`` requires its router to be wired up; if we strip the
# router AND the app, the app's AppConfig.ready() check never fires.
INSTALLED_APPS = [  # noqa: F405
    app for app in INSTALLED_APPS if app != "django_tenants"  # noqa: F405
]
SHARED_APPS = INSTALLED_APPS  # noqa: F405
TENANT_APPS = []

DATABASE_ROUTERS = ()

# django-tenants middleware and URL conf are no-ops without the tenant engine;
# strip them so each request resolves directly against ``core.urls``.
# ``TenantAwareSessionMiddleware`` stands in for Django's default
# ``SessionMiddleware`` in production, so we have to put the stock middleware
# back when we drop the tenant-aware one (otherwise ``AuthenticationMiddleware``
# trips on the missing ``request.session``).
MIDDLEWARE = [  # noqa: F405
    m for m in MIDDLEWARE  # noqa: F405
    if m not in {
        "django_tenants.middleware.main.TenantMainMiddleware",
        "core.middleware.TenantPathRoutingMiddleware",
        "core.middleware.TenantAwareSessionMiddleware",
        "core.middleware.PublicSchemaSessionRoutingMiddleware",
    }
]
# Insert SessionMiddleware right after SecurityMiddleware (same slot the
# tenant-aware one occupies in production).
_security_idx = MIDDLEWARE.index("django.middleware.security.SecurityMiddleware")
MIDDLEWARE.insert(_security_idx + 1, "django.contrib.sessions.middleware.SessionMiddleware")

# NOTE: without django-tenants the context processors that read tenant
# branding / settings short-circuit, so the navbar campaign selector and
# tenant-specific theming don't render. Tests that need to exercise those
# pieces should run under ``--ds=core.settings.test`` with the ``tenant``
# fixture instead.
