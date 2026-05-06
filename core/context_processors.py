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


def tenant_features(request):
    """Expose ``tenant_features`` (set of enabled module names) to templates.

    Reads ``TenantSettings`` from the public schema based on the active
    tenant. When no row exists yet (legacy tenants), defaults to "everything
    enabled" so the migration is non-breaking.
    """
    tenant = getattr(request, "tenant", None)
    if not tenant or getattr(tenant, "schema_name", None) == get_public_schema_name():
        return {"tenant_features": GATED_MENU_SECTIONS}

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
                )
                .first()
            )
    except DatabaseError:
        return {"tenant_features": GATED_MENU_SECTIONS}

    if tsettings is None:
        return {"tenant_features": GATED_MENU_SECTIONS}
    return {"tenant_features": tsettings.enabled_modules()}


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
