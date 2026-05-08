from superadmin.decorators import register

from core.base import BaseSite, DetailMapsMixin, HideEmptyFieldsetsMixin
from core.list_mixins import DropdownFilterMixin, WorkflowStateFilterMixin
from core.map_mixins import MapInitialLocationMixin

from .forms import PoliticalAgendaEventForm, PoliticalAgendaRequestForm


class AgendaMapInitialLocationMixin(MapInitialLocationMixin):
    """Prefill tentative coordinates when the create form is opened with map params."""

    coordinate_initial_fields = ("latitude", "longitude")
    map_location_field = "location"


@register("political_agenda.AgendaEventType")
class AgendaEventTypeSite(BaseSite):
    list_fields = (
        "code",
        "name",
        "order",
        "color",
        "icon",
        "is_active:Activo",
    )
    detail_fields = {
        "Tipo de evento": (
            ("code", "name"),
            ("order", "is_active"),
            ("color", "icon"),
        ),
    }
    search_params = ("code__icontains", "name__icontains")
    filter_fields = ("is_active:Activo",)


@register("political_agenda.PoliticalAgendaRequest")
class PoliticalAgendaRequestSite(BaseSite):
    form_class = PoliticalAgendaRequestForm
    list_template_name = "political_agenda/superadmin_politicalagendarequest_list.html"
    list_mixins = (WorkflowStateFilterMixin, DropdownFilterMixin)
    create_mixins = (AgendaMapInitialLocationMixin,)
    detail_mixins = (HideEmptyFieldsetsMixin, DetailMapsMixin)
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
            ("event_type",),
            ("priority",),
        ),
        "Solicitante": (
            ("requester_name", "requester_phone"),
            ("organization",),
        ),
        "Fecha tentativa": (
            ("proposed_start_at", "proposed_end_at"),
            ("alternative_dates",),
        ),
        "Ubicación tentativa": (
            ("address",),
            ("reference",),
            ("latitude", "longitude"),
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
    detail_maps = (
        {
            "title": "Ubicación tentativa",
            "points": [
                {
                    "label": "Tentativa",
                    "lat": "latitude",
                    "lng": "longitude",
                    "color": "#3e97ff",
                },
            ],
        },
    )


@register("political_agenda.PoliticalAgendaEvent")
class PoliticalAgendaEventSite(BaseSite):
    form_class = PoliticalAgendaEventForm
    list_template_name = "political_agenda/superadmin_politicalagendaevent_list.html"
    list_mixins = (WorkflowStateFilterMixin, DropdownFilterMixin)
    create_mixins = (AgendaMapInitialLocationMixin,)
    detail_mixins = (HideEmptyFieldsetsMixin, DetailMapsMixin)
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
            ("start_at", "end_at"),
        ),
        "Ubicación": (
            ("address",),
            ("reference",),
            ("latitude", "longitude"),
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
    detail_maps = (
        {
            "title": "Ubicación del evento",
            "points": [
                {
                    "label": "Evento",
                    "lat": "latitude",
                    "lng": "longitude",
                    "color": "#50cd89",
                },
            ],
        },
    )
