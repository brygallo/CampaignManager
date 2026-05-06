"""URL configuration for the PUBLIC schema (root domain only).

This conf is used by django-tenants when the request hits a host that maps
to the public schema (e.g. tudominio.com). It must NOT include tenant-specific
routes — no `superadmin` package, no per-party login, no domain apps.

For now this is a stub: a placeholder landing page. Fase 6 will add public
signup; Fase 7 will mount the global super-admin panel.
"""
import json

from django.conf import settings
from django.db.models import Prefetch
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import path, re_path
from django_tenants.utils import get_public_schema_name

from . import views as core_views


_AVATAR_PALETTE = ["primary", "success", "warning", "info", "danger", "secondary"]


def _initials(name: str) -> str:
    parts = [p for p in (name or "").split() if p]
    letters = [p[0] for p in parts[:2]]
    return ("".join(letters) or "?").upper()


def public_landing(request):
    """Marketing landing for the platform's root domain.

    Renders a card grid of active tenants so users can pick their party and
    jump straight to its login. Falls back to a free-text slug input for
    parties that aren't listed.
    """
    from apps.tenancy.models import Domain, Tenant

    root_host = request.get_host()
    scheme = request.scheme

    primary_domains = Prefetch(
        "domains",
        queryset=Domain.objects.filter(is_primary=True),
        to_attr="_primary_domains",
    )
    tenants_qs = (
        Tenant.objects
        .filter(is_active=True)
        .exclude(schema_name=get_public_schema_name())
        .select_related("branding")
        .prefetch_related(primary_domains)
        .order_by("name")
    )

    parties = []
    for i, t in enumerate(tenants_qs):
        primary = (t._primary_domains[0].domain if t._primary_domains else None)
        login_url = (
            f"{scheme}://{primary}/"
            if primary
            else f"{scheme}://{root_host}/{t.slug}/"
        )
        domain_label = primary or f"{root_host}/{t.slug}"
        brand_name = (
            getattr(getattr(t, "branding", None), "brand_name", "") or t.name
        )
        parties.append({
            "name": brand_name,
            "slug": t.slug,
            "initials": _initials(brand_name),
            "color": _AVATAR_PALETTE[i % len(_AVATAR_PALETTE)],
            "login_url": login_url,
            "domain_label": domain_label,
        })

    return render(
        request,
        "public/landing.html",
        {
            "root_host": root_host,
            "root_host_json": json.dumps(root_host),
            "parties": parties,
        },
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
