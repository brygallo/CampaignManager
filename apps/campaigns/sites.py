"""Registro de los modelos de campaigns en superadmin."""
from superadmin.decorators import register

from core.base import BaseSite

from .forms import (
    CampaignForm,
    CandidateForm,
    ElectionForm,
    PoliticalMovementForm,
    PositionForm,
)


@register("campaigns.Election")
class ElectionSite(BaseSite):
    form_class = ElectionForm
    list_fields = ("name", "election_date", "is_active:Activa")
    detail_fields = (
        ("name", "election_date"),
        ("description",),
    )
    search_params = ("name__icontains",)
    filter_fields = ("is_active",)


@register("campaigns.PoliticalMovement")
class PoliticalMovementSite(BaseSite):
    form_class = PoliticalMovementForm
    list_fields = ("name", "acronym", "list_number", "is_active:Activo")
    detail_fields = (
        ("name", "acronym"),
        ("list_number", "color"),
        ("logo",),
    )
    search_params = ("name__icontains", "acronym__icontains")
    filter_fields = ("is_active",)


@register("campaigns.Position")
class PositionSite(BaseSite):
    form_class = PositionForm
    list_fields = ("name", "scope", "is_active:Activo")
    detail_fields = (
        ("name", "scope"),
    )
    search_params = ("name__icontains",)
    filter_fields = ("scope", "is_active")


@register("campaigns.Candidate")
class CandidateSite(BaseSite):
    form_class = CandidateForm
    list_fields = ("full_name", "identification", "email", "phone", "is_active:Activo")
    detail_fields = (
        ("full_name", "identification"),
        ("email", "phone"),
        ("photo",),
        ("bio",),
    )
    search_params = (
        "full_name__icontains",
        "identification__icontains",
        "email__icontains",
    )
    filter_fields = ("is_active",)


@register("campaigns.Campaign")
class CampaignSite(BaseSite):
    form_class = CampaignForm
    list_fields = (
        "name",
        "election",
        "candidate",
        "movement",
        "position",
        "get_state_display:Estado",
    )
    detail_fields = {
        "Identificación": (
            ("name",),
            ("election", "candidate"),
            ("movement", "position"),
        ),
        "Vigencia": (
            ("start_date", "end_date"),
            ("get_state_display:Estado",),
        ),
        "Detalle": (
            ("description",),
        ),
        "Auditoría": (
            ("created_user", "created_date"),
            ("modified_user", "modified_date"),
        ),
    }
    search_params = (
        "name__icontains",
        "candidate__full_name__icontains",
        "election__name__icontains",
        "movement__name__icontains",
        "position__name__icontains",
    )
    filter_fields = ("state", "election", "movement", "position", "is_active")
