"""Context processors that expose globals to all templates."""
from django.conf import settings

from .tenancy import get_user_sites


def active_site(request):
    return {
        "active_site": getattr(request, "active_site", None),
        "available_sites": get_user_sites(request),
        "brand_name": getattr(settings, "MAXTON_BRAND_NAME", "CampaignManager"),
        "default_theme": getattr(settings, "MAXTON_DEFAULT_THEME", "light"),
    }
