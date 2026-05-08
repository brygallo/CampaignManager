from superadmin.decorators import register

from core.base import BaseSite, DetailMapsMixin, HideEmptyFieldsetsMixin
from core.list_mixins import DropdownFilterMixin, WorkflowStateFilterMixin
from core.map_mixins import MapInitialLocationMixin

from .forms import PoliticalAgendaEventForm, PoliticalAgendaRequestForm
from .models import PoliticalAgendaRequest


class AgendaMapInitialLocationMixin(MapInitialLocationMixin):
    """Prefill tentative coordinates when the create form is opened with map params."""

    coordinate_initial_fields = ("latitude", "longitude")
    map_location_field = "location"


class PrefillEventFromRequestMixin:
    """Prefill the event create form from ``?source_request=<pk>``.

    Only approved requests are honored; otherwise the form opens blank so the
    state guard in ``PoliticalAgendaEvent.validate_agenda_rules`` keeps holding.
    """

    def get_initial(self):
        initial = super().get_initial()
        request_pk = self.request.GET.get("source_request")
        if not request_pk:
            return initial
        try:
            req = PoliticalAgendaRequest.objects.get(pk=request_pk)
        except (PoliticalAgendaRequest.DoesNotExist, ValueError):
            return initial
        if req.state != PoliticalAgendaRequest.workflow.APPROVED:
            return initial
        prefill = {
            "campaign": req.campaign_id,
            "source_request": req.pk,
            "title": req.title,
            "event_type": req.event_type_id,
            "start_at": req.proposed_start_at,
            "end_at": req.proposed_end_at,
            "address": req.address,
            "reference": req.reference,
            "latitude": req.latitude,
            "longitude": req.longitude,
            "organizer_name": req.requester_name,
            "organizer_phone": req.requester_phone,
            "expected_attendees": req.expected_attendees,
            "objective": req.objective,
        }
        for key, value in prefill.items():
            if value not in (None, "") and key not in initial:
                initial[key] = value
        return initial


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
    list_template_name = "political_agenda/politicalagendarequest_list.html"
    detail_template_name = "political_agenda/politicalagendarequest_detail.html"
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
    list_template_name = "political_agenda/politicalagendaevent_list.html"
    list_mixins = (WorkflowStateFilterMixin, DropdownFilterMixin)
    create_mixins = (PrefillEventFromRequestMixin, AgendaMapInitialLocationMixin)
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
