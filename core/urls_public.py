"""URL configuration for the PUBLIC schema (root domain only).

This conf is used by django-tenants when the request hits a host that maps
to the public schema (e.g. tudominio.com). It must NOT include tenant-specific
routes — no `superadmin` package, no per-party login, no domain apps.

For now this is a stub: a placeholder landing page. Fase 6 will add public
signup; Fase 7 will mount the global super-admin panel.
"""
from django.conf import settings
from django.http import HttpResponse
from django.urls import path, re_path

from . import views as core_views


def public_landing(request):
    return HttpResponse(
        "<h1>CampaignManager</h1>"
        "<p>Plataforma multipartido. Acceda al subdominio de su partido.</p>",
        content_type="text/html; charset=utf-8",
    )


def healthz(request):
    return HttpResponse("ok", content_type="text/plain")


urlpatterns = [
    path("healthz", healthz, name="healthz"),
    # Tenant branding (logos / favicons) is the only media expected on the
    # public schema. The view enforces auth + path-prefix checks.
    re_path(
        rf"^{settings.MEDIA_URL.lstrip('/')}(?P<path>.*)$",
        core_views.serve_protected_media,
        name="protected_media",
    ),
    path("", public_landing, name="public_landing"),
]
