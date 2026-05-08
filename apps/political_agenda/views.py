"""Calendar view for political agenda events.

Single-page FullCalendar showing one entry per ``PoliticalAgendaEvent``.
Color comes from the ``AgendaEventType`` lookup; border encodes workflow state.
Cancelled events are hidden by default.
"""
from datetime import datetime

from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from django.views import View
from django.views.generic import TemplateView

from apps.campaigns.models import Campaign

from .models import AgendaEventType, PoliticalAgendaEvent


# Border encodes workflow state. Fill comes from AgendaEventType.color, so the
# border has to remain readable on top of any catalog color.
STATE_BORDERS = {
    0: "#9aa0a6",   # CANCELED (hidden by default)
    1: "#3e97ff",   # DRAFT
    2: "#50cd89",   # SCHEDULED
    3: "#ffc700",   # RESCHEDULED
    4: "#7e8299",   # DONE
}


def event_detail_url(pk):
    return reverse("site:political_agenda_politicalagendaevent_", kwargs={"pk": pk})


def _parse_iso(raw):
    if not raw:
        return None
    parsed = parse_datetime(raw)
    if parsed is not None:
        return parsed
    # FullCalendar sometimes sends a bare YYYY-MM-DD.
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


class PoliticalAgendaCalendarView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "political_agenda/calendar.html"
    permission_required = "political_agenda.view_politicalagendaevent"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["campaigns"] = Campaign.objects.filter(is_active=True).order_by("name")
        context["event_types"] = AgendaEventType.objects.filter(is_active=True).order_by(
            "order", "name"
        )
        context["states"] = PoliticalAgendaEvent.workflow.choices
        User = get_user_model()
        context["responsibles"] = (
            User.objects.filter(
                is_active=True, responsible_agenda_events__isnull=False
            )
            .distinct()
            .order_by("first_name", "last_name", "username")
        )
        return context


class PoliticalAgendaCalendarDataView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "political_agenda.view_politicalagendaevent"

    def get(self, request, *args, **kwargs):
        queryset = PoliticalAgendaEvent.objects.select_related(
            "campaign", "event_type", "responsible"
        )

        start = _parse_iso(request.GET.get("start"))
        end = _parse_iso(request.GET.get("end"))
        if start and end:
            queryset = queryset.filter(start_at__lt=end, end_at__gt=start)

        campaign_id = request.GET.get("campaign")
        if campaign_id:
            queryset = queryset.filter(campaign_id=campaign_id)
        event_type_id = request.GET.get("event_type")
        if event_type_id:
            queryset = queryset.filter(event_type_id=event_type_id)
        responsible_id = request.GET.get("responsible")
        if responsible_id:
            queryset = queryset.filter(responsible_id=responsible_id)

        state_param = request.GET.get("state")
        if state_param:
            queryset = queryset.filter(state=state_param)
        else:
            include_canceled = request.GET.get("include_canceled") == "1"
            if not include_canceled:
                queryset = queryset.exclude(state=PoliticalAgendaEvent.workflow.CANCELED)

        events = []
        for event in queryset:
            color = event.event_type.color if event.event_type_id else "#3e97ff"
            border = STATE_BORDERS.get(event.state, color)
            events.append(
                {
                    "id": event.id,
                    "title": event.title,
                    "start": event.start_at.isoformat(),
                    "end": event.end_at.isoformat(),
                    "color": color,
                    "borderColor": border,
                    "url": event_detail_url(event.id),
                    "extendedProps": {
                        "state": event.state,
                        "state_label": event.get_state_display(),
                        "type_id": event.event_type_id,
                        "type_label": event.event_type.name if event.event_type_id else "",
                        "type_icon": event.event_type.icon if event.event_type_id else "calendar-tick",
                        "campaign": event.campaign.name if event.campaign_id else "",
                        "address": event.address or "",
                        "latitude": float(event.latitude) if event.latitude is not None else None,
                        "longitude": float(event.longitude) if event.longitude is not None else None,
                        "responsible": str(event.responsible) if event.responsible_id else "",
                        "popup_url": reverse(
                            "political_agenda:calendar_popup", kwargs={"pk": event.id}
                        ),
                    },
                }
            )
        return JsonResponse(events, safe=False)


class PoliticalAgendaEventPopupView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Render a rich HTML card for a single event, used inside the calendar's modal."""

    permission_required = "political_agenda.view_politicalagendaevent"

    def get(self, request, pk, *args, **kwargs):
        event = get_object_or_404(
            PoliticalAgendaEvent.objects.select_related(
                "campaign",
                "event_type",
                "responsible",
                "source_request",
            ),
            pk=pk,
        )
        color = event.event_type.color if event.event_type_id else "#3e97ff"
        border = STATE_BORDERS.get(event.state, color)
        html = render_to_string(
            "political_agenda/_calendar_popup.html",
            {
                "event": event,
                "type_color": color,
                "state_border": border,
                "type_icon": event.event_type.icon if event.event_type_id else "calendar-tick",
            },
            request=request,
        )
        return JsonResponse(
            {
                "html": html,
                "title": event.title,
                "url": event_detail_url(event.id),
            }
        )
