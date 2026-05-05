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
from django.conf import settings
from django.db import connection
from django.urls import get_script_prefix, set_script_prefix
from django_tenants.utils import get_public_schema_name, get_tenant_model


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
