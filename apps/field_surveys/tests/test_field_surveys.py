from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.campaigns.models import Campaign, Candidate, Election, PoliticalMovement, Position
from apps.field_surveys.forms import FieldSurveyQuickForm
from apps.field_surveys.models import (
    AdvertisingType,
    Competitor,
    CompetitorAdvertisingDetection,
    FieldSurvey,
)
from apps.field_surveys.views import fieldsurvey_queryset_for_user
from apps.territorial_ads.models import AdvertisingCostType, PhysicalAdvertisement


class FieldSurveyRulesTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="brigadier",
            email="brigadier@example.com",
            password="testpass123",
        )
        self.other_user = User.objects.create_user(
            username="other",
            email="other@example.com",
            password="testpass123",
        )
        election = Election.objects.create(name="Elección test")
        candidate = Candidate.objects.create(full_name="Candidato Test")
        movement = PoliticalMovement.objects.create(name="Movimiento Test")
        position = Position.objects.create(name="Alcaldía")
        self.campaign = Campaign.objects.create(
            name="Campaña Test",
            election=election,
            candidate=candidate,
            movement=movement,
            position=position,
        )
        self.ad_type, _ = AdvertisingType.objects.get_or_create(
            code="AFICHE", defaults={"name": "Afiche", "icon": "document"}
        )
        self.cost_type, _ = AdvertisingCostType.objects.get_or_create(
            code="GRATUITA", defaults={"name": "Gratuita", "requires_amount": False}
        )
        self.competitor = Competitor.objects.create(
            campaign=self.campaign,
            list_number="1",
            political_organization="Lista Test",
        )
        self.survey = FieldSurvey.objects.create(
            campaign=self.campaign,
            brigadier=self.user,
            latitude=Decimal("-2.170998"),
            longitude=Decimal("-79.922359"),
            created_by=self.user,
        )

    def test_field_survey_autogenerates_code(self):
        self.assertTrue(self.survey.code.startswith("LC-"))
        self.assertEqual(self.survey.code, f"LC-{self.survey.pk:06d}")

    def test_quick_form_allows_empty_person_data_with_required_gps(self):
        form = FieldSurveyQuickForm(
            data={
                "campaign": self.campaign.id,
                "latitude": "-2.170998",
                "longitude": "-79.922359",
                "location_was_manually_adjusted": "False",
                "voters_count": "0",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_quick_form_requires_gps(self):
        form = FieldSurveyQuickForm(
            data={
                "campaign": self.campaign.id,
                "voters_count": "0",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("latitude", form.errors)
        self.assertIn("longitude", form.errors)

    def test_quick_form_offering_advertising_requires_owner_data(self):
        form = FieldSurveyQuickForm(
            data={
                "campaign": self.campaign.id,
                "latitude": "-2.170998",
                "longitude": "-79.922359",
                "location_was_manually_adjusted": "False",
                "voters_count": "0",
                "offer_advertising": "on",
                "offered_advertisement_type": self.ad_type.id,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("offered_owner_name", form.errors)
        self.assertIn("offered_owner_phone", form.errors)

    def test_quick_form_offering_advertising_creates_physical_ad(self):
        form = FieldSurveyQuickForm(
            data={
                "campaign": self.campaign.id,
                "latitude": "-2.170998",
                "longitude": "-79.922359",
                "location_was_manually_adjusted": "False",
                "voters_count": "0",
                "address": "Av. test",
                "offer_advertising": "on",
                "offered_advertisement_type": self.ad_type.id,
                "offered_owner_name": "Sr. Pruebas",
                "offered_owner_phone": "0999999999",
                "offered_cost_type": self.cost_type.id,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        survey = form.save(commit=False)
        survey.brigadier = self.user
        survey.created_by = self.user
        survey.save()
        form.save_m2m()
        form.save_related_records(survey, self.user)

        ad = PhysicalAdvertisement.objects.filter(campaign=self.campaign).order_by("-pk").first()
        self.assertIsNotNone(ad)
        self.assertEqual(ad.owner_name, "Sr. Pruebas")
        self.assertEqual(ad.advertisement_type_id, self.ad_type.id)
        self.assertEqual(ad.state, PhysicalAdvertisement.workflow.OFRECIDA)

    def test_competitor_detection_photo_is_optional(self):
        detection = CompetitorAdvertisingDetection(
            campaign=self.campaign,
            competitor=self.competitor,
            brigadier=self.user,
            advertising_type=self.ad_type,
            latitude=Decimal("-2.170998"),
            longitude=Decimal("-79.922359"),
            created_by=self.user,
        )

        detection.full_clean()

    def test_brigadier_queryset_excludes_other_brigadier_survey(self):
        other_survey = FieldSurvey.objects.create(
            campaign=self.campaign,
            brigadier=self.other_user,
            latitude=Decimal("-2.170998"),
            longitude=Decimal("-79.922359"),
            created_by=self.other_user,
        )

        queryset = fieldsurvey_queryset_for_user(self.user)

        self.assertIn(self.survey, queryset)
        self.assertNotIn(other_survey, queryset)
