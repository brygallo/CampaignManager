"""Registro de modelos en superadmin."""
from superadmin.decorators import register

from core.base import BaseSite

from .forms import DomainForm, SiteForm, SiteMembershipForm


@register("sites_mgmt.Site")
class SiteSite(BaseSite):
    form_class = SiteForm
    list_fields = ("name", "slug", "currency", "timezone", "is_active:Activo")
    detail_fields = {
        "Información del sitio": (
            ("name", "slug"),
            ("brand_color", "logo"),
            ("timezone", "currency"),
            ("description",),
        ),
        "Auditoría": (
            ("created_user", "created_date"),
            ("modified_user", "modified_date"),
        ),
    }
    search_params = ("name__icontains", "slug__icontains")
    filter_fields = ("is_active",)
    slug_field = "slug"
    prepopulate_slug = ("name",)


@register("sites_mgmt.Domain")
class DomainSite(BaseSite):
    form_class = DomainForm
    list_fields = ("site", "host", "is_primary")
    detail_fields = ("site", "host", "is_primary")
    search_params = ("host__icontains",)
    filter_fields = ("is_primary", "site")


@register("sites_mgmt.SiteMembership")
class SiteMembershipSite(BaseSite):
    form_class = SiteMembershipForm
    list_fields = ("user", "site", "role")
    detail_fields = ("user", "site", "role")
    search_params = (
        "user__username__icontains",
        "user__email__icontains",
        "site__name__icontains",
    )
    filter_fields = ("role", "site")
