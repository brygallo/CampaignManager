"""URL configuration for the PUBLIC schema (root domain only).

This conf is used by django-tenants when the request hits a host that maps
to the public schema (e.g. tudominio.com). It must NOT include tenant-specific
routes — no `superadmin` package, no per-party login, no domain apps.

For now this is a stub: a placeholder landing page. Fase 6 will add public
signup; Fase 7 will mount the global super-admin panel.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from django.urls import path


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
    path("", public_landing, name="public_landing"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
