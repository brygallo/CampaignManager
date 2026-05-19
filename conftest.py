"""Project-wide pytest configuration.

The test settings (`core.settings.test`) flatten the django-tenants split:
all apps run inside the public schema so existing Django TestCase fixtures
keep working without spinning a fresh schema per test. Tests that exercise
true tenant isolation should be marked with ``@pytest.mark.tenant`` and use
the ``tenant`` fixture below to get a schema_context.

Playwright E2E fixtures live here too. They build on top of pytest-django's
``live_server`` (which runs the WSGI app in a side thread bound to a random
host port) plus pytest-playwright's ``page`` fixture.
"""
from __future__ import annotations

import os

# pytest-playwright spins up an asyncio event loop in the background.
# Django's sync ORM aborts when it detects an active loop unless this flag
# is set. Tests run sync code only, so this is safe.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

# Settings selection: pytest.ini forces ``--ds=core.settings.test_e2e`` via
# ``addopts`` because pipenv pre-loads ``.env`` (which exports the dev
# ``DJANGO_SETTINGS_MODULE``) and pytest-django prefers the env var over its
# ini key — passing ``--ds`` as a command-line option is the only reliable
# way to override that. ``test_e2e.py`` itself inherits from ``test.py``,
# so unit tests pick up the same overrides.
# Tests marked ``@pytest.mark.tenant`` should run with
# ``pytest --ds=core.settings.test`` instead, to get the django-tenants engine.

import pytest
from django.contrib.auth import get_user_model
from django.db import connection


@pytest.fixture
def tenant(db):
    """Create a throwaway tenant + domain and yield it.

    The fixture is opt-in (depends on ``db``) and only useful for the
    handful of tests that must verify cross-tenant isolation. Default
    tests can ignore it.
    """
    from django_tenants.utils import schema_context

    from apps.tenancy.models import Domain, Tenant

    tenant_obj = Tenant.objects.create(
        schema_name="test_tenant",
        slug="test-tenant",
        name="Test Tenant",
    )
    Domain.objects.create(domain="test-tenant.localhost", tenant=tenant_obj, is_primary=True)

    with schema_context(tenant_obj.schema_name):
        yield tenant_obj

    # Cleanup: schema is dropped automatically because the test DB is
    # destroyed at session end, but be explicit if running with --reuse-db.
    if getattr(connection, "schema_name", None) != "public":
        connection.set_schema_to_public()
    Tenant.objects.filter(pk=tenant_obj.pk).delete()


# ---------------------------------------------------------------------------
# Playwright / E2E helpers
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Default context options for every Playwright page.

    Forcing a stable viewport, locale and timezone keeps screenshots and
    date-formatted strings reproducible across machines.
    """
    return {
        **browser_context_args,
        "viewport": {"width": 1366, "height": 900},
        "ignore_https_errors": True,
        "locale": "es-EC",
        "timezone_id": "America/Guayaquil",
    }


@pytest.fixture
def password() -> str:
    """Default password reused across the E2E suite."""
    return "Sup3rS3cret!"


@pytest.fixture
def user(db, password):
    """Active non-staff user, ready to log in via the standard form."""
    User = get_user_model()
    return User.objects.create_user(
        username="brigadier",
        email="brigadier@example.com",
        password=password,
        first_name="Brigada",
        last_name="Uno",
        is_active=True,
    )


@pytest.fixture
def staff_user(db, password):
    """Active staff user (can hit ``/admin-panel/``)."""
    User = get_user_model()
    return User.objects.create_user(
        username="coordinador",
        email="coordinador@example.com",
        password=password,
        first_name="Coord",
        last_name="General",
        is_active=True,
        is_staff=True,
    )


@pytest.fixture
def superuser(db, password):
    """Superuser fixture for tests that need to bypass permission checks."""
    User = get_user_model()
    return User.objects.create_superuser(
        username="root",
        email="root@example.com",
        password=password,
        first_name="Root",
        last_name="Admin",
    )


def _do_login(page, base_url: str, username: str, pw: str, path_prefix: str = "") -> None:
    """Walk the login form and wait for the post-login redirect.

    ``path_prefix`` is used in tenant path-routed scenarios (e.g. "/test-tenant").
    """
    page.goto(f"{base_url}{path_prefix}/login/")
    page.fill("input[name=username]", username)
    page.fill("input[name=password]", pw)
    page.click("button[type=submit]")
    # On success the view redirects to "/" (or to ``next``). Wait for the URL
    # to leave the login page rather than asserting a specific destination so
    # the helper works regardless of redirect target.
    page.wait_for_url(lambda url: "/login/" not in url, timeout=10_000)


@pytest.fixture
def login_as(page, live_server, password):
    """Factory that logs the given Django user into the active page."""

    def _login(django_user, path_prefix: str = ""):
        _do_login(page, live_server.url, django_user.username, password, path_prefix)
        return page

    return _login


@pytest.fixture
def logged_in_page(page, live_server, user, password):
    """Browser page already authenticated as the default non-staff ``user``."""
    _do_login(page, live_server.url, user.username, password)
    return page


@pytest.fixture
def logged_in_staff_page(page, live_server, staff_user, password):
    """Browser page already authenticated as a staff user."""
    _do_login(page, live_server.url, staff_user.username, password)
    return page


@pytest.fixture
def logged_in_superuser_page(page, live_server, superuser, password):
    """Browser page already authenticated as a superuser."""
    _do_login(page, live_server.url, superuser.username, password)
    return page
