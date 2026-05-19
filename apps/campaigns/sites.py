"""Register campaign models in superadmin."""
from superadmin.decorators import register

from core.audit import AuditContextMixin
from core.base import BaseSite, BlockEditOnReadOnlyStateMixin, DetailMapsMixin, ProtectedDeleteMixin
from core.list_mixins import DropdownFilterMixin, OrderingMixin, WorkflowStateFilterMixin

from .list_mixins import VisibleCampaignsMixin
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
    list_mixins = (OrderingMixin, DropdownFilterMixin)
    list_fields = ("name", "election_date", "is_active:Activa")
    detail_fields = ElectionForm.Meta.fieldsets
    search_params = ("name__icontains",)
    filter_fields = ("is_active:Activa", "election_date:Fecha de elección")


@register("campaigns.PoliticalMovement")
class PoliticalMovementSite(BaseSite):
    form_class = PoliticalMovementForm
    list_mixins = (OrderingMixin, DropdownFilterMixin)
    list_fields = ("name", "acronym", "list_number", "is_active:Activo")
    detail_fields = PoliticalMovementForm.Meta.fieldsets
    search_params = ("name__icontains", "acronym__icontains")
    filter_fields = ("is_active:Activo",)


@register("campaigns.Position")
class PositionSite(BaseSite):
    form_class = PositionForm
    list_mixins = (OrderingMixin, DropdownFilterMixin)
    list_fields = ("name", "scope", "is_active:Activo")
    detail_fields = PositionForm.Meta.fieldsets
    search_params = ("name__icontains",)
    filter_fields = ("scope:Alcance", "is_active:Activo")


@register("campaigns.Candidate")
class CandidateSite(BaseSite):
    form_class = CandidateForm
    list_mixins = (OrderingMixin, DropdownFilterMixin)
    list_fields = ("full_name", "identification", "email", "phone", "is_active:Activo")
    detail_fields = CandidateForm.Meta.fieldsets
    search_params = (
        "full_name__icontains",
        "identification__icontains",
        "email__icontains",
    )
    filter_fields = ("is_active:Activo",)


@register("campaigns.Campaign")
class CampaignSite(BaseSite):
    form_class = CampaignForm
    # The Campaign site manages the campaigns themselves: scoping its own
    # queryset to the active campaign would hide every other campaign in
    # the list and break the picker. Same for the form, which obviously
    # doesn't have a "campaign" FK on itself.
    respect_active_campaign = False
    list_mixins = (VisibleCampaignsMixin, OrderingMixin, WorkflowStateFilterMixin, DropdownFilterMixin)
    detail_mixins = (VisibleCampaignsMixin, AuditContextMixin, DetailMapsMixin)
    delete_mixins = (VisibleCampaignsMixin, ProtectedDeleteMixin)
    update_mixins = (VisibleCampaignsMixin, BlockEditOnReadOnlyStateMixin)
    list_fields = (
        "name",
        "election",
        "candidate",
        "movement",
        "position",
        "get_state_display:Estado",
        "is_default:Predeterminada",
    )
    detail_fields = CampaignForm.Meta.fieldsets
    search_params = (
        "name__icontains",
        "candidate__full_name__icontains",
        "election__name__icontains",
        "movement__name__icontains",
        "position__name__icontains",
    )
    filter_fields = (
        "state:Estado",
        "election:Elección",
        "movement:Movimiento",
        "position:Cargo",
        "is_active:Activa",
        "start_date:Fecha de inicio",
    )
