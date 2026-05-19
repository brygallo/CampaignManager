"""Regression tests for active-campaign behavior in agenda special views."""
import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import Http404
from django.test import RequestFactory
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.campaigns.active import SESSION_KEY
from apps.campaigns.models import Campaign, Candidate, Election, PoliticalMovement, Position
from apps.political_agenda.models import AgendaEventType, PoliticalAgendaEvent
from apps.political_agenda.views import (
    PoliticalAgendaCalendarDataView,
    PoliticalAgendaCalendarView,
    PoliticalAgendaEventPopupView,
)


def _make_campaign(name):
    election = Election.objects.create(name=f"Elección {name}")
    candidate = Candidate.objects.create(full_name=f"Candidato {name}")
    movement = PoliticalMovement.objects.create(name=f"Movimiento {name}")
    position = Position.objects.create(name=f"Cargo {name}")
    return Campaign.objects.create(
        name=name,
        election=election,
        candidate=candidate,
        movement=movement,
        position=position,
    )


@override_settings(PUBLIC_SCHEMA_URLCONF="core.urls")
class PoliticalAgendaActiveCampaignViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        User = get_user_model()
        self.user = User.objects.create_user(
            username="agenda-ac",
            email="agenda-ac@example.com",
            password="testpass123",
        )
        view_perm = Permission.objects.get(codename="view_politicalagendaevent")
        self.user.user_permissions.add(view_perm)
        self.client.force_login(self.user)

        self.first_campaign = _make_campaign("Campaña A")
        self.second_campaign = _make_campaign("Campaña B")
        self.event_type, _ = AgendaEventType.objects.get_or_create(
            code="REUNION",
            defaults={
                "name": "Reunión",
                "order": 1,
                "color": "#3e97ff",
                "icon": "people",
            },
        )
        start = timezone.now().replace(microsecond=0) + timedelta(days=1)
        end = start + timedelta(hours=1)
        self.first_event = PoliticalAgendaEvent.objects.create(
            campaign=self.first_campaign,
            title="Evento A",
            event_type=self.event_type,
            start_at=start,
            end_at=end,
            address="Centro",
            latitude="-2.31",
            longitude="-78.12",
            created_by=self.user,
        )
        self.second_event = PoliticalAgendaEvent.objects.create(
            campaign=self.second_campaign,
            title="Evento B",
            event_type=self.event_type,
            start_at=start,
            end_at=end,
            address="Centro",
            latitude="-2.32",
            longitude="-78.13",
            created_by=self.user,
        )
        session = self.client.session
        session[SESSION_KEY] = self.first_campaign.pk
        session.save()

    def _request(self, path, params=None):
        request = self.factory.get(path, data=params or {})
        request.user = self.user
        request.active_campaign = self.first_campaign
        SessionMiddleware(lambda req: None).process_request(request)
        request.session.save()
        return request

    def _feed(self, **params):
        params.setdefault("start", (timezone.now() - timedelta(days=1)).isoformat())
        params.setdefault("end", (timezone.now() + timedelta(days=30)).isoformat())
        request = self._request(reverse("political_agenda:calendar_data"), params)
        return PoliticalAgendaCalendarDataView.as_view()(request)

    def test_feed_falls_back_to_active_campaign(self):
        response = self._feed()
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual({row["id"] for row in payload}, {self.first_event.id})

    def test_feed_explicit_campaign_overrides_active_campaign(self):
        response = self._feed(campaign=self.second_campaign.pk)
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual({row["id"] for row in payload}, {self.second_event.id})

    def test_popup_rejects_event_from_other_campaign(self):
        request = self._request(
            reverse("political_agenda:calendar_popup", kwargs={"pk": self.second_event.pk})
        )
        with self.assertRaises(Http404):
            PoliticalAgendaEventPopupView.as_view()(request, pk=self.second_event.pk)

    def test_calendar_view_marks_active_campaign_as_selected(self):
        request = self._request(reverse("political_agenda:calendar"))
        response = PoliticalAgendaCalendarView.as_view()(request)
        response.render()
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'<option value="{self.first_campaign.pk}" selected>',
            html=False,
        )
