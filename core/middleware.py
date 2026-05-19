"""Custom middleware that complements django-tenants.

`TenantPathRoutingMiddleware` adds a third tenant-resolution mode on top of
the two that django-tenants supports natively:

  1. Custom domain      mipartido.com           → Domain row
  2. Subdomain          pk.tudominio.com        → Domain row
  3. Path-based  (NEW)  tudominio.com/pk/...    → first URL segment == slug

It runs AFTER `TenantMainMiddleware`. If that middleware already resolved a
tenant from the host header, this one is a no-op. If we're still on the
public schema and the first path segment matches an active Tenant.slug,
we switch the connection, rewrite request.path, and set the script prefix
so reverse() generates URLs that include the slug.

Caveat: tenants sharing a root domain also share cookies and sessions.
Recommended only for trial/demo tenants. Premium tenants should use mode 1
or 2.
"""
from importlib import import_module
import time

from django.conf import settings
from django.contrib.sessions.exceptions import SessionInterrupted
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.sessions.backends.base import UpdateError
from django.db import connection
from django.urls import get_script_prefix, set_script_prefix
from django.utils.cache import patch_vary_headers
from django.utils.http import http_date
from django_tenants.utils import get_public_schema_name, get_tenant_model

# Importing this module is enough to install the multi-tenant patch on
# ``tracing.middleware.TracingMiddleware`` (see the docstring there). Done
# here because Django imports ``core.middleware`` before processing any
# request, which guarantees the patch is in place before signals fire.
from core import tracing_patches  # noqa: F401


def _tenant_cookie_slug(request):
    prefix = getattr(request, "tenant_path_prefix", "") or ""
    if not prefix:
        return ""
    return prefix.strip("/").replace("/", "_")


def _session_cookie_name_for_request(request):
    slug = _tenant_cookie_slug(request)
    if not slug:
        return settings.SESSION_COOKIE_NAME
    return f"{settings.SESSION_COOKIE_NAME}_{slug}"


def _session_cookie_path_for_request(request):
    prefix = getattr(request, "tenant_path_prefix", "") or ""
    if not prefix:
        return settings.SESSION_COOKIE_PATH
    return f"{prefix}/"


class TenantAwareSessionMiddleware(SessionMiddleware):
    """Use one session cookie per path-routed tenant.

    Path-routed tenants (``/slug/...``) share the same host with the public
    landing. Reusing a single cookie name (``sessionid``) can leave the
    browser with multiple cookies of the same name but different paths, which
    makes the next request ambiguous and can bounce an apparently successful
    login back to ``/login/``. Naming the cookie per slug removes that clash.
    """

    def process_request(self, request):
        cookie_name = _session_cookie_name_for_request(request)
        cookie_path = _session_cookie_path_for_request(request)
        session_key = request.COOKIES.get(cookie_name)

        # Backward-compatible fallback for pre-fix cookies. The response will
        # re-issue the session under the tenant-specific name.
        if session_key is None and cookie_name != settings.SESSION_COOKIE_NAME:
            session_key = request.COOKIES.get(settings.SESSION_COOKIE_NAME)

        request._session_cookie_name = cookie_name
        request._session_cookie_path = cookie_path
        request.session = self.SessionStore(session_key)

    def process_response(self, request, response):
        try:
            accessed = request.session.accessed
            modified = request.session.modified
            empty = request.session.is_empty()
        except AttributeError:
            return response

        cookie_name = getattr(request, "_session_cookie_name", settings.SESSION_COOKIE_NAME)
        cookie_path = getattr(request, "_session_cookie_path", settings.SESSION_COOKIE_PATH)
        legacy_cookie_name = settings.SESSION_COOKIE_NAME

        if cookie_name in request.COOKIES and empty:
            response.delete_cookie(
                cookie_name,
                path=cookie_path,
                domain=settings.SESSION_COOKIE_DOMAIN,
                samesite=settings.SESSION_COOKIE_SAMESITE,
            )
            patch_vary_headers(response, ("Cookie",))
        else:
            if accessed:
                patch_vary_headers(response, ("Cookie",))
            if (modified or settings.SESSION_SAVE_EVERY_REQUEST) and not empty:
                if request.session.get_expire_at_browser_close():
                    max_age = None
                    expires = None
                else:
                    max_age = request.session.get_expiry_age()
                    expires = http_date(time.time() + max_age)
                if response.status_code < 500:
                    try:
                        request.session.save()
                    except UpdateError:
                        raise SessionInterrupted(
                            "The request's session was deleted before the "
                            "request completed. The user may have logged "
                            "out in a concurrent request, for example."
                        )
                    response.set_cookie(
                        cookie_name,
                        request.session.session_key,
                        max_age=max_age,
                        expires=expires,
                        domain=settings.SESSION_COOKIE_DOMAIN,
                        path=cookie_path,
                        secure=settings.SESSION_COOKIE_SECURE or None,
                        httponly=settings.SESSION_COOKIE_HTTPONLY or None,
                        samesite=settings.SESSION_COOKIE_SAMESITE,
                    )

        if cookie_name != legacy_cookie_name:
            response.delete_cookie(
                legacy_cookie_name,
                path=settings.SESSION_COOKIE_PATH,
                domain=settings.SESSION_COOKIE_DOMAIN,
                samesite=settings.SESSION_COOKIE_SAMESITE,
            )

        return response


