from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from django_fsm import TransitionNotAllowed

from apps.campaigns.models import (
    Campaign,
    Candidate,
    Election,
    PoliticalMovement,
    Position,
)
from apps.political_agenda.models import PoliticalAgendaEvent
from apps.territorial_ads.models import PhysicalAdvertisement
from apps.workflows.exceptions import WorkflowException


class CampaignWorkflowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="campaign_user",
            email="campaign@example.com",
            password="testpass123",
        )
        self.election = Election.objects.create(name="Elección Workflow")
        self.candidate = Candidate.objects.create(full_name="Candidato Workflow")
        self.movement = PoliticalMovement.objects.create(name="Movimiento Workflow")
        self.position = Position.objects.create(name="Alcaldía")
        self.start = timezone.now().replace(microsecond=0) + timedelta(days=1)
        self.end = self.start + timedelta(hours=2)

    def _build_campaign(self, **overrides):
        data = {
            "name": "Campaña test",
            "election": self.election,
            "candidate": self.candidate,
            "movement": self.movement,
            "position": self.position,
            "start_date": (timezone.now() + timedelta(days=1)).date(),
            "end_date": (timezone.now() + timedelta(days=30)).date(),
        }
        data.update(overrides)
        return Campaign.objects.create(**data)

    def test_default_state_is_draft(self):
        campaign = self._build_campaign()
        self.assertEqual(campaign.state, Campaign.workflow.DRAFT)

    def test_activate_moves_draft_to_active(self):
        campaign = self._build_campaign()
        campaign.activate()
        campaign.save()
        self.assertEqual(campaign.state, Campaign.workflow.ACTIVE)

    def test_close_blocked_when_scheduled_event_exists(self):
        campaign = self._build_campaign()
        campaign.activate()
        campaign.save()

        event = PoliticalAgendaEvent(
            campaign=campaign,
            title="Evento bloqueante",
            start_at=self.start,
            end_at=self.end,
            created_by=self.user,
        )
        event.schedule()
        event.save()

        with self.assertRaises(WorkflowException):
            campaign.close()

    def test_close_blocked_when_active_advertisement_exists(self):
        campaign = self._build_campaign()
        campaign.activate()
        campaign.save()

        PhysicalAdvertisement.objects.create(
            campaign=campaign,
            title="Lona activa",
            owner_name="Dueño",
            owner_phone="0999999999",
            address="Av. Principal",
        )

        with self.assertRaises(WorkflowException):
            campaign.close()

    def test_close_succeeds_when_no_active_dependencies(self):
        campaign = self._build_campaign()
        campaign.activate()
        campaign.save()

        campaign.close()
        campaign.save()
        self.assertEqual(campaign.state, Campaign.workflow.CLOSED)

    def test_cancel_blocked_when_active_dependencies(self):
        campaign = self._build_campaign()
        campaign.activate()
        campaign.save()

        PhysicalAdvertisement.objects.create(
            campaign=campaign,
            title="Lona activa",
            owner_name="Dueño",
            owner_phone="0999999999",
            address="Av. Principal",
        )

        with self.assertRaises(WorkflowException):
            campaign.cancel()

    def test_cancel_succeeds_when_clean(self):
        campaign = self._build_campaign()
        campaign.cancel()
        campaign.save()
        self.assertEqual(campaign.state, Campaign.workflow.CANCELED)

    def test_cannot_reactivate_closed_campaign(self):
        campaign = self._build_campaign()
        campaign.activate()
        campaign.save()
        campaign.close()
        campaign.save()

        with self.assertRaises(TransitionNotAllowed):
            campaign.activate()

    def test_transition_requirements_pending_dates_in_draft(self):
        campaign = self._build_campaign(start_date=None, end_date=None)
        req = campaign.transition_requirements
        self.assertIsNotNone(req)
        self.assertEqual(req["pending_count"], 2)

    def test_transition_requirements_ready_when_no_active_dependencies(self):
        campaign = self._build_campaign()
        campaign.activate()
        campaign.save()
        req = campaign.transition_requirements
        self.assertEqual(req["pending_count"], 0)

    def test_transition_requirements_blocks_close_with_dependencies(self):
        campaign = self._build_campaign()
        campaign.activate()
        campaign.save()

        PhysicalAdvertisement.objects.create(
            campaign=campaign,
            title="Lona",
            owner_name="Dueño",
            owner_phone="0999999999",
            address="Av. Test",
        )

        req = campaign.transition_requirements
        self.assertGreater(req["pending_count"], 0)
