from superadmin.decorators import register

from core.base import BaseSite
from core.list_mixins import DropdownFilterMixin, WorkflowStateFilterMixin

from .forms import PoliticalAgendaEventForm, PoliticalAgendaRequestForm
from .models import PoliticalAgendaEvent, PoliticalAgendaRequest


@register("political_agenda.PoliticalAgendaRequest")
class PoliticalAgendaRequestSite(BaseSite):
    form_class = PoliticalAgendaRequestForm
    list_mixins = (WorkflowStateFilterMixin, DropdownFilterMixin)
    list_fields = (
        "title",
        "campaign",
        "requester_name",
        "event_type",
        "get_state_display:Estado",
        "priority",
        "proposed_start_at",
    )
    detail_fields = {
        "Solicitud": (
            ("campaign", "title"),
            ("event_type", "get_state_display"),
            ("priority", "blocks_candidate_agenda"),
        ),
        "Solicitante": (
            ("requester_name", "requester_phone"),
            ("requester_email", "organization"),
        ),
        "Fecha tentativa": (
            ("proposed_start_at", "proposed_end_at"),
            ("alternative_dates",),
        ),
        "Ubicación tentativa": (
            ("province", "canton"),
            ("parish", "sector"),
            ("address",),
            ("reference",),
        ),
        "Detalle": (
            ("objective",),
            ("expected_attendees",),
            ("notes",),
        ),
        "Revisión": (
            ("reviewed_by", "reviewed_at"),
            ("rejection_reason",),
        ),
    }
    search_params = (
        "title__icontains",
        "requester_name__icontains",
        "organization__icontains",
        "address__icontains",
    )
    filter_fields = (
        "campaign:Campaña",
        "event_type:Tipo",
        "state:Estado",
        "priority:Prioridad",
        "proposed_start_at:Fecha tentativa",
    )


@register("political_agenda.PoliticalAgendaEvent")
class PoliticalAgendaEventSite(BaseSite):
    form_class = PoliticalAgendaEventForm
    list_mixins = (WorkflowStateFilterMixin, DropdownFilterMixin)
    list_fields = (
        "title",
        "campaign",
        "event_type",
        "get_state_display:Estado",
        "start_at",
        "end_at",
        "responsible",
    )
    detail_fields = {
        "Evento": (
            ("campaign", "source_request"),
            ("title", "event_type"),
            ("get_state_display", "blocks_candidate_agenda"),
            ("start_at", "end_at"),
        ),
        "Ubicación": (
            ("province", "canton"),
            ("parish", "sector"),
            ("address",),
            ("reference",),
        ),
        "Organización": (
            ("organizer_name", "organizer_phone"),
            ("responsible", "expected_attendees"),
        ),
        "Detalle": (
            ("objective",),
            ("logistics_notes",),
            ("result_notes",),
        ),
    }
    search_params = (
        "title__icontains",
        "organizer_name__icontains",
        "address__icontains",
        "objective__icontains",
    )
    filter_fields = (
        "campaign:Campaña",
        "event_type:Tipo",
        "state:Estado",
        "start_at:Fecha inicio",
        "responsible:Responsable",
    )
