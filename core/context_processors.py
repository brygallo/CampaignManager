"""Context processors that expose globals to all templates."""
from django.conf import settings
from django.db import DatabaseError
from django.templatetags.static import static
from django_tenants.utils import get_public_schema_name, schema_context

# Module names listed in menu.yaml whose visibility is gated by TenantSettings
# flags. Anything not in this set is shown to every tenant.
GATED_MENU_SECTIONS = {
    "Campañas",
    "Agenda política",
    "Levantamientos de campo",
    "Publicidad territorial",
    "Geografía",
}


def _default_brand():
    icon_path = getattr(settings, "BRAND_ICON", "assets/img/control-campana.svg")
    return {
        "brand_name": getattr(settings, "BRAND_NAME", "Control de Campaña"),
        "brand_icon": icon_path,
        "brand_icon_url": static(icon_path),
        "default_theme": getattr(settings, "DEFAULT_THEME", "light"),
    }


def brand(request):
    context = _default_brand()
    tenant = getattr(request, "tenant", None)
    if not tenant or getattr(tenant, "schema_name", None) == get_public_schema_name():
        return context

    try:
        from apps.tenancy.models import TenantBranding

        with schema_context(get_public_schema_name()):
            branding = (
                TenantBranding.objects.filter(tenant__schema_name=tenant.schema_name)
                .only("brand_name", "logo", "favicon", "theme_default")
                .first()
            )
    except DatabaseError:
        return context

    if not branding:
        return context

    context["brand_name"] = branding.brand_name or getattr(tenant, "name", context["brand_name"])
    context["default_theme"] = branding.theme_default or context["default_theme"]
    if branding.logo:
        context["brand_icon_url"] = branding.logo.url
    if branding.favicon:
        context["brand_icon_url"] = branding.favicon.url
    return context


DEFAULT_MAP_CENTER = {
    "lat": -2.3046,
    "lng": -78.1175,
    "zoom": 13,
}


def _default_map_payload():
    return {
        "tenant_features": GATED_MENU_SECTIONS,
        "tenant_map_center": DEFAULT_MAP_CENTER,
    }


def tenant_features(request):
    """Expose ``tenant_features`` (enabled modules) and ``tenant_map_center``.

    Reads ``TenantSettings`` from the public schema based on the active
    tenant. When no row exists yet (legacy tenants), defaults to "everything
    enabled" + a sensible default map center so the migration is non-breaking.
    """
    tenant = getattr(request, "tenant", None)
    if not tenant or getattr(tenant, "schema_name", None) == get_public_schema_name():
        return _default_map_payload()

    try:
        from apps.tenancy.models import TenantSettings

        with schema_context(get_public_schema_name()):
            tsettings = (
                TenantSettings.objects.filter(tenant__schema_name=tenant.schema_name)
                .only(
                    "enable_campaigns",
                    "enable_political_agenda",
                    "enable_field_surveys",
                    "enable_territorial_ads",
                    "enable_locations",
                    "map_center_latitude",
                    "map_center_longitude",
                    "map_default_zoom",
                )
                .first()
            )
    except DatabaseError:
        return _default_map_payload()

    if tsettings is None:
        return _default_map_payload()
    return {
        "tenant_features": tsettings.enabled_modules(),
        "tenant_map_center": {
            "lat": float(tsettings.map_center_latitude),
            "lng": float(tsettings.map_center_longitude),
            "zoom": int(tsettings.map_default_zoom),
        },
    }


def active_campaign(request):
    """Expose ``active_campaign`` and ``available_campaigns`` to all templates.

    ``request.active_campaign`` is set by ``ActiveCampaignMiddleware``. We
    list candidates lazily so the navbar can show a selector when there is
    more than one campaign in the tenant. No-op on the public schema.

    The campaign list is memoized on the request: context processors run
    once per rendered template (including partials in the same response),
    and the navbar query shouldn't repeat for each of them.
    """
    tenant = getattr(request, "tenant", None)
    if not tenant or getattr(tenant, "schema_name", None) == get_public_schema_name():
        return {}

    campaigns = getattr(request, "_available_campaigns_cache", None)
    if campaigns is None:
        try:
            from apps.campaigns.active import list_available_campaigns

            campaigns = list(list_available_campaigns(request))
        except DatabaseError:
            return {}
        request._available_campaigns_cache = campaigns

    from apps.campaigns.active import is_campaign_read_only

    active = getattr(request, "active_campaign", None)
    return {
        "active_campaign": active,
        "available_campaigns": campaigns,
        # Tenant-schema marker so the navbar can render the selector shell
        # (e.g. the "create first campaign" CTA) even with zero campaigns.
        "campaign_selector_enabled": True,
        # Terminal-state or archived campaign: browsing-only scope.
        "active_campaign_read_only": is_campaign_read_only(active),
    }


def dev_prefill(request):
    """Expose the test-data prefill flag, gated by the ``DEV_PREFILL`` env var.

    When enabled, ``base_form.html`` renders a button (and loads the JS) that
    fills every CRUD form with dummy data except the location. Off by default
    and never enabled in production.
    """
    return {"dev_prefill_enabled": getattr(settings, "DEV_PREFILL", False)}


def tenant_path_menu(request):
    """Prefix sidebar menu URLs when tenants are routed by path.

    ``TenantPathRoutingMiddleware`` rewrites ``request.path`` to the tenant
    internal path, but rendered links still need the visible ``/<tenant>/``
    prefix or they will fall back to the public URLconf.
    """
    prefix = getattr(request, "tenant_path_prefix", "")
    if not prefix:
        return {}

    try:
        from superadmin.context_processors import build_user_menu
    except Exception:
        return {}

    def prefix_node(node):
        copied = dict(node)
        url = copied.get("url")
        if url and url.startswith("/") and not url.startswith(f"{prefix}/"):
            copied["url"] = f"{prefix}{url}"
        copied["submenus"] = [prefix_node(sub) for sub in copied.get("submenus") or []]
        return copied

    return {"menu_tree": [prefix_node(item) for item in build_user_menu(request.user)]}
