"""Context processors that expose globals to all templates."""
from django.conf import settings


def brand(request):
    return {
        "brand_name": getattr(settings, "BRAND_NAME", "Control de Campaña"),
        "brand_icon": getattr(settings, "BRAND_ICON", "assets/img/control-campana.svg"),
        "default_theme": getattr(settings, "DEFAULT_THEME", "light"),
    }
