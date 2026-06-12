"""Tests for multi-type items, per-type approval instructions and
per-unit installation photo validation."""
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils.datastructures import MultiValueDict

from apps.field_surveys.tests.factories import AdvertisingTypeFactory
from apps.territorial_ads.forms import (
    ApprovalForm,
    InstallationEvidenceForm,
    PhysicalAdvertisementItemFormSet,
)
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
        self.ad = PhysicalAdvertisementFactory(
            items=[(self.valla, 2), (self.lona, 3)]
        )

    def test_items_summary_and_total_units(self):
        self.assertEqual(self.ad.total_units, 5)
        self.assertIn("2× Valla", self.ad.items_summary)
        self.assertIn("3× Lona", self.ad.items_summary)

    def test_approval_form_builds_one_field_per_item(self):
        form = ApprovalForm(obj=self.ad)
        item_fields = [
            name for name in form.fields if name.startswith("item_instructions_")
        ]
        self.assertEqual(len(item_fields), 2)
        for field_name in item_fields:
            self.assertTrue(form.fields[field_name].required)

    def test_approve_stores_per_item_instructions(self):
        items = list(self.ad.items.all())
        kwargs = {
            f"item_instructions_{item.pk}": f"Instrucciones {item.pk}"
            for item in items
        }
        self.ad.approve(user=None, **kwargs)
        self.ad.save()
        for item in self.ad.items.all():
            self.assertEqual(item.installation_instructions, f"Instrucciones {item.pk}")

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


class InstallationEvidenceFormTests(TestCase):
    def setUp(self):
        self.valla = AdvertisingTypeFactory(code="VALLA", name="Valla")
        self.ad = PhysicalAdvertisementFactory(items=[(self.valla, 2)])

    def _form(self, photos):
        data = {
            "installed_latitude": "-2.300000",
            "installed_longitude": "-78.120000",
            "installation_notes": "",
        }
        files = MultiValueDict({"installation_photos": photos})
        return InstallationEvidenceForm(data, files, obj=self.ad)

    def test_rejects_fewer_photos_than_units(self):
        form = self._form([_photo("a.gif")])
        self.assertFalse(form.is_valid())
        self.assertIn("installation_photos", form.errors)

    def test_accepts_one_photo_per_unit(self):
        form = self._form([_photo("a.gif"), _photo("b.gif")])
        self.assertTrue(form.is_valid(), form.errors)

    def test_mark_installed_creates_one_record_per_photo(self):
        self.ad.approve(
            user=None,
            **{
                f"item_instructions_{item.pk}": "Escalera"
                for item in self.ad.items.all()
            },
        )
        self.ad.save()
        self.ad.assign_installation(user=None, installer_team="Brigada")
        self.ad.save()
        self.ad.mark_installed(
            user=None,
            installation_photos=[_photo("a.gif"), _photo("b.gif")],
            installed_latitude=-2.3,
            installed_longitude=-78.12,
        )
        self.ad.save()
        self.assertEqual(self.ad.installation_photos.count(), 2)
        self.ad.revert_to_pending(user=None)
        self.ad.save()
        self.assertEqual(self.ad.installation_photos.count(), 0)
