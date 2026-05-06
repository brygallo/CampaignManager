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
from apps.territorial_ads.models import PhysicalAdvertisement


class PhysicalAdvertisementWorkflowTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="ads",
            email="ads@example.com",
            password="testpass123",
        )
        election = Election.objects.create(name="Elección Ads")
        candidate = Candidate.objects.create(full_name="Candidato Ads")
        movement = PoliticalMovement.objects.create(name="Movimiento Ads")
        position = Position.objects.create(name="Alcaldía Ads")
        self.campaign = Campaign.objects.create(
            name="Campaña Ads",
            election=election,
            candidate=candidate,
            movement=movement,
            position=position,
            start_date=(timezone.now() + timedelta(days=1)).date(),
            end_date=(timezone.now() + timedelta(days=30)).date(),
        )

    def _build_ad(self, **overrides):
        data = {
            "campaign": self.campaign,
            "owner_name": "Dueño",
            "owner_phone": "0999999999",
            "address": "Av. Principal",
        }
        data.update(overrides)
        return PhysicalAdvertisement.objects.create(**data)

    def test_default_state_is_ofrecida(self):
        ad = self._build_ad()
        self.assertEqual(ad.state, PhysicalAdvertisement.workflow.OFRECIDA)

    def test_code_assigned_after_save(self):
        ad = self._build_ad()
        self.assertTrue(ad.code.startswith("PF-"))

    def test_approve_sets_user_and_timestamp(self):
        ad = self._build_ad()
        ad.approve(user=self.user)
        ad.save()
        self.assertEqual(ad.state, PhysicalAdvertisement.workflow.APROBADA)
        self.assertEqual(ad.approved_by, self.user)
        self.assertIsNotNone(ad.approved_at)

    def test_assign_installation_sets_assignee_and_timestamp(self):
        ad = self._build_ad()
        ad.approve(user=self.user)
        ad.save()
        ad.assign_installation(
            user=self.user,
            assigned_installer=self.user.pk,
            installer_team="",
        )
        ad.save()
        self.assertEqual(ad.state, PhysicalAdvertisement.workflow.PENDIENTE_INSTALACION)
        self.assertEqual(ad.assigned_installer, self.user)
        self.assertIsNotNone(ad.assigned_at)

    def test_mark_installed_records_evidence(self):
        ad = self._build_ad()
        ad.approve(user=self.user)
        ad.save()
        ad.assign_installation(user=self.user, installer_team="Brigada A")
        ad.save()
        ad.mark_installed(
            user=self.user,
            installation_photo=None,
            installed_latitude=-1.234567,
            installed_longitude=-78.123456,
            installation_notes="Pegada en pared sur",
        )
        ad.save()
        self.assertEqual(ad.state, PhysicalAdvertisement.workflow.INSTALADA)
        self.assertEqual(ad.installed_by, self.user)
        self.assertIsNotNone(ad.installed_at)
        self.assertEqual(ad.installation_notes, "Pegada en pared sur")

    def test_report_damage_records_user_and_time(self):
        ad = self._build_ad()
        ad.approve(user=self.user)
        ad.save()
        ad.assign_installation(user=self.user, installer_team="Brigada A")
        ad.save()
        ad.mark_installed(
            user=self.user,
            installed_latitude=-1.0,
            installed_longitude=-78.0,
        )
        ad.save()
        ad.report_damage(user=self.user, damage_notes="Rota por viento")
        ad.save()
        self.assertEqual(ad.state, PhysicalAdvertisement.workflow.DANADA)
        self.assertEqual(ad.damage_reported_by, self.user)
        self.assertIsNotNone(ad.damage_reported_at)

    def test_retire_from_damaged(self):
        ad = self._build_ad()
        ad.approve(user=self.user)
        ad.save()
        ad.assign_installation(user=self.user, installer_team="Brigada A")
        ad.save()
        ad.mark_installed(
            user=self.user,
            installed_latitude=-1.0,
            installed_longitude=-78.0,
        )
        ad.save()
        ad.report_damage(user=self.user, damage_notes="Rota")
        ad.save()
        ad.retire(user=self.user, retirement_notes="Retirada por daño")
        ad.save()
        self.assertEqual(ad.state, PhysicalAdvertisement.workflow.RETIRADA)
        self.assertEqual(ad.retired_by, self.user)
        self.assertIsNotNone(ad.retired_at)

    def test_cannot_skip_states(self):
        ad = self._build_ad()
        with self.assertRaises(TransitionNotAllowed):
            ad.mark_installed(user=self.user)

    def test_transition_requirements_in_aprobada_pending(self):
        ad = self._build_ad()
        ad.approve(user=self.user)
        ad.save()
        req = ad.transition_requirements
        self.assertIsNotNone(req)
        self.assertEqual(req["pending_count"], 1)

    def test_transition_requirements_in_aprobada_ready_after_assignment(self):
        ad = self._build_ad()
        ad.approve(user=self.user)
        ad.save()
        ad.installer_team = "Brigada B"
        req = ad.transition_requirements
        self.assertEqual(req["pending_count"], 0)
