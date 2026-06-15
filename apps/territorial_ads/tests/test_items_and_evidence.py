"""Tests for multi-type items, per-unit approval sizes and per-unit
installation evidence (photo + GPS + notes)."""
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils.datastructures import MultiValueDict

from apps.field_surveys.tests.factories import AdvertisingTypeFactory
from apps.territorial_ads.forms import (
    ApprovalForm,
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

    def test_approval_form_builds_instructions_per_item_and_sizes_per_unit(self):
        form = ApprovalForm(obj=self.ad)
        instruction_fields = [
            name for name in form.fields if name.startswith("item_instructions_")
        ]
        self.assertEqual(len(instruction_fields), 2)
        # Valla has no size catalog → no size selects; Lona has 3 units.
        size_fields = [name for name in form.fields if name.startswith("item_size_")]
        lona_item = self.ad.items.get(advertisement_type=self.lona)
        self.assertEqual(len(size_fields), 3)
        for number in range(1, 4):
            self.assertIn(f"item_size_{lona_item.pk}_{number}", form.fields)

    def test_approve_stores_instructions_sizes_and_creates_units(self):
        lona_item = self.ad.items.get(advertisement_type=self.lona)
        valla_item = self.ad.items.get(advertisement_type=self.valla)
        kwargs = {
            f"item_instructions_{lona_item.pk}": "Escalera",
            f"item_instructions_{valla_item.pk}": "Andamio",
            f"item_size_{lona_item.pk}_1": self.lona_pared.pk,
            f"item_size_{lona_item.pk}_2": str(self.lona_cuadro.pk),
            f"item_size_{lona_item.pk}_3": self.lona_pared.pk,
        }
        self.ad.approve(user=None, **kwargs)
        self.ad.save()
        lona_item.refresh_from_db()
        self.assertEqual(lona_item.installation_instructions, "Escalera")
        self.assertEqual(lona_item.units.count(), 3)
        self.assertEqual(valla_item.units.count(), 2)
        sizes = [u.size for u in lona_item.units.order_by("unit_number")]
        self.assertEqual(
            [s.pk for s in sizes],
            [self.lona_pared.pk, self.lona_cuadro.pk, self.lona_pared.pk],
        )
        # Mixed sizes show up in the summary.
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
        self.ad.approve(user=None)
        self.ad.save()
        self.ad.assign_installation(user=None, installer_team="Brigada")
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
