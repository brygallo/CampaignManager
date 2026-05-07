from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.campaigns.models import Campaign, Candidate, Election, PoliticalMovement, Position
from apps.field_surveys.forms import CompetitorAdvertisingDetectionForm, FieldSurveyForm
from apps.field_surveys.models import (
    AdvertisingType,
    Competitor,
    CompetitorAdvertisingDetection,
    FieldSurvey,
)
from apps.field_surveys.views import fieldsurvey_queryset_for_user


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

    def test_field_survey_form_allows_empty_person_data_with_required_gps(self):
        form = FieldSurveyForm(
            data={
                "campaign": self.campaign.id,
                "latitude": "-2.170998",
                "longitude": "-79.922359",
                "location_was_manually_adjusted": "False",
                "voters_count": "0",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_field_survey_form_requires_gps(self):
        form = FieldSurveyForm(
            data={
                "campaign": self.campaign.id,
                "voters_count": "0",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("latitude", form.errors)
        self.assertIn("longitude", form.errors)

    def test_competitor_detection_form_requires_gps(self):
        form = CompetitorAdvertisingDetectionForm(
            data={
                "campaign": self.campaign.id,
                "competitor": self.competitor.id,
                "advertising_type": self.ad_type.id,
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("latitude", form.errors)
        self.assertIn("longitude", form.errors)

    def test_competitor_detection_form_rejects_competitor_from_other_campaign(self):
        other_candidate = Candidate.objects.create(full_name="Otro Candidato")
        other_position = Position.objects.create(name="Prefectura")
        other_campaign = Campaign.objects.create(
            name="Otra campaña",
            election=self.campaign.election,
            candidate=other_candidate,
            movement=self.campaign.movement,
            position=other_position,
        )
        other_competitor = Competitor.objects.create(
            campaign=other_campaign,
            list_number="2",
            political_organization="Lista Externa",
        )
        form = CompetitorAdvertisingDetectionForm(
            data={
                "campaign": self.campaign.id,
                "competitor": other_competitor.id,
                "advertising_type": self.ad_type.id,
                "latitude": "-2.170998",
                "longitude": "-79.922359",
                "location_was_manually_adjusted": "False",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("competitor", form.errors)

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
