from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.campaigns.models import Campaign, Candidate, Election, PoliticalMovement, Position
from apps.political_agenda.forms import PoliticalAgendaEventForm, PoliticalAgendaRequestForm
from apps.political_agenda.models import PoliticalAgendaEvent, PoliticalAgendaRequest


class PoliticalAgendaRulesTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="agenda",
            email="agenda@example.com",
            password="testpass123",
        )
        election = Election.objects.create(name="Elección agenda")
        self.candidate = Candidate.objects.create(full_name="Candidato Agenda")
        movement = PoliticalMovement.objects.create(name="Movimiento Agenda")
        position = Position.objects.create(name="Prefectura")
        self.campaign = Campaign.objects.create(
            name="Campaña Agenda",
            election=election,
            candidate=self.candidate,
            movement=movement,
            position=position,
        )
        self.start = timezone.now().replace(microsecond=0) + timedelta(days=1)
        self.end = self.start + timedelta(hours=2)

    def test_request_never_blocks_candidate_agenda(self):
        request = PoliticalAgendaRequest.objects.create(
            campaign=self.campaign,
            title="Solicitud tentativa",
            requester_name="Dirigente barrial",
            proposed_start_at=self.start,
            proposed_end_at=self.end,
            created_by=self.user,
        )

        self.assertFalse(request.blocks_candidate_agenda)

    def test_draft_event_does_not_block_candidate_agenda(self):
        event = PoliticalAgendaEvent.objects.create(
            campaign=self.campaign,
            title="Evento borrador",
            start_at=self.start,
            end_at=self.end,
            created_by=self.user,
        )

        self.assertFalse(event.blocks_candidate_agenda)

    def test_scheduled_event_blocks_candidate_agenda(self):
        event = PoliticalAgendaEvent(
            campaign=self.campaign,
            title="Evento agendado",
            start_at=self.start,
            end_at=self.end,
            created_by=self.user,
        )
        event.schedule()
        event.save()

        self.assertTrue(event.blocks_candidate_agenda)

    def test_scheduled_event_rejects_overlap_for_same_candidate(self):
        scheduled = PoliticalAgendaEvent(
            campaign=self.campaign,
            title="Evento agendado",
            start_at=self.start,
            end_at=self.end,
            created_by=self.user,
        )
        scheduled.schedule()
        scheduled.save()
        overlapping = PoliticalAgendaEvent(
            campaign=self.campaign,
            title="Evento cruzado",
            start_at=self.start + timedelta(minutes=30),
            end_at=self.end + timedelta(hours=1),
            created_by=self.user,
        )

        with self.assertRaises(ValidationError):
            overlapping.schedule()

    def test_event_from_request_requires_approved_request(self):
        request = PoliticalAgendaRequest.objects.create(
            campaign=self.campaign,
            title="Solicitud pendiente",
            requester_name="Dirigente",
            proposed_start_at=self.start,
            proposed_end_at=self.end,
        )
        event = PoliticalAgendaEvent.build_from_request(
            request,
            created_by=self.user,
        )

        with self.assertRaises(ValidationError):
            event.validate_agenda_rules()

    def test_request_location_selects_are_dependent(self):
        form = PoliticalAgendaRequestForm()

        self.assertEqual(
            form.fields["canton"].widget.dependent_fields,
            {"province": "province"},
        )
        self.assertEqual(
            form.fields["parish"].widget.dependent_fields,
            {"canton": "canton"},
        )
        self.assertEqual(
            form.fields["sector"].widget.dependent_fields,
            {"parish": "parish"},
        )

    def test_event_selects_are_dependent(self):
        form = PoliticalAgendaEventForm()

        self.assertEqual(
            form.fields["source_request"].widget.dependent_fields,
            {"campaign": "campaign"},
        )
        self.assertEqual(
            form.fields["canton"].widget.dependent_fields,
            {"province": "province"},
        )
        self.assertEqual(
            form.fields["parish"].widget.dependent_fields,
            {"canton": "canton"},
        )
        self.assertEqual(
            form.fields["sector"].widget.dependent_fields,
            {"parish": "parish"},
        )
