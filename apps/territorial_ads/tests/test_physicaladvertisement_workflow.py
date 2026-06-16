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
from apps.field_surveys.models import AdvertisingType
from apps.territorial_ads.models import PhysicalAdvertisement


class PhysicalAdvertisementWorkflowTests(TestCase):
    """Request (solicitud) lifecycle + unit aggregation rules."""

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
        self.ad_type = AdvertisingType.objects.create(
            code="LONA",
            name="Lona",
            icon="picture",
        )

    def _build_ad(self, quantity=1, **overrides):
        data = {
            "campaign": self.campaign,
            "owner_name": "Dueño",
            "owner_phone": "0999999999",
            "address": "Av. Principal",
        }
        data.update(overrides)
        ad = PhysicalAdvertisement.objects.create(**data)
        ad.items.create(advertisement_type=self.ad_type, quantity=quantity)
        # Units are materialized at offer time now (the CRUD view does this
        # via MaterializeUnitsMixin; tests build the ad directly).
        ad.materialize_units()
        return ad

    def _approve(self, ad):
        # Approval requires every publicidad decided; drive the configure
        # transition (PENDIENTE → CONFIGURADA) first.
        for unit in ad.units:
            if unit.state == unit.workflow.PENDIENTE:
                unit.configure(user=self.user, installation_instructions="ok")
                unit.save()
        ad.approve(user=self.user)

    def _send_to_installation(self, ad):
        # Every configured publicidad needs an installer (→ ASIGNADA) before the
        # request can move to installation.
        for unit in ad.units:
            if unit.state == unit.workflow.CONFIGURADA:
                unit.assign_installer(user=self.user, installer_team="Brigada")
                unit.save()
        ad.assign_installation(user=self.user)
        ad.save()

    def _install_all_units(self, ad):
        for item in ad.items.all():
            for unit in item.units.all():
                unit.mark_installed(
                    user=self.user, latitude=-2.3, longitude=-78.1, notes="ok"
                )
                unit.save()
        return PhysicalAdvertisement.objects.get(pk=ad.pk)

    def test_default_state_is_ofrecida(self):
        ad = self._build_ad()
        self.assertEqual(ad.state, PhysicalAdvertisement.workflow.OFRECIDA)
        self.assertFalse(ad.is_state_read_only())

    def test_code_assigned_after_save(self):
        ad = self._build_ad()
        self.assertTrue(ad.code.startswith("SOL-"))

    def test_approve_materializes_units(self):
        ad = self._build_ad(quantity=3)
        self._approve(ad)
        ad.save()
        self.assertEqual(ad.state, PhysicalAdvertisement.workflow.APROBADA)
        self.assertTrue(ad.is_state_read_only())
        self.assertEqual(ad.approved_by, self.user)
        self.assertIsNotNone(ad.approved_at)
        self.assertEqual(len(ad.units), 3)
        for unit in ad.units:
            self.assertEqual(
                unit.state, unit.workflow.CONFIGURADA
            )

    def test_assign_installation_moves_request_to_pending(self):
        # Installer/team are assigned per unit now; this transition only moves
        # the request into the installation stage.
        ad = self._build_ad()
        self._approve(ad)
        ad.save()
        self._send_to_installation(ad)
        self.assertEqual(ad.state, PhysicalAdvertisement.workflow.PENDIENTE_INSTALACION)

    def test_installing_last_unit_auto_installs_request(self):
        ad = self._build_ad(quantity=2)
        self._approve(ad)
        ad.save()
        self._send_to_installation(ad)
        units = list(ad.items.first().units.all())
        units[0].mark_installed(user=self.user, latitude=-2.3, longitude=-78.1)
        units[0].save()
        refreshed = PhysicalAdvertisement.objects.get(pk=ad.pk)
        self.assertEqual(
            refreshed.state, PhysicalAdvertisement.workflow.PENDIENTE_INSTALACION
        )
        units[1].mark_installed(user=self.user, latitude=-2.31, longitude=-78.11)
        units[1].save()
        refreshed = PhysicalAdvertisement.objects.get(pk=ad.pk)
        self.assertEqual(refreshed.state, PhysicalAdvertisement.workflow.INSTALADA)
        self.assertIsNotNone(refreshed.installed_at)

    def test_unit_revert_to_pending_reverts_request(self):
        ad = self._build_ad()
        self._approve(ad)
        ad.save()
        self._send_to_installation(ad)
        ad = self._install_all_units(ad)
        self.assertEqual(ad.state, PhysicalAdvertisement.workflow.INSTALADA)
        unit = ad.items.first().units.first()
        unit.revert_to_pending(user=self.user)
        unit.save()
        refreshed = PhysicalAdvertisement.objects.get(pk=ad.pk)
        self.assertEqual(
            refreshed.state, PhysicalAdvertisement.workflow.PENDIENTE_INSTALACION
        )
        self.assertIsNone(unit.photo.name or None)
        self.assertIsNone(unit.latitude)

    def test_request_state_derived_from_unit_retirement(self):
        # Retiring some units keeps the request Instalada; retiring the LAST
        # active unit auto-derives the request to Retirada.
        ad = self._build_ad(quantity=2)
        self._approve(ad)
        ad.save()
        self._send_to_installation(ad)
        ad = self._install_all_units(ad)
        units = list(ad.items.first().units.all())
        units[0].retire(user=self.user)
        units[0].save()
        self.assertEqual(
            PhysicalAdvertisement.objects.get(pk=ad.pk).state,
            PhysicalAdvertisement.workflow.INSTALADA,
        )
        units[1].retire(user=self.user)
        units[1].save()
        refreshed = PhysicalAdvertisement.objects.get(pk=ad.pk)
        self.assertEqual(refreshed.state, PhysicalAdvertisement.workflow.RETIRADA)
        self.assertIsNotNone(refreshed.retired_at)

    def test_retire_all_from_request_retires_units_and_request(self):
        ad = self._build_ad(quantity=2)
        self._approve(ad)
        ad.save()
        self._send_to_installation(ad)
        ad = self._install_all_units(ad)
        ad.retire(user=self.user)
        ad.save()
        # Bulk action retires every unit and the request becomes Retirada.
        refreshed = PhysicalAdvertisement.objects.get(pk=ad.pk)
        self.assertEqual(refreshed.state, PhysicalAdvertisement.workflow.RETIRADA)
        for unit in refreshed.units:
            self.assertEqual(unit.state, unit.workflow.RETIRADA)

    def test_discard_unit_lets_request_complete(self):
        # Request asks for 2 units, only 1 installed, the other discarded
        # ("won't install") → request still reaches Instalada.
        ad = self._build_ad(quantity=2)
        self._approve(ad)
        ad.save()
        self._send_to_installation(ad)
        units = list(ad.items.first().units.all())
        units[0].mark_installed(user=self.user, latitude=-2.3, longitude=-78.1)
        units[0].save()
        self.assertEqual(
            PhysicalAdvertisement.objects.get(pk=ad.pk).state,
            PhysicalAdvertisement.workflow.PENDIENTE_INSTALACION,
        )
        units[1].discard(user=self.user, notes="No se necesitó")
        units[1].save()
        refreshed = PhysicalAdvertisement.objects.get(pk=ad.pk)
        self.assertEqual(refreshed.state, PhysicalAdvertisement.workflow.INSTALADA)
        discarded = ad.items.first().units.get(pk=units[1].pk)
        self.assertEqual(discarded.state, discarded.workflow.DESCARTADA)
        self.assertEqual(discarded.notes, "No se necesitó")

    def test_unit_damage_and_repair_cycle(self):
        ad = self._build_ad()
        self._approve(ad)
        ad.save()
        self._send_to_installation(ad)
        ad = self._install_all_units(ad)
        unit = ad.items.first().units.first()
        unit.report_damage(user=self.user, damage_notes="Rota por viento")
        unit.save()
        self.assertEqual(unit.state, unit.workflow.DANADA)
        self.assertEqual(unit.damage_reported_by, self.user)
        # The request stays INSTALADA: damage is a unit-level affair.
        refreshed = PhysicalAdvertisement.objects.get(pk=ad.pk)
        self.assertEqual(refreshed.state, PhysicalAdvertisement.workflow.INSTALADA)
        unit.mark_repaired(user=self.user)
        unit.save()
        self.assertEqual(unit.state, unit.workflow.INSTALADA)
        # Damage history is kept after repair.
        self.assertEqual(unit.damage_notes, "Rota por viento")

    def test_cannot_skip_states(self):
        ad = self._build_ad()
        with self.assertRaises(TransitionNotAllowed):
            ad.mark_installed(user=self.user)
