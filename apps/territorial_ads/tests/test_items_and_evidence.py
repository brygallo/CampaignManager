"""Tests for multi-type items, unit materialization, per-publicidad config
(size + instructions) and per-unit installation evidence."""
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils.datastructures import MultiValueDict
from django_fsm import TransitionNotAllowed

from apps.field_surveys.tests.factories import AdvertisingTypeFactory
from apps.territorial_ads.forms import (
    AssignUnitInstallerForm,
    PhysicalAdvertisementItemFormSet,
    UnitConfigForm,
    UnitInstallForm,
)
from apps.territorial_ads.models import AdvertisingTypeSize
from apps.territorial_ads.tests.factories import PhysicalAdvertisementFactory
from apps.territorial_ads.workflows import PhysicalAdUnitWorkflow

# Smallest valid GIF (1x1 transparent pixel) for ImageField validation.
GIF_BYTES = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04"
    b"\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D"
    b"\x01\x00;"
)


def _photo(name="evidence.gif"):
    return SimpleUploadedFile(name, GIF_BYTES, content_type="image/gif")


def _configure_units(ad):
    """Drive each pending unit through the ``configure`` transition so approve()
    is allowed (the approve transition now requires each publicidad decided).
    Leaves every unit in CONFIGURADA."""
    for unit in ad.units:
        if unit.state == unit.workflow.PENDIENTE:
            unit.configure(user=None, installation_instructions="ok")
            unit.save()


class MaterializeUnitsTests(TestCase):
    def setUp(self):
        self.valla = AdvertisingTypeFactory(code="VALLA", name="Valla")
        self.lona = AdvertisingTypeFactory(code="LONA", name="Lona")

    def test_materialize_creates_one_unit_per_quantity(self):
        ad = PhysicalAdvertisementFactory(items=[(self.valla, 2), (self.lona, 3)])
        ad.materialize_units()
        self.assertEqual(ad.total_units, 5)
        self.assertEqual(len(ad.units), 5)
        for unit in ad.units:
            self.assertEqual(unit.state, PhysicalAdUnitWorkflow().PENDIENTE)
            self.assertIsNone(unit.size_id)

    def test_materialize_is_idempotent(self):
        ad = PhysicalAdvertisementFactory(items=[(self.valla, 2)])
        ad.materialize_units()
        ad.materialize_units()
        self.assertEqual(len(ad.units), 2)

    def test_decreasing_quantity_trims_only_unconfigured_pending(self):
        ad = PhysicalAdvertisementFactory(items=[(self.lona, 3)])
        ad.materialize_units()
        item = ad.items.first()
        # Configure unit #3 → it must survive a quantity drop.
        size = AdvertisingTypeSize.objects.create(
            advertisement_type=self.lona, name="Pared", order=0
        )
        unit3 = item.units.get(unit_number=3)
        unit3.configure(user=None, size=size.pk)
        unit3.save()
        item.quantity = 1
        item.save(update_fields=["quantity"])
        ad.materialize_units()
        numbers = set(item.units.values_list("unit_number", flat=True))
        # #2 (unconfigured) trimmed; #1 kept; #3 kept because configured.
        self.assertEqual(numbers, {1, 3})


class ApproveRequirementTests(TestCase):
    """Approve is blocked until every publicidad is configured or discarded."""

    def setUp(self):
        self.lona = AdvertisingTypeFactory(code="LONA", name="Lona")
        self.ad = PhysicalAdvertisementFactory(items=[(self.lona, 2)])
        self.ad.materialize_units()

    def test_transition_requirements_pending_when_unconfigured(self):
        req = self.ad.transition_requirements
        self.assertIsNotNone(req)
        self.assertEqual(req["pending_count"], 1)  # the single "decided" item

    def test_approve_blocked_until_all_decided(self):
        from apps.workflows.exceptions import WorkflowException

        with self.assertRaises(WorkflowException):
            self.ad.approve(user=None)

    def test_approve_allowed_once_configured(self):
        for unit in self.ad.units:
            unit.configure(user=None, installation_instructions="ok")
            unit.save()
        self.ad.approve(user=None)  # no raise
        self.ad.save()
        self.assertEqual(self.ad.state, self.ad.workflow.APROBADA)

    def test_approve_allowed_when_remaining_discarded(self):
        units = list(self.ad.units)
        units[0].configure(user=None, installation_instructions="ok")
        units[0].save()
        units[1].discard(user=None)
        units[1].save()
        self.ad.approve(user=None)  # discarded counts as decided
        self.ad.save()
        self.assertEqual(self.ad.state, self.ad.workflow.APROBADA)


