"""Tests for multi-type items, per-unit approval sizes and per-unit
installation evidence (photo + GPS + notes)."""
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils.datastructures import MultiValueDict

from apps.field_surveys.tests.factories import AdvertisingTypeFactory
from apps.territorial_ads.forms import (
    ApprovalForm,
    AssignUnitInstallerForm,
    PhysicalAdvertisementItemFormSet,
    UnitInstallForm,
)
from apps.territorial_ads.models import AdvertisingTypeSize
from apps.territorial_ads.tests.factories import PhysicalAdvertisementFactory

# Smallest valid GIF (1x1 transparent pixel) for ImageField validation.
GIF_BYTES = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04"
    b"\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D"
    b"\x01\x00;"
)


def _photo(name="evidence.gif"):
    return SimpleUploadedFile(name, GIF_BYTES, content_type="image/gif")


class ApprovalNewAdvertisementTests(TestCase):
    """Adding brand-new advertisements (type + qty + size + instructions) in
    the approval form."""

    def setUp(self):
        self.valla = AdvertisingTypeFactory(code="VALLA", name="Valla")
        self.banner = AdvertisingTypeFactory(code="BANNER", name="Banner")
        self.banner_grande = AdvertisingTypeSize.objects.create(
            advertisement_type=self.banner, name="Grande", order=0
        )
        self.ad = PhysicalAdvertisementFactory(items=[(self.valla, 1)])
        self.valla_item = self.ad.items.first()

    def test_new_ad_types_exclude_types_already_in_request(self):
        form = ApprovalForm(obj=self.ad)
        type_ids = list(form.new_ad_types.values_list("pk", flat=True))
        self.assertIn(self.banner.pk, type_ids)
        self.assertNotIn(self.valla.pk, type_ids)

    def test_approve_creates_new_advertisement_with_units(self):
        kwargs = {
            f"unit_approved_{self.valla_item.pk}_1": "on",
            f"unit_instructions_{self.valla_item.pk}_1": "Grúa",
            "new_type_0": str(self.banner.pk),
            "new_quantity_0": "2",
            "new_size_0": str(self.banner_grande.pk),
            "new_instructions_0": "Pegar arriba",
        }
        self.ad.approve(user=None, **kwargs)
        self.ad.save()
        banner_item = self.ad.items.get(advertisement_type=self.banner)
        self.assertEqual(banner_item.quantity, 2)
        self.assertEqual(banner_item.units.count(), 2)
        unit = banner_item.units.first()
        self.assertEqual(unit.size, self.banner_grande)
        self.assertEqual(unit.installation_instructions, "Pegar arriba")

    def test_form_valid_with_only_a_new_advertisement(self):
        # Nothing existing approved, but a new advertisement is added.
        data = {
            "new_type_0": str(self.banner.pk),
            "new_quantity_0": "1",
        }
        form = ApprovalForm(obj=self.ad, data=data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_rejects_duplicate_existing_type(self):
        data = {
            f"unit_approved_{self.valla_item.pk}_1": "on",
            f"unit_instructions_{self.valla_item.pk}_1": "Grúa",
            "new_type_0": str(self.valla.pk),
            "new_quantity_0": "1",
        }
        form = ApprovalForm(obj=self.ad, data=data)
        self.assertFalse(form.is_valid())
        self.assertIn(
            "Ese tipo de publicidad ya está en la solicitud.",
            form.non_field_errors(),
        )

    def test_form_rejects_size_not_matching_new_type(self):
        other = AdvertisingTypeFactory(code="OTRO", name="Otro")
        other_size = AdvertisingTypeSize.objects.create(
            advertisement_type=other, name="X", order=0
        )
        data = {
            "new_type_0": str(self.banner.pk),
            "new_quantity_0": "1",
            "new_size_0": str(other_size.pk),
        }
        form = ApprovalForm(obj=self.ad, data=data)
        self.assertFalse(form.is_valid())

    def test_form_rejects_zero_quantity(self):
        data = {
            "new_type_0": str(self.banner.pk),
            "new_quantity_0": "0",
        }
        form = ApprovalForm(obj=self.ad, data=data)
        self.assertFalse(form.is_valid())

    def test_approval_modal_template_renders(self):
        from django.template.loader import render_to_string

        html = render_to_string("workflows/form.html", {"form": ApprovalForm(obj=self.ad)})
        self.assertIn("Aprobar esta publicidad", html)
        self.assertIn("Agregar publicidad", html)
        self.assertIn("new-ad-row-template", html)
        self.assertIn("Tipo de publicidad", html)


class AddAdvertisementToApprovedTests(TestCase):
    """Adding a new advertisement to an already-approved request."""

    def setUp(self):
        self.valla = AdvertisingTypeFactory(code="VALLA", name="Valla")
        self.banner = AdvertisingTypeFactory(code="BANNER", name="Banner")
        self.banner_grande = AdvertisingTypeSize.objects.create(
            advertisement_type=self.banner, name="Grande", order=0
        )
        self.ad = PhysicalAdvertisementFactory(items=[(self.valla, 1)])
        item = self.ad.items.first()
        self.ad.approve(
            user=None,
            **{
                f"unit_approved_{item.pk}_1": "on",
                f"unit_instructions_{item.pk}_1": "x",
            },
        )
        self.ad.save()

    def test_add_advertisement_transition_creates_units(self):
        from apps.territorial_ads.workflows import PhysicalAdUnitWorkflow

        # Same contract as ChangeStateView: raw POST-style kwargs.
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
        self.assertEqual(unit.state, PhysicalAdUnitWorkflow().PENDIENTE)
        self.assertEqual(unit.size, self.banner_grande)
        self.assertEqual(unit.installation_instructions, "arriba")

    def test_form_validates_against_request(self):
        from apps.territorial_ads.forms import AddAdvertisementForm

        form = AddAdvertisementForm(
            obj=self.ad,
            data={"advertisement_type": self.banner.pk, "quantity": 1},
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_rejects_duplicate_existing_type(self):
        from apps.territorial_ads.forms import AddAdvertisementForm

        # Valla is already in the request → not offered / invalid.
        form = AddAdvertisementForm(
            obj=self.ad,
            data={"advertisement_type": self.valla.pk, "quantity": 1},
        )
        self.assertFalse(form.is_valid())

    def test_form_rejects_size_not_matching_type(self):
        from apps.territorial_ads.forms import AddAdvertisementForm

        other = AdvertisingTypeFactory(code="OTRO", name="Otro")
        other_size = AdvertisingTypeSize.objects.create(
            advertisement_type=other, name="X", order=0
        )
        form = AddAdvertisementForm(
            obj=self.ad,
            data={"advertisement_type": self.banner.pk, "quantity": 1, "size": other_size.pk},
        )
        self.assertFalse(form.is_valid())


class PerUnitInstallerAssignmentTests(TestCase):
    """Installer/team is assigned per physical unit."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Permission

        self.valla = AdvertisingTypeFactory(code="VALLA", name="Valla")
        self.ad = PhysicalAdvertisementFactory(items=[(self.valla, 1)])
        item = self.ad.items.first()
        self.ad.approve(
            user=None, **{f"unit_approved_{item.pk}_1": "on"}
        )
        self.ad.save()
        self.unit = item.units.first()
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

    def test_approval_form_builds_instructions_and_sizes_per_unit(self):
        form = ApprovalForm(obj=self.ad)
        instruction_fields = [
            name for name in form.fields if name.startswith("unit_instructions_")
        ]
        # One instructions textarea per physical unit (2 vallas + 3 lonas).
        self.assertEqual(len(instruction_fields), 5)
        # Valla has no size catalog → no size selects; Lona has 3 units.
        size_fields = [name for name in form.fields if name.startswith("item_size_")]
        lona_item = self.ad.items.get(advertisement_type=self.lona)
        self.assertEqual(len(size_fields), 3)
        for number in range(1, 4):
            self.assertIn(f"item_size_{lona_item.pk}_{number}", form.fields)
            self.assertIn(f"unit_instructions_{lona_item.pk}_{number}", form.fields)

    def test_approve_stores_instructions_sizes_and_creates_units(self):
        lona_item = self.ad.items.get(advertisement_type=self.lona)
        valla_item = self.ad.items.get(advertisement_type=self.valla)
        kwargs = {
            f"unit_approved_{lona_item.pk}_1": "on",
            f"unit_approved_{lona_item.pk}_2": "on",
            f"unit_approved_{lona_item.pk}_3": "on",
            f"unit_approved_{valla_item.pk}_1": "on",
            f"unit_approved_{valla_item.pk}_2": "on",
            f"unit_instructions_{lona_item.pk}_1": "Escalera",
            f"unit_instructions_{lona_item.pk}_2": "Andamio",
            f"unit_instructions_{lona_item.pk}_3": "Permiso",
            f"unit_instructions_{valla_item.pk}_1": "Grúa",
            f"unit_instructions_{valla_item.pk}_2": "Grúa",
            f"item_size_{lona_item.pk}_1": self.lona_pared.pk,
            f"item_size_{lona_item.pk}_2": str(self.lona_cuadro.pk),
            f"item_size_{lona_item.pk}_3": self.lona_pared.pk,
        }
        self.ad.approve(user=None, **kwargs)
        self.ad.save()
        self.assertEqual(lona_item.units.count(), 3)
        self.assertEqual(valla_item.units.count(), 2)
        instructions = [
            u.installation_instructions for u in lona_item.units.order_by("unit_number")
        ]
        self.assertEqual(instructions, ["Escalera", "Andamio", "Permiso"])
        sizes = [u.size for u in lona_item.units.order_by("unit_number")]
        self.assertEqual(
            [s.pk for s in sizes],
            [self.lona_pared.pk, self.lona_cuadro.pk, self.lona_pared.pk],
        )
        # Mixed sizes show up in the summary.
        self.assertIn("Lona:", self.ad.items_sizes_summary)
        self.assertIn("Cuadro", self.ad.items_sizes_summary)

    def test_approve_marks_unchecked_units_as_discarded(self):
        from apps.territorial_ads.workflows import PhysicalAdUnitWorkflow

        lona_item = self.ad.items.get(advertisement_type=self.lona)
        valla_item = self.ad.items.get(advertisement_type=self.valla)
        # Approve both vallas but only the first lona; the other two are left
        # unchecked → kept as DESCARTADA (visible, reactivatable) not removed.
        kwargs = {
            f"unit_approved_{valla_item.pk}_1": "on",
            f"unit_approved_{valla_item.pk}_2": "on",
            f"unit_approved_{lona_item.pk}_1": "on",
            f"unit_instructions_{valla_item.pk}_1": "Grúa",
            f"unit_instructions_{valla_item.pk}_2": "Grúa",
            f"unit_instructions_{lona_item.pk}_1": "Escalera",
            f"item_size_{lona_item.pk}_1": self.lona_pared.pk,
        }
        self.ad.approve(user=None, **kwargs)
        self.ad.save()
        wf = PhysicalAdUnitWorkflow()
        self.assertEqual(valla_item.units.count(), 2)
        self.assertEqual(lona_item.units.count(), 3)
        states = dict(lona_item.units.values_list("unit_number", "state"))
        self.assertEqual(states[1], wf.PENDIENTE)
        self.assertEqual(states[2], wf.DESCARTADA)
        self.assertEqual(states[3], wf.DESCARTADA)

    def test_approval_form_invalid_when_nothing_approved(self):
        form = ApprovalForm(obj=self.ad, data={})
        self.assertFalse(form.is_valid())
        self.assertIn(
            "Debes aprobar al menos una publicidad.", form.non_field_errors()
        )

    def test_approval_form_requires_data_only_for_approved_units(self):
        lona_item = self.ad.items.get(advertisement_type=self.lona)
        valla_item = self.ad.items.get(advertisement_type=self.valla)
        # Only valla #1 approved → lona size/instructions must not be required.
        data = {
            f"unit_approved_{valla_item.pk}_1": "on",
            f"unit_instructions_{valla_item.pk}_1": "Grúa",
        }
        form = ApprovalForm(obj=self.ad, data=data)
        self.assertTrue(form.is_valid(), form.errors)

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
        valla_item = self.ad.items.first()
        self.ad.approve(
            user=None,
            **{
                f"unit_approved_{valla_item.pk}_{n}": "on" for n in (1, 2)
            },
        )
        self.ad.save()
        self.ad.assign_installation(user=None)
        self.ad.save()
        self.unit = self.ad.items.first().units.first()

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