class PublicSchemaSessionRoutingMiddleware:
    """Swap the session store on `public` before auth/messages touch it.

    The public landing runs on the `public` schema, which deliberately does
    not contain tenant-only tables such as `django_session`. Using the regular
    DB-backed session engine there causes every anonymous request to `/` to
    fail before the view runs. Tenant schemas keep the default session engine.
    The standard SessionMiddleware remains in MIDDLEWARE so Django's checks
    and admin integration still see it.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self._public_session_store = import_module(
            "django.contrib.sessions.backends.signed_cookies"
        ).SessionStore

    def __call__(self, request):
        if connection.schema_name == get_public_schema_name():
            session_key = request.COOKIES.get(settings.SESSION_COOKIE_NAME)
            request.session = self._public_session_store(session_key)
        return self.get_response(request)


class TenantPathRoutingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if connection.schema_name != get_public_schema_name():
            return self.get_response(request)

        path = request.path_info
        parts = path.lstrip("/").split("/", 1)
        candidate_slug = parts[0] if parts and parts[0] else ""
        if not candidate_slug:
            return self.get_response(request)

        TenantModel = get_tenant_model()
        try:
            tenant = TenantModel.objects.get(slug=candidate_slug, is_active=True)
        except TenantModel.DoesNotExist:
            return self.get_response(request)

        connection.set_tenant(tenant)
        request.tenant = tenant
        request.tenant_path_prefix = f"/{candidate_slug}"

        new_path = "/" + (parts[1] if len(parts) > 1 else "")
        request.path_info = new_path
        request.path = new_path

        old_script_prefix = get_script_prefix()
        set_script_prefix(f"/{candidate_slug}/")
        request.urlconf = settings.ROOT_URLCONF

        try:
            response = self.get_response(request)
            self._prefix_tenant_redirect(request, response)
            self._scope_cookies_to_tenant(request, response)
            return response
        finally:
            set_script_prefix(old_script_prefix)

    def _prefix_tenant_redirect(self, request, response):
        """Keep local redirects inside the path-routed tenant namespace."""
        if response.status_code not in {301, 302, 303, 307, 308}:
            return

        location = response.get("Location")
        prefix = getattr(request, "tenant_path_prefix", "")
        if not location or not prefix:
            return
        if not location.startswith("/"):
            return
        if location.startswith((f"{prefix}/", f"{prefix}?", "//")):
            return
        if location.startswith((settings.STATIC_URL, settings.MEDIA_URL)):
            return

        response["Location"] = f"{prefix}{location}"

    def _scope_cookies_to_tenant(self, request, response):
        """Set cookie ``Path`` to the tenant prefix so cookies don't bleed.

        In path-routed mode (mode C in docs/05_MULTITENANT_SPRINT1.md) every
        tenant lives on the same root domain. Without scoping, a session
        cookie issued by ``/pk1/login/`` would also be sent on requests to
        ``/pk2/...``. Pinning ``Path=/pk1/`` keeps each tenant's cookies in
        their own URL namespace.
        """
        prefix = getattr(request, "tenant_path_prefix", "")
        if not prefix:
            return
        scoped_path = f"{prefix}/"
        for morsel in response.cookies.values():
            current_path = morsel["path"] or "/"
            if current_path == "/" or not current_path.startswith(prefix):
                morsel["path"] = scoped_path
