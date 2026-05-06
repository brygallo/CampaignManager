"""Register territorial advertising models in superadmin."""
from superadmin.decorators import register

from core.base import BaseSite, DetailMapsMixin, HideEmptyFieldsetsMixin
from core.list_mixins import WorkflowStateFilterMixin

from .forms import PhysicalAdvertisementForm
from .models import AdvertisingCostType, PhysicalAdvertisement


@register("territorial_ads.AdvertisingCostType")
class AdvertisingCostTypeSite(BaseSite):
    list_fields = ("code", "name", "order", "requires_amount", "is_active:Activo")
    detail_fields = {
        "Tipo de costo": (
            ("code", "name"),
            ("order", "requires_amount"),
        ),
    }
    search_params = ("code__icontains", "name__icontains")
    filter_fields = ("requires_amount", "is_active:Activo")


@register("territorial_ads.PhysicalAdvertisement")
class PhysicalAdvertisementSite(BaseSite):
    form_class = PhysicalAdvertisementForm
    form_template_name = "territorial_ads/physicaladvertisement_form.html"
    list_mixins = (WorkflowStateFilterMixin,)
    detail_mixins = (HideEmptyFieldsetsMixin, DetailMapsMixin)
    always_visible_fieldsets = (
        "Publicidad",
        "Contacto que ofreció el lugar",
        "Ubicación ofrecida",
        "Seguimiento",
    )
    list_fields = (
        "code",
        "campaign",
        "owner_name",
        "cost_type:Costo",
        "get_state_display:Estado",
        "assigned_installer",
        "installer_team",
    )
    detail_fields = {
        "Publicidad": (
            ("campaign", "advertisement_type"),
            ("quantity",),
        ),
        "Contacto que ofreció el lugar": (
            ("owner_name", "owner_phone"),
            ("cost_type", "cost_amount"),
            ("offered_notes",),
        ),
        "Ubicación ofrecida": (
            ("address",),
            ("reference",),
            ("offered_latitude", "offered_longitude"),
            ("offered_photo",),
        ),
        "Seguimiento": (
            ("code", "get_state_display:Estado"),
        ),
        "Rechazo": (
            ("rejected_at", "rejected_by"),
            ("rejection_reason",),
        ),
        "Aprobación": (
            ("approved_by", "approved_at"),
            ("width_meters", "height_meters"),
            ("installation_instructions",),
        ),
        "Asignación de instalación": (
            ("assigned_installer", "installer_team"),
            ("assigned_by", "assigned_at"),
        ),
        "Instalación": (
            ("installation_photo",),
            ("installed_latitude", "installed_longitude"),
            ("installed_at", "installed_by"),
            ("installation_notes",),
        ),
        "Daño reportado": (
            ("damage_reported_at", "damage_reported_by"),
            ("damage_notes",),
            ("damage_photo",),
        ),
        "Retiro": (
            ("retired_at", "retired_by"),
        ),
    }
    search_params = (
        "code__icontains",
        "owner_name__icontains",
        "owner_phone__icontains",
        "address__icontains",
    )
    filter_fields = (
        "state",
        "campaign",
        "advertisement_type",
        "cost_type",
        "assigned_installer",
        "is_active",
    )
    detail_maps = (
        {
            "title": "Ubicaciones",
            "points": [
                {
                    "label": "Ofrecida",
                    "lat": "offered_latitude",
                    "lng": "offered_longitude",
                    "color": "#3388ff",
                },
                {
                    "label": "Instalada",
                    "lat": "installed_latitude",
                    "lng": "installed_longitude",
                    "color": "#198754",
                },
            ],
        },
    )
