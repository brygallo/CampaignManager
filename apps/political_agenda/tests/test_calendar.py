"""Tests for the political agenda calendar view + JSON feed."""
import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.campaigns.models import Campaign, Candidate, Election, PoliticalMovement, Position
from apps.political_agenda.models import (
    AgendaEventType,
    PoliticalAgendaEvent,
)


class PoliticalAgendaCalendarFeedTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="cal-user",
            email="cal@example.com",
            password="testpass123",
        )
        view_perm = Permission.objects.get(codename="view_politicalagendaevent")
        self.user.user_permissions.add(view_perm)
        self.client.force_login(self.user)

        election = Election.objects.create(name="Elección Calendar")
        candidate = Candidate.objects.create(full_name="Candidato Calendar")
        movement = PoliticalMovement.objects.create(name="Movimiento Calendar")
        position = Position.objects.create(name="Prefectura Calendar")
        self.campaign = Campaign.objects.create(
            name="Campaña Calendar",
            election=election,
            candidate=candidate,
            movement=movement,
            position=position,
        )
        self.type_reunion = AgendaEventType.objects.create(
            code="REUNION", name="Reunión", order=10, color="#3e97ff", icon="people"
        )
        self.type_mitin = AgendaEventType.objects.create(
            code="MITIN", name="Mitin", order=40, color="#f1416c", icon="flag"
        )
        now = timezone.now().replace(microsecond=0)
        self.start = now + timedelta(days=2)
        self.end = self.start + timedelta(hours=2)
        self.event_reunion = PoliticalAgendaEvent.objects.create(
            campaign=self.campaign,
            title="Reunión de prueba",
            event_type=self.type_reunion,
            start_at=self.start,
            end_at=self.end,
            address="Centro",
            latitude="-2.310000",
            longitude="-78.120000",
            created_by=self.user,
        )
        self.event_mitin = PoliticalAgendaEvent.objects.create(
            campaign=self.campaign,
            title="Mitin de prueba",
            event_type=self.type_mitin,
            start_at=self.start + timedelta(days=3),
            end_at=self.end + timedelta(days=3),
            created_by=self.user,
        )
        self.canceled = PoliticalAgendaEvent.objects.create(
            campaign=self.campaign,
            title="Evento cancelado",
            event_type=self.type_mitin,
            start_at=self.start,
            end_at=self.end,
            state=PoliticalAgendaEvent.workflow.CANCELED,
            created_by=self.user,
        )

    def _feed(self, **params):
        url = reverse("political_agenda:calendar_data")
        rng_start = (self.start - timedelta(days=10)).isoformat()
        rng_end = (self.start + timedelta(days=30)).isoformat()
        params.setdefault("start", rng_start)
        params.setdefault("end", rng_end)
        return self.client.get(url, params)

    def test_feed_excludes_canceled_by_default(self):
        response = self._feed()
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        ids = {entry["id"] for entry in data}
        self.assertIn(self.event_reunion.id, ids)
        self.assertIn(self.event_mitin.id, ids)
        self.assertNotIn(self.canceled.id, ids)

    def test_feed_filters_by_event_type(self):
        data = json.loads(self._feed(event_type=self.type_reunion.id).content)
        ids = {entry["id"] for entry in data}
        self.assertEqual(ids, {self.event_reunion.id})

    def test_feed_uses_event_type_color(self):
        data = json.loads(self._feed(event_type=self.type_mitin.id).content)
        self.assertEqual(data[0]["color"], "#f1416c")

    def test_feed_includes_canceled_when_requested(self):
        data = json.loads(self._feed(include_canceled="1").content)
        ids = {entry["id"] for entry in data}
        self.assertIn(self.canceled.id, ids)

    def test_feed_requires_view_permission(self):
        User = get_user_model()
        unprivileged = User.objects.create_user(
            username="no-perm", email="no@example.com", password="x"
        )
        self.client.force_login(unprivileged)
        response = self._feed()
        self.assertEqual(response.status_code, 403)

    def test_calendar_view_renders(self):
        response = self.client.get(reverse("political_agenda:calendar"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "agenda-calendar")

    def test_popup_view_returns_html(self):
        url = reverse(
            "political_agenda:calendar_popup", kwargs={"pk": self.event_reunion.id}
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertIn("html", payload)
        self.assertIn(self.event_reunion.title, payload["html"])
