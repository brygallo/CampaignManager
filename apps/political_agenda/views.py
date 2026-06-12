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

from apps.campaigns.active import scope_queryset_to_active_campaign
from apps.campaigns.querysets import visible_campaign_choices

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

VIEW_PRIVATE_PERM = "political_agenda.view_private_politicalagendaevent"

# Neutral gray used for private events shown as "Ocupado" to users without
# the view-private permission.
MASKED_EVENT_COLOR = "#7e8299"


def _can_view_private_events(user):
    """User can see private events if staff or holds the explicit permission."""
    return bool(user and user.is_active and (user.is_superuser or user.has_perm(VIEW_PRIVATE_PERM)))


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
        context["page_title"] = "Calendario de agenda"
        context["breadcrumbs"] = [
            ("Inicio", "/"),
            ("Agenda política", None),
            ("Calendario", None),
        ]
        context["campaigns"] = visible_campaign_choices(self.request.user)
        context["selected_campaign_id"] = (
            self.request.GET.get("campaign")
            or (
                str(self.request.active_campaign.pk)
                if getattr(self.request, "active_campaign", None)
                else ""
            )
        )
        context["event_types"] = AgendaEventType.objects.filter(is_active=True).order_by(
            "order", "name"
        )
        context["states"] = PoliticalAgendaEvent.workflow.choices
        User = get_user_model()
        responsibles = User.objects.filter(
            is_active=True, responsible_agenda_events__isnull=False
        )
        if context["selected_campaign_id"]:
            responsibles = responsibles.filter(
                responsible_agenda_events__campaign_id=context["selected_campaign_id"]
            )
        context["responsibles"] = responsibles.distinct().order_by(
            "first_name", "last_name", "username"
        )
        return context


class PoliticalAgendaCalendarDataView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "political_agenda.view_politicalagendaevent"

    def get(self, request, *args, **kwargs):
        queryset = PoliticalAgendaEvent.objects.select_related(
            "campaign", "event_type", "responsible"
        )
        campaign_id = request.GET.get("campaign")
        if not campaign_id and getattr(request, "active_campaign", None):
            campaign_id = str(request.active_campaign.pk)
        if campaign_id:
            queryset = queryset.filter(campaign_id=campaign_id)
        can_view_private = _can_view_private_events(request.user)

        start = _parse_iso(request.GET.get("start"))
        end = _parse_iso(request.GET.get("end"))
        if start and end:
            queryset = queryset.filter(start_at__lt=end, end_at__gt=start)

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
            # Private events stay on the calendar for everyone, but users
            # without the permission only see the slot as "busy" plus the
            # optional reference — never the title, place or details.
            if not event.is_public and not can_view_private:
                title = "Ocupado"
                if event.private_reference:
                    title = f"Ocupado — {event.private_reference}"
                events.append(
                    {
                        "id": event.id,
                        "title": title,
                        "start": event.start_at.isoformat(),
                        "end": event.end_at.isoformat(),
                        "color": MASKED_EVENT_COLOR,
                        "borderColor": MASKED_EVENT_COLOR,
                        "url": "",
                        "extendedProps": {
                            "state": event.state,
                            "state_label": event.get_state_display(),
                            "type_id": None,
                            "type_label": "",
                            "type_icon": "lock",
                            "campaign": "",
                            "address": "",
                            "latitude": None,
                            "longitude": None,
                            "responsible": "",
                            "is_public": False,
                            "is_masked": True,
                            "popup_url": reverse(
                                "political_agenda:calendar_popup",
                                kwargs={"pk": event.id},
                            ),
                        },
                    }
                )
                continue
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
                        "is_public": event.is_public,
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
        queryset = scope_queryset_to_active_campaign(
            PoliticalAgendaEvent.objects.select_related(
                "campaign",
                "event_type",
                "responsible",
                "source_request",
            ),
            request,
        )
        event = get_object_or_404(
            queryset,
            pk=pk,
        )
        if not event.is_public and not _can_view_private_events(request.user):
            # Show a minimal "Ocupado" card: schedule plus the optional
            # reference, with no title, place or organizational details.
            html = render_to_string(
                "political_agenda/_calendar_popup_masked.html",
                {"event": event, "masked_color": MASKED_EVENT_COLOR},
                request=request,
            )
            return JsonResponse(
                {
                    "html": html,
                    "title": "Ocupado",
                    "url": "",
                }
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
