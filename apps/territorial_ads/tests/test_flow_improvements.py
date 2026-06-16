"""Tests for flow corrections: un-approve, contact fixes on read-only
states, installer assignment filtering and the direct-install fast track."""
import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.template.loader import render_to_string
from django.urls import reverse
from django_fsm import TransitionNotAllowed

from apps.field_surveys.tests.factories import AdvertisingTypeFactory
from apps.territorial_ads.forms import (
    AssignInstallationForm,
    ContactUpdateForm,
    DirectInstallForm,
    UnitConfigForm,
    installer_users_queryset,
)
from apps.territorial_ads.models import AdvertisingTypeSize, PhysicalAdvertisement
from apps.territorial_ads.tests.factories import PhysicalAdvertisementFactory
from apps.territorial_ads.views import DirectInstallCreateView

# Smallest valid GIF (1x1 transparent pixel) for ImageField validation.
GIF_BYTES = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04"
    b"\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D"
    b"\x01\x00;"
)


def _photo(name="evidence.gif"):
    return SimpleUploadedFile(name, GIF_BYTES, content_type="image/gif")


class MapChoicePermissionsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.User = get_user_model()

    def _render_for(self, username, *codenames):
        user = self.User.objects.create_user(username=username, password="x")
        for codename in codenames:
            user.user_permissions.add(
                Permission.objects.get(
                    codename=codename,
                    content_type__app_label="territorial_ads",
                )
            )
        request = self.factory.get("/")
        request.user = user
        return render_to_string(
            "territorial_ads/_choose_modal_body.html", request=request
        )

    def test_request_option_requires_add_permission(self):
        html = self._render_for("request-user", "add_physicaladvertisement")
        self.assertIn("Ingresar solicitud", html)
        self.assertNotIn("Registrar publicidad", html)
        self.assertNotIn("No quiere publicidad", html)

    def test_direct_option_requires_add_and_install_permissions(self):
        html = self._render_for(
            "installer-user",
            "add_physicaladvertisement",
            "install_physicaladvertisement",
        )
        self.assertIn("Ingresar solicitud", html)
        self.assertIn("Registrar publicidad", html)
        self.assertNotIn("No quiere publicidad", html)

    def test_refusal_option_requires_refusal_add_permission(self):
        html = self._render_for("refusal-user", "add_advertisingrefusal")
        self.assertNotIn("Ingresar solicitud", html)
        self.assertNotIn("Registrar publicidad", html)
        self.assertIn("No quiere publicidad", html)


class CorrectionTransitionsTests(TestCase):
    def setUp(self):
        self.valla = AdvertisingTypeFactory(code="VALLA", name="Valla")
        self.ad = PhysicalAdvertisementFactory(items=[(self.valla, 2)])

    def _approve(self):
        # Units are materialized at offer time; drive the configure transition
        # (PENDIENTE → CONFIGURADA) so the approve requirement (every publicidad
        # decided) is satisfied.
        self.ad.materialize_units()
        for unit in self.ad.units:
            if unit.state == unit.workflow.PENDIENTE:
                unit.configure(user=None, installation_instructions="ok")
                unit.save()
        self.ad.approve(user=None)
        self.ad.save()

    def test_revert_to_offered_keeps_units(self):
        self._approve()
        self.assertEqual(len(self.ad.units), 2)
        self.ad.revert_to_offered(user=None)
        self.ad.save()
        self.assertEqual(self.ad.state, PhysicalAdvertisement.workflow.OFRECIDA)
        self.assertIsNone(self.ad.approved_by)
        self.assertIsNone(self.ad.approved_at)
        # Units persist across the lifecycle now.
        self.assertEqual(len(self.ad.units), 2)
        self.assertFalse(self.ad.is_state_read_only())

    def test_revert_to_offered_only_from_approved(self):
        with self.assertRaises(TransitionNotAllowed):
            self.ad.revert_to_offered(user=None)

    def test_update_contact_info_keeps_state(self):
        self._approve()
        self.ad.update_contact_info(
            user=None,
            owner_name="Nuevo Dueño",
            owner_phone="0988888888",
            reference="Junto a la farmacia",
        )
        self.ad.save()
        refreshed = PhysicalAdvertisement.objects.get(pk=self.ad.pk)
        self.assertEqual(refreshed.state, PhysicalAdvertisement.workflow.APROBADA)
        self.assertEqual(refreshed.owner_name, "Nuevo Dueño")
        self.assertEqual(refreshed.owner_phone, "0988888888")
        self.assertEqual(refreshed.reference, "Junto a la farmacia")

    def test_update_contact_info_not_available_when_offered(self):
        # While OFRECIDA the regular update view applies; the corrective
        # transition only exists for read-only states.
        with self.assertRaises(TransitionNotAllowed):
            self.ad.update_contact_info(user=None, owner_name="X")

    def test_contact_form_prefills_from_object(self):
        form = ContactUpdateForm(obj=self.ad)
        self.assertEqual(form.fields["owner_name"].initial, self.ad.owner_name)
        self.assertEqual(form.fields["owner_phone"].initial, self.ad.owner_phone)

    def test_unit_config_form_requires_size_when_catalog_exists(self):
        size = AdvertisingTypeSize.objects.create(
            advertisement_type=self.valla, name="Grande", order=0
        )
        self.ad.materialize_units()
        unit = self.ad.units[0]
        # UnitConfigForm only validates now (obj= kwarg, no .save()); the
        # configure transition writes the fields.
        form = UnitConfigForm(obj=unit)
        self.assertTrue(form.fields["size"].required)
        self.assertIn(size, form.fields["size"].queryset)
        bound = UnitConfigForm(
            data={"installation_instructions": "Andamio"}, obj=unit
        )
        self.assertFalse(bound.is_valid())
        self.assertIn("size", bound.errors)
        ok = UnitConfigForm(
            data={"size": size.pk, "installation_instructions": "Andamio"},
            obj=unit,
        )
        self.assertTrue(ok.is_valid(), ok.errors)
        # Drive the transition with the validated data.
        unit.configure(user=None, size=size.pk, installation_instructions="Andamio")
        unit.save()
        saved = type(unit).objects.get(pk=unit.pk)
        self.assertEqual(saved.size, size)
        self.assertEqual(saved.installation_instructions, "Andamio")
        self.assertEqual(saved.state, saved.workflow.CONFIGURADA)


class InstallerAssignmentQuerysetTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.with_perm = User.objects.create_user(
            username="installer", email="installer@example.com", password="x"
        )
        self.with_perm.user_permissions.add(
            Permission.objects.get(
                codename="install_physicaladvertisement",
                content_type__app_label="territorial_ads",
            )
        )
        self.without_perm = User.objects.create_user(
            username="clerk", email="clerk@example.com", password="x"
        )

    def test_queryset_only_includes_users_with_install_permission(self):
        usernames = set(installer_users_queryset().values_list("username", flat=True))
        self.assertIn("installer", usernames)
        self.assertNotIn("clerk", usernames)

    def test_assign_form_uses_filtered_queryset(self):
        form = AssignInstallationForm()
        usernames = set(
            form.fields["assigned_installer"].queryset.values_list(
                "username", flat=True
            )
        )
        self.assertIn("installer", usernames)
        self.assertNotIn("clerk", usernames)


class DirectInstallTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        User = get_user_model()
        self.user = User.objects.create_user(
            username="direct", email="direct@example.com", password="x"
        )
        for codename in (
            "add_physicaladvertisement",
            "install_physicaladvertisement",
        ):
            self.user.user_permissions.add(
                Permission.objects.get(
                    codename=codename, content_type__app_label="territorial_ads"
                )
            )
        self.valla = AdvertisingTypeFactory(code="VALLA", name="Valla")
        self.size = AdvertisingTypeSize.objects.create(
            advertisement_type=self.valla, name="Grande", order=0
        )
        # Reuse the factory only to get a campaign conveniently.
        self.campaign = PhysicalAdvertisementFactory(items=[(self.valla, 1)]).campaign

    def _request(self, method="get", data=None):
        url = reverse("territorial_ads:direct_install_create")
        request = getattr(self.factory, method)(url, data=data or {})
        request.user = self.user
        request.active_campaign = None
        return request

    def test_size_must_match_type(self):
        other_type = AdvertisingTypeFactory(code="LONA", name="Lona")
        form = DirectInstallForm(
            {
                "campaign": self.campaign.pk,
                "address": "Av. X",
                "owner_name": "Dueño",
                "owner_phone": "099",
                "advertisement_type": other_type.pk,
                "size": self.size.pk,
                "latitude": "-2.3",
                "longitude": "-78.1",
            },
            {"photo": _photo()},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("size", form.errors)

    def test_post_creates_installed_request_with_unit(self):
        request = self._request(
            method="post",
            data={
                "campaign": self.campaign.pk,
                "address": "Av. Principal 123",
                "reference": "Frente al parque",
                "owner_name": "Dueño Directo",
                "owner_phone": "0990001122",
                "advertisement_type": self.valla.pk,
                "size": self.size.pk,
                "notes": "Colocada hace una semana",
                "latitude": "-2.305",
                "longitude": "-78.115",
            },
        )
        request.FILES["photo"] = _photo()
        response = DirectInstallCreateView.as_view()(request)
        payload = json.loads(response.content)
        self.assertTrue(payload["ok"], payload)
        ad = PhysicalAdvertisement.objects.get(pk=payload["id"])
        self.assertEqual(ad.state, PhysicalAdvertisement.workflow.INSTALADA)
        self.assertEqual(ad.owner_name, "Dueño Directo")
        units = ad.units
        self.assertEqual(len(units), 1)
        unit = units[0]
        self.assertEqual(unit.state, unit.workflow.INSTALADA)
        self.assertEqual(unit.size_id, self.size.pk)
        self.assertTrue(unit.photo.name)
        self.assertEqual(unit.installed_by_id, self.user.pk)
