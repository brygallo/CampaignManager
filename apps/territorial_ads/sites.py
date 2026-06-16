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

from .forms import (
    AdvertisingRefusalForm,
    PhysicalAdvertisementForm,
    PhysicalAdvertisementItemFormSet,
)
from .views import (
    MaterializeUnitsMixin,
    PhysicalAdMapAjaxCreateMixin,
    PhysicalAdMapAjaxUpdateMixin,
    PhysicalAdMapInitialLocationMixin,
    RefusalMapAjaxUpdateMixin,
)


@register("territorial_ads.AdvertisingRefusal")
class AdvertisingRefusalSite(BaseSite):
    form_class = AdvertisingRefusalForm
    list_template_name = "territorial_ads/advertisingrefusal_list.html"
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


@register("territorial_ads.AdvertisingTypeSize")
class AdvertisingTypeSizeSite(BaseSite):
    """Catálogo de tamaños por tipo de publicidad (Sticker: pequeño…)."""

    list_fields = ("advertisement_type", "name", "order", "is_active:Activo")
    detail_fields = {
        "Tamaño": (
            ("advertisement_type",),
            ("name", "order"),
        ),
    }
    search_params = ("name__icontains", "advertisement_type__name__icontains")
    filter_fields = ("advertisement_type", "is_active:Activo")


@register("territorial_ads.PhysicalAdvertisementUnit")
class PhysicalAdvertisementUnitSite(BaseSite):
    """Las publicidades físicas se crean al aprobar una solicitud y se
    gestionan vía transiciones, así que el sitio solo lista y muestra."""

    allow_views = ("list", "detail")
    list_template_name = "territorial_ads/physicaladvertisementunit_list.html"
    detail_mixins = (AuditContextMixin, HideEmptyFieldsetsMixin, DetailMapsMixin)

    list_fields = (
        "code:Código",
        "display_label:Publicidad",
        "request_code:Solicitud",
        "request_campaign:Campaña",
        "get_state_display:Estado",
        "assigned_installer",
        "installer_team",
        "installed_at",
        "installed_by",
    )
    detail_fields = {
        "Publicidad": (
            ("code:Código", "display_label:Publicidad"),
            ("item__advertisement:Solicitud", "size"),
        ),
        "Asignación": (
            ("assigned_installer", "installer_team"),
            ("assigned_by", "assigned_at"),
        ),
        "Instalación": (
            ("photo",),
            ("latitude", "longitude"),
            ("installed_at", "installed_by"),
            ("notes",),
        ),
        "Daño": (
            ("damage_reported_at", "damage_reported_by"),
            ("damage_notes",),
            ("damage_photo",),
        ),
        "Retiro": (("retired_at", "retired_by"),),
    }
    search_params = (
        "item__advertisement__code__icontains",
        "item__advertisement__address__icontains",
        "item__advertisement_type__name__icontains",
    )
    filter_fields = ("state",)
    detail_maps = (
        {
            "title": "Ubicación",
            "points": [
                {
                    "label": "Instalada",
                    "lat": "latitude",
                    "lng": "longitude",
                    "color": "#198754",
                },
            ],
        },
    )


@register("territorial_ads.PhysicalAdvertisement")
class PhysicalAdvertisementSite(BaseSite):
    form_class = PhysicalAdvertisementForm
    # Superadmin's InlinesMixin: per-type quantities edited as inline rows.
    inlines = (PhysicalAdvertisementItemFormSet,)
    form_template_name = "territorial_ads/physicaladvertisement_form.html"
    list_template_name = "territorial_ads/physicaladvertisement_list.html"
    # Custom detail: adds the per-unit "Publicidades" cards (state, evidence
    # and per-unit transition buttons) under the regular fieldsets.
    detail_template_name = "territorial_ads/physicaladvertisement_detail.html"
    list_mixins = (OrderingMixin, WorkflowStateFilterMixin)
    create_mixins = (
        MaterializeUnitsMixin,
        PhysicalAdMapInitialLocationMixin,
        PhysicalAdMapAjaxCreateMixin,
        SaveOptionsMixin,
    )
    update_mixins = (MaterializeUnitsMixin, PhysicalAdMapAjaxUpdateMixin)
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
    )
    detail_fields = {
        "Publicidad": (
            ("campaign",),
            ("items_summary_badges:Tipos de publicidad",),
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
            ("items_sizes_summary:Tamaños por unidad",),
            ("items_instructions_summary:Indicaciones por unidad",),
        ),
        "Instalación": (
            ("units_state_summary:Publicidades",),
            ("installed_at", "installed_by"),
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
        "cost_type",
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
