"""Register territorial advertising models in superadmin."""
from superadmin.decorators import register

from core.base import BaseSite
from core.list_mixins import WorkflowStateFilterMixin

from .forms import PhysicalAdvertisementForm
from .models import PhysicalAdvertisement


@register("territorial_ads.PhysicalAdvertisement")
class PhysicalAdvertisementSite(BaseSite):
    form_class = PhysicalAdvertisementForm
    list_mixins = (WorkflowStateFilterMixin,)
    list_fields = (
        "code",
        "title",
        "campaign",
        "owner_name",
        "canton",
        "sector",
        "get_state_display:Estado",
        "assigned_installer",
        "installer_team",
    )
    detail_fields = {
        "Publicidad": (
            ("campaign", "advertisement_type"),
            ("title", "quantity"),
            ("width_meters", "height_meters"),
        ),
        "Contacto que ofreció el lugar": (
            ("owner_name", "owner_phone"),
            ("offered_notes",),
        ),
        "Ubicación ofrecida": (
            ("province", "canton"),
            ("parish", "sector"),
            ("address",),
            ("reference",),
            ("offered_latitude", "offered_longitude"),
        ),
        "Seguimiento": (
            ("code", "get_state_display:Estado"),
        ),
        "Aprobación y asignación": (
            ("approved_by", "approved_at"),
            ("assigned_installer", "installer_team"),
            ("assigned_by", "assigned_at"),
        ),
        "Instalación": (
            ("installation_photo",),
            ("installed_latitude", "installed_longitude"),
            ("installed_at", "installed_by"),
            ("installation_notes",),
        ),
        "Control posterior": (
            ("damage_notes", "damage_photo"),
            ("damage_reported_at", "damage_reported_by"),
            ("retirement_notes", "retirement_photo"),
            ("retired_at", "retired_by"),
        ),
    }
    search_params = (
        "code__icontains",
        "title__icontains",
        "owner_name__icontains",
        "owner_phone__icontains",
        "province__name__icontains",
        "canton__name__icontains",
        "parish__name__icontains",
        "sector__name__icontains",
        "address__icontains",
    )
    filter_fields = (
        "state",
        "campaign",
        "advertisement_type",
        "province",
        "canton",
        "assigned_installer",
        "is_active",
    )
    detail_maps = (
        ("Ubicación ofrecida", "offered_latitude", "offered_longitude"),
        ("Ubicación GPS de instalación", "installed_latitude", "installed_longitude"),
    )
