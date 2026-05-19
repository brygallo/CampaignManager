import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.campaigns.models import Campaign, Candidate, Election, PoliticalMovement, Position
from apps.political_agenda.models import AgendaEventType, PoliticalAgendaEvent
from apps.political_agenda.views import (
    PoliticalAgendaCalendarDataView,
    PoliticalAgendaEventPopupView,
    _can_view_private_events,
    _parse_iso,
)


def _make_campaign(name):
    election = Election.objects.create(name=f"E {name}")
    candidate = Candidate.objects.create(full_name=f"C {name}")
    movement = PoliticalMovement.objects.create(name=f"M {name}")
    position = Position.objects.create(name=f"P {name}")
    return Campaign.objects.create(
        name=name,
        election=election,
        candidate=candidate,
        movement=movement,
        position=position,
    )


class PoliticalAgendaViewHelperTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        User = get_user_model()
        self.user = User.objects.create_user(username="pa1", email="pa1@example.com", password="x")
        self.manager = User.objects.create_user(
            username="pa2",
            email="pa2@example.com",
            password="x",
        )
        self.manager.user_permissions.add(
            Permission.objects.get(codename="view_politicalagendaevent")
        )
        self.campaign = _make_campaign("A")
        self.event_type = AgendaEventType.objects.create(code="EV1", name="Evento")

    def test_parse_iso_handles_empty_bare_and_invalid_values(self):
        self.assertIsNone(_parse_iso(""))
        self.assertIsNone(_parse_iso("not-a-date"))
        self.assertIsNotNone(_parse_iso("2026-01-01"))

    def test_can_view_private_events_respects_superuser_and_permission(self):
        self.assertFalse(_can_view_private_events(self.user))
        self.user.is_superuser = True
        self.assertTrue(_can_view_private_events(self.user))

    def test_popup_raises_permission_denied_for_private_event(self):
        self.user.user_permissions.add(Permission.objects.get(codename="view_politicalagendaevent"))
        event = PoliticalAgendaEvent.objects.create(
            campaign=self.campaign,
            title="Privado",
            event_type=self.event_type,
            start_at=timezone.now(),
            end_at=timezone.now() + timedelta(hours=1),
            is_public=False,
            created_by=self.user,
        )
        request = self.factory.get("/")
        request.user = self.user
        request.active_campaign = self.campaign
        with self.assertRaises(PermissionDenied):
            PoliticalAgendaEventPopupView.as_view()(request, pk=event.pk)

    def test_calendar_data_without_campaign_or_dates_can_show_private_events_for_privileged_user(self):
        self.manager.user_permissions.add(
            Permission.objects.get(codename="view_private_politicalagendaevent")
        )
        private_event = PoliticalAgendaEvent.objects.create(
            campaign=self.campaign,
            title="Privado visible",
            event_type=self.event_type,
            start_at=timezone.now(),
            end_at=timezone.now() + timedelta(hours=1),
            is_public=False,
            created_by=self.user,
        )
        request = self.factory.get(reverse("political_agenda:calendar_data"))
        request.user = self.manager
        request.active_campaign = None
        response = PoliticalAgendaCalendarDataView.as_view()(request)
        payload = json.loads(response.content)
        self.assertEqual([row["id"] for row in payload], [private_event.id])

    def test_calendar_data_applies_optional_filters_and_private_visibility(self):
        other_type = AgendaEventType.objects.create(code="EV2", name="Asamblea")
        start = timezone.now()
        end = start + timedelta(hours=1)
        public_event = PoliticalAgendaEvent.objects.create(
            campaign=self.campaign,
            title="Publico",
            event_type=self.event_type,
            responsible=self.manager,
            start_at=start,
            end_at=end,
            state=PoliticalAgendaEvent.workflow.SCHEDULED,
            is_public=True,
            created_by=self.user,
        )
        PoliticalAgendaEvent.objects.create(
            campaign=self.campaign,
            title="Cancelado",
            event_type=self.event_type,
            responsible=self.manager,
            start_at=start,
            end_at=end,
            state=PoliticalAgendaEvent.workflow.CANCELED,
            is_public=True,
            created_by=self.user,
        )
        PoliticalAgendaEvent.objects.create(
            campaign=self.campaign,
            title="Privado",
            event_type=other_type,
            responsible=self.user,
            start_at=start,
            end_at=end,
            state=PoliticalAgendaEvent.workflow.DRAFT,
            is_public=False,
            created_by=self.user,
        )
        request = self.factory.get(
            reverse("political_agenda:calendar_data"),
            {
                "campaign": self.campaign.pk,
                "start": (start - timedelta(days=1)).isoformat(),
                "end": (end + timedelta(days=1)).isoformat(),
                "event_type": self.event_type.pk,
                "responsible": self.manager.pk,
                "state": PoliticalAgendaEvent.workflow.SCHEDULED,
            },
        )
        request.user = self.manager
        request.active_campaign = None
        response = PoliticalAgendaCalendarDataView.as_view()(request)
        payload = response.json() if hasattr(response, "json") else json.loads(response.content)
        self.assertEqual([row["id"] for row in payload], [public_event.id])

    def test_calendar_data_include_canceled_and_popup_success(self):
        start = timezone.now()
        end = start + timedelta(hours=2)
        canceled = PoliticalAgendaEvent.objects.create(
            campaign=self.campaign,
            title="Cancelado visible",
            event_type=self.event_type,
            start_at=start,
            end_at=end,
            state=PoliticalAgendaEvent.workflow.CANCELED,
            is_public=True,
            created_by=self.user,
        )
        request = self.factory.get(
            reverse("political_agenda:calendar_data"),
            {
                "campaign": self.campaign.pk,
                "start": (start - timedelta(days=1)).isoformat(),
                "end": (end + timedelta(days=1)).isoformat(),
                "include_canceled": "1",
            },
        )
        request.user = self.manager
        request.active_campaign = None
        response = PoliticalAgendaCalendarDataView.as_view()(request)
        payload = response.json() if hasattr(response, "json") else json.loads(response.content)
        self.assertEqual([row["id"] for row in payload], [canceled.id])

        popup_request = self.factory.get(
            reverse("political_agenda:calendar_popup", kwargs={"pk": canceled.pk})
        )
        popup_request.user = self.manager
        popup_request.active_campaign = self.campaign
        popup_response = PoliticalAgendaEventPopupView.as_view()(popup_request, pk=canceled.pk)
        popup_payload = popup_response.json() if hasattr(popup_response, "json") else json.loads(
            popup_response.content
        )
        self.assertEqual(popup_payload["title"], canceled.title)
        self.assertIn("html", popup_payload)