class PerPublicidadConfigTests(TestCase):
    """Configure each publicidad (size + instructions) via UnitConfigForm."""

    def setUp(self):
        self.lona = AdvertisingTypeFactory(code="LONA", name="Lona")
        self.size = AdvertisingTypeSize.objects.create(
            advertisement_type=self.lona, name="Pared", order=0
        )
        self.ad = PhysicalAdvertisementFactory(items=[(self.lona, 1)])
        self.ad.materialize_units()
        self.unit = self.ad.units[0]

    def test_config_form_sets_size_and_instructions(self):
        # UnitConfigForm only validates now; the fields are written by the
        # configure transition (PENDIENTE → CONFIGURADA).
        self.unit.configure(
            user=None, size=self.size.pk, installation_instructions="Escalera"
        )
        self.unit.save()
        unit = type(self.unit).objects.get(pk=self.unit.pk)
        self.assertEqual(unit.size, self.size)
        self.assertEqual(unit.installation_instructions, "Escalera")
        self.assertEqual(unit.state, unit.workflow.CONFIGURADA)

    def test_config_form_size_queryset_is_scoped_to_type(self):
        other = AdvertisingTypeFactory(code="OTRO", name="Otro")
        AdvertisingTypeSize.objects.create(
            advertisement_type=other, name="X", order=0
        )
        form = UnitConfigForm(obj=self.unit)
        self.assertEqual(list(form.fields["size"].queryset), [self.size])

    def test_view_get_returns_form_and_post_saves(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Permission
        from django.test import RequestFactory
        from django.urls import reverse

        from apps.territorial_ads.views import PhysicalAdUnitActionView

        user = get_user_model().objects.create_user(
            username="appr", email="a@b.com", password="x"
        )
        user.user_permissions.add(
            Permission.objects.get(
                codename="approve_physicaladvertisement",
                content_type__app_label="territorial_ads",
            )
        )
        url = reverse(
            "territorial_ads:unit_action",
            kwargs={"pk": self.unit.pk, "name": "configure"},
        )

        get_req = RequestFactory().get(url)
        get_req.user = user
        get_resp = PhysicalAdUnitActionView.as_view()(
            get_req, pk=self.unit.pk, name="configure"
        )
        self.assertEqual(get_resp.status_code, 200)
        self.assertIn(b"create_url", get_resp.content)

        post_req = RequestFactory().post(
            url, {"size": self.size.pk, "installation_instructions": "Andamio"}
        )
        post_req.user = user
        post_resp = PhysicalAdUnitActionView.as_view()(
            post_req, pk=self.unit.pk, name="configure"
        )
        self.assertEqual(post_resp.status_code, 200)
        unit = type(self.unit).objects.get(pk=self.unit.pk)
        self.assertEqual(unit.state, unit.workflow.CONFIGURADA)
        self.assertEqual(unit.installation_instructions, "Andamio")

    def test_view_forbidden_without_permission(self):
        from django.contrib.auth import get_user_model
        from django.test import RequestFactory
        from django.urls import reverse

        from apps.territorial_ads.views import PhysicalAdUnitActionView

        user = get_user_model().objects.create_user(
            username="nobody", email="n@b.com", password="x"
        )
        url = reverse(
            "territorial_ads:unit_action",
            kwargs={"pk": self.unit.pk, "name": "configure"},
        )
        req = RequestFactory().get(url)
        req.user = user
        resp = PhysicalAdUnitActionView.as_view()(
            req, pk=self.unit.pk, name="configure"
        )
        self.assertEqual(resp.status_code, 400)


class AddAdvertisementToApprovedTests(TestCase):
    """Adding a new advertisement to an already-approved request."""

    def setUp(self):
        self.valla = AdvertisingTypeFactory(code="VALLA", name="Valla")
        self.banner = AdvertisingTypeFactory(code="BANNER", name="Banner")
        self.banner_grande = AdvertisingTypeSize.objects.create(
            advertisement_type=self.banner, name="Grande", order=0
        )
        self.ad = PhysicalAdvertisementFactory(items=[(self.valla, 1)])
        self.ad.materialize_units()
        _configure_units(self.ad)
        self.ad.approve(user=None)
        self.ad.save()

    def test_add_advertisement_transition_creates_units(self):
        self.ad.add_advertisement(
            user=None,
            advertisement_type=str(self.banner.pk),
            quantity="2",
            size=str(self.banner_grande.pk),
            instructions="arriba",
        )
        self.ad.save()
        item = self.ad.items.get(advertisement_type=self.banner)
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.units.count(), 2)
        unit = item.units.first()
        # A size was passed, so the new units are born CONFIGURADA.
        self.assertEqual(unit.state, PhysicalAdUnitWorkflow().CONFIGURADA)
        self.assertEqual(unit.size, self.banner_grande)
        self.assertEqual(unit.installation_instructions, "arriba")

    def test_form_validates_against_request(self):
        from apps.territorial_ads.forms import AddAdvertisementForm

        form = AddAdvertisementForm(
            obj=self.ad,
            data={
                "advertisement_type": self.banner.pk,
                "quantity": 1,
                "installer_team": "Brigada",
            },
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_requires_installer_when_request_approved(self):
        from apps.territorial_ads.forms import AddAdvertisementForm

        # The request is already approved, so adding a publicidad must say who
        # installs it (an installer is required before it can move forward).
        form = AddAdvertisementForm(
            obj=self.ad,
            data={"advertisement_type": self.banner.pk, "quantity": 1},
        )
        self.assertFalse(form.is_valid())

    def test_add_advertisement_assigns_installer_to_new_units(self):
        self.ad.add_advertisement(
            user=None,
            advertisement_type=str(self.banner.pk),
            quantity="1",
            size=str(self.banner_grande.pk),
            installer_team="Brigada Externa",
        )
        self.ad.save()
        unit = self.ad.items.get(advertisement_type=self.banner).units.first()
        self.assertEqual(unit.installer_team, "Brigada Externa")
        self.assertIsNotNone(unit.assigned_at)

    def test_add_more_of_existing_type_appends_units(self):
        # Adding a type already in the request appends more units to its item
        # (one item per type) instead of failing — "varias lonas / banners".
        before = self.ad.items.get(advertisement_type=self.valla).units.count()
        self.ad.add_advertisement(
            user=None,
            advertisement_type=str(self.valla.pk),
            quantity="2",
            installer_team="Brigada",
        )
        self.ad.save()
        item = self.ad.items.get(advertisement_type=self.valla)
        self.assertEqual(item.units.count(), before + 2)
        self.assertEqual(item.quantity, before + 2)

    def test_form_rejects_size_not_matching_type(self):
        from apps.territorial_ads.forms import AddAdvertisementForm

        other = AdvertisingTypeFactory(code="OTRO", name="Otro")
        other_size = AdvertisingTypeSize.objects.create(
            advertisement_type=other, name="X", order=0
        )
        form = AddAdvertisementForm(
            obj=self.ad,
            data={
                "advertisement_type": self.banner.pk,
                "quantity": 1,
                "size": other_size.pk,
            },
        )
        self.assertFalse(form.is_valid())


class PerUnitInstallerAssignmentTests(TestCase):
    """Installer/team is assigned per physical unit."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Permission

        self.valla = AdvertisingTypeFactory(code="VALLA", name="Valla")
        self.ad = PhysicalAdvertisementFactory(items=[(self.valla, 1)])
        self.ad.materialize_units()
        _configure_units(self.ad)
        self.ad.approve(user=None)
        self.ad.save()
        self.unit = self.ad.units[0]
        self.installer = get_user_model().objects.create_user(
            username="installer", email="installer@example.com", password="x"
        )
        self.installer.user_permissions.add(
            Permission.objects.get(
                codename="install_physicaladvertisement",
                content_type__app_label="territorial_ads",
            )
        )

    def test_assign_installer_transition_sets_fields(self):
        self.unit.assign_installer(
            user=self.installer, assigned_installer=str(self.installer.pk)
        )
        self.unit.save()
        # Re-fetch (not refresh_from_db: it trips django_fsm's protected guard).
        self.unit = type(self.unit).objects.get(pk=self.unit.pk)
        self.assertEqual(self.unit.assigned_installer, self.installer)
        self.assertEqual(self.unit.assigned_by, self.installer)
        self.assertIsNotNone(self.unit.assigned_at)

    def test_assign_installer_external_team(self):
        self.unit.assign_installer(user=self.installer, installer_team="Brigada Externa")
        self.unit.save()
        self.unit = type(self.unit).objects.get(pk=self.unit.pk)
        self.assertEqual(self.unit.installer_team, "Brigada Externa")
        self.assertIsNone(self.unit.assigned_installer)

    def test_form_requires_installer_or_team(self):
        form = AssignUnitInstallerForm(data={})
        self.assertFalse(form.is_valid())


class PhysicalAdvertisementItemsTests(TestCase):
    def setUp(self):
        self.valla = AdvertisingTypeFactory(code="VALLA", name="Valla")
        self.lona = AdvertisingTypeFactory(code="LONA", name="Lona")
        self.lona_pared = AdvertisingTypeSize.objects.create(
            advertisement_type=self.lona, name="Pared", order=0
        )
        self.lona_cuadro = AdvertisingTypeSize.objects.create(
            advertisement_type=self.lona, name="Cuadro", order=1
        )
        self.ad = PhysicalAdvertisementFactory(
            items=[(self.valla, 2), (self.lona, 3)]
        )

    def test_items_summary_and_total_units(self):
        self.assertEqual(self.ad.total_units, 5)
        self.assertIn("2× Valla", self.ad.items_summary)
        self.assertIn("3× Lona", self.ad.items_summary)

    def test_configured_sizes_show_in_summary(self):
        self.ad.materialize_units()
        lona_item = self.ad.items.get(advertisement_type=self.lona)
        units = list(lona_item.units.order_by("unit_number"))
        units[0].configure(user=None, size=self.lona_pared.pk)
        units[0].save()
        units[1].configure(user=None, size=self.lona_cuadro.pk)
        units[1].save()
        self.assertIn("Lona:", self.ad.items_sizes_summary)
        self.assertIn("Cuadro", self.ad.items_sizes_summary)

    def test_items_formset_requires_at_least_one_row(self):
        data = {
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "1",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-advertisement_type": "",
            "items-0-quantity": "",
        }
        formset = PhysicalAdvertisementItemFormSet(
            data, instance=PhysicalAdvertisementFactory(items=[])
        )
        self.assertFalse(formset.is_valid())


class UnitInstallFormTests(TestCase):
    def setUp(self):
        self.valla = AdvertisingTypeFactory(code="VALLA", name="Valla")
        self.ad = PhysicalAdvertisementFactory(items=[(self.valla, 2)])
        self.ad.materialize_units()
        _configure_units(self.ad)  # → CONFIGURADA
        self.ad.approve(user=None)
        self.ad.save()
        # Sending to installation requires every publicidad to have an installer
        # assigned (→ ASIGNADA) before the request can move to installation.
        for unit in self.ad.units:
            unit.assign_installer(user=None, installer_team="Brigada")
            unit.save()
        self.ad.assign_installation(user=None)
        self.ad.save()
        self.unit = self.ad.units[0]

    def _form(self, photos, data_extra=None):
        data = {
            "latitude": "-2.300000",
            "longitude": "-78.120000",
            "notes": "",
        }
        data.update(data_extra or {})
        files = MultiValueDict({"photo": photos})
        return UnitInstallForm(data, files, obj=self.unit)

    def test_requires_photo(self):
        form = self._form([])
        self.assertFalse(form.is_valid())
        self.assertIn("photo", form.errors)

    def test_requires_coordinates(self):
        form = UnitInstallForm(
            {"notes": ""}, MultiValueDict({"photo": [_photo()]}), obj=self.unit
        )
        self.assertFalse(form.is_valid())
        self.assertIn("location", form.errors)

    def test_valid_with_photo_and_coordinates(self):
        form = self._form([_photo()])
        self.assertTrue(form.is_valid(), form.errors)

    def test_mark_installed_saves_unit_evidence(self):
        self.unit.mark_installed(
            user=None,
            photo=_photo("a.gif"),
            latitude=-2.3,
            longitude=-78.12,
            notes="Pegada en pared sur",
        )
        self.unit.save()
        # NOTE: protected FSM fields break refresh_from_db; re-fetch instead.
        unit = type(self.unit).objects.get(pk=self.unit.pk)
        self.assertEqual(unit.state, unit.workflow.INSTALADA)
        self.assertTrue(unit.photo.name)
        self.assertEqual(unit.notes, "Pegada en pared sur")
        self.assertIsNotNone(unit.installed_at)


class PhysicalAdUnitActionViewTests(TestCase):
    """Generic insoles runner for per-unit workflow transitions."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Permission

        self.lona = AdvertisingTypeFactory(code="LONA", name="Lona")
        self.ad = PhysicalAdvertisementFactory(items=[(self.lona, 1)])
        self.ad.materialize_units()
        self.unit = self.ad.units[0]
        self.user = get_user_model().objects.create_user(
            username="installer", email="i@b.com", password="x"
        )
        self.user.user_permissions.add(
            Permission.objects.get(
                codename="install_physicaladvertisement",
                content_type__app_label="territorial_ads",
            )
        )

    def _get(self, name, user=None):
        from django.test import RequestFactory
        from django.urls import reverse

        from apps.territorial_ads.views import PhysicalAdUnitActionView

        url = reverse("territorial_ads:unit_action", kwargs={"pk": self.unit.pk, "name": name})
        req = RequestFactory().get(url)
        req.user = user or self.user
        return PhysicalAdUnitActionView.as_view()(req, pk=self.unit.pk, name=name)

    def _post(self, name, data=None, user=None):
        from django.test import RequestFactory
        from django.urls import reverse

        from apps.territorial_ads.views import PhysicalAdUnitActionView

        url = reverse("territorial_ads:unit_action", kwargs={"pk": self.unit.pk, "name": name})
        req = RequestFactory().post(url, data or {})
        req.user = user or self.user
        return PhysicalAdUnitActionView.as_view()(req, pk=self.unit.pk, name=name)

    def test_get_form_action_returns_insoles_payload(self):
        # mark_installed is only offered once the publicidad is ASIGNADA and the
        # request has been sent to installation, so drive that sub-flow first.
        self.unit.configure(user=self.user)
        self.unit.save()
        self.ad.approve(user=self.user)
        self.ad.save()
        self.unit = type(self.unit).objects.get(pk=self.unit.pk)
        self.unit.assign_installer(user=self.user, installer_team="Brigada")
        self.unit.save()
        self.ad.assign_installation(user=self.user)
        self.ad.save()
        resp = self._get("mark_installed")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"create_url", resp.content)
        self.assertIn(b"template", resp.content)

    def test_get_confirm_action_without_form(self):
        # Discard first so the no-form "undiscard" (Reactivar) is available.
        self.unit.discard(user=self.user)
        self.unit.save()
        resp = self._get("undiscard")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"create_url", resp.content)

    def test_post_runs_transition(self):
        resp = self._post("discard")
        self.assertEqual(resp.status_code, 200)
        unit = type(self.unit).objects.get(pk=self.unit.pk)
        self.assertEqual(unit.state, unit.workflow.DESCARTADA)

    def test_permission_denied_returns_400(self):
        from django.contrib.auth import get_user_model

        nobody = get_user_model().objects.create_user(
            username="nobody", email="n@b.com", password="x"
        )
        resp = self._get("mark_installed", user=nobody)
        self.assertEqual(resp.status_code, 400)

    def test_unknown_action_returns_400(self):
        resp = self._get("does_not_exist")
        self.assertEqual(resp.status_code, 400)


