from superadmin.decorators import register

from core.audit import AuditContextMixin
from core.base import (
    BaseSite,
    DetailMapsMixin,
    HideEmptyFieldsetsMixin,
)
from core.form_mixins import SaveOptionsMixin
from core.list_mixins import OrderingMixin, WorkflowStateFilterMixin
from core.map_mixins import MapAjaxDeleteMixin

from .forms import AdvertisingRefusalForm, PhysicalAdvertisementForm
from .views import (
    PhysicalAdMapAjaxCreateMixin,
    PhysicalAdMapAjaxUpdateMixin,
    PhysicalAdMapInitialLocationMixin,
    RefusalMapAjaxUpdateMixin,
)


@register("territorial_ads.AdvertisingRefusal")
class AdvertisingRefusalSite(BaseSite):
    form_class = AdvertisingRefusalForm
    detail_mixins = (AuditContextMixin, HideEmptyFieldsetsMixin, DetailMapsMixin)
    update_mixins = (RefusalMapAjaxUpdateMixin,)
    delete_mixins = (MapAjaxDeleteMixin,)

    list_fields = (
        "id",
        "campaign",
        "owner_reference",
        "reason",
        "reported_by",
        "created_date",
    )
    detail_fields = {
        "Rechazo": (
            ("campaign",),
            ("owner_reference",),
            ("reason",),
        ),
        "Ubicación": (
            ("latitude", "longitude"),
        ),
        "Registro": (
            ("reported_by", "created_date"),
        ),
    }
    search_params = (
        "owner_reference__icontains",
        "reason__icontains",
    )
    filter_fields = ("campaign", "is_active")
    detail_maps = (
        {
            "title": "Ubicación",
            "points": [
                {
                    "label": "Rechazo",
                    "lat": "latitude",
                    "lng": "longitude",
                    "color": "#7e8299",
                },
            ],
        },
    )


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
    list_template_name = "territorial_ads/physicaladvertisement_list.html"
    list_mixins = (OrderingMixin, WorkflowStateFilterMixin)
    create_mixins = (
        PhysicalAdMapInitialLocationMixin,
        PhysicalAdMapAjaxCreateMixin,
        SaveOptionsMixin,
    )
    update_mixins = (PhysicalAdMapAjaxUpdateMixin,)
    delete_mixins = (MapAjaxDeleteMixin,)
    detail_mixins = (AuditContextMixin, HideEmptyFieldsetsMixin, DetailMapsMixin)

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
        "Seguimiento": (("code", "get_state_display:Estado"),),
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
        "Retiro": (("retired_at", "retired_by"),),
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
