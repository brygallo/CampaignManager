"""Context processors that expose globals to all templates."""
from django.conf import settings
from django.db import DatabaseError
from django.templatetags.static import static
from django_tenants.utils import get_public_schema_name, schema_context


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