class InstallationGatingTests(TestCase):
    """assign_installer and mark_installed are gated on the publicidad being
    configured (size) and the parent request being in the right stage."""

    def setUp(self):
        self.lona = AdvertisingTypeFactory(code="LONA", name="Lona")
        self.size = AdvertisingTypeSize.objects.create(
            advertisement_type=self.lona, name="Pared", order=0
        )
        self.ad = PhysicalAdvertisementFactory(items=[(self.lona, 1)])
        self.ad.materialize_units()
        self.unit = self.ad.units[0]

    def _configure(self):
        # Drive the configure transition (PENDIENTE → CONFIGURADA).
        self.unit.configure(user=None, size=self.size.pk)
        self.unit.save()
        self.unit = type(self.unit).objects.get(pk=self.unit.pk)

    def _approve(self):
        self.ad.approve(user=None)
        self.ad.save()

    def _send_to_installation(self):
        # The unit must reach ASIGNADA before the request can move to
        # installation.
        self.unit = type(self.unit).objects.get(pk=self.unit.pk)
        self.unit.assign_installer(user=None, installer_team="Brigada")
        self.unit.save()
        self.ad.assign_installation(user=None)
        self.ad.save()

    def test_send_to_installation_blocked_without_installer(self):
        from apps.workflows.exceptions import WorkflowException

        self._configure()
        self._approve()  # configured + approved, but no installer assigned yet
        with self.assertRaises(WorkflowException):
            self.ad.assign_installation(user=None)

    def test_assign_installer_blocked_when_unit_not_configured(self):
        # A not-configured unit is simply PENDIENTE; assign_installer's
        # source=CONFIGURADA blocks it.
        self.assertFalse(self.unit.is_configured)
        with self.assertRaises(TransitionNotAllowed):
            self.unit.assign_installer(user=None, installer_team="Brigada")

    def test_assign_installer_blocked_until_request_approved(self):
        self._configure()
        self.assertTrue(self.unit.is_configured)
        with self.assertRaises(TransitionNotAllowed):
            self.unit.assign_installer(user=None, installer_team="Brigada")

    def test_assign_installer_allowed_when_configured_and_approved(self):
        self._configure()
        self._approve()
        self.unit = type(self.unit).objects.get(pk=self.unit.pk)
        self.unit.assign_installer(user=None, installer_team="Brigada")
        self.unit.save()
        unit = type(self.unit).objects.get(pk=self.unit.pk)
        self.assertEqual(unit.installer_team, "Brigada")
        self.assertEqual(unit.state, unit.workflow.ASIGNADA)

    def test_mark_installed_blocked_before_sent_to_installation(self):
        self._configure()
        self._approve()
        self.unit = type(self.unit).objects.get(pk=self.unit.pk)
        self.unit.assign_installer(user=None, installer_team="Brigada")  # ASIGNADA
        self.unit.save()
        # Request is APROBADA, not yet PENDIENTE_INSTALACION.
        with self.assertRaises(TransitionNotAllowed):
            self.unit.mark_installed(user=None, latitude=-2.3, longitude=-78.1)

    def test_mark_installed_allowed_when_configured_and_in_installation(self):
        self._configure()
        self._approve()
        self._send_to_installation()
        self.unit = type(self.unit).objects.get(pk=self.unit.pk)
        self.unit.mark_installed(user=None, latitude=-2.3, longitude=-78.1)
        self.unit.save()
        unit = type(self.unit).objects.get(pk=self.unit.pk)
        self.assertEqual(unit.state, unit.workflow.INSTALADA)
