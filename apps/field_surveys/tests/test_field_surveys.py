from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from apps.campaigns.models import Campaign, Candidate, Election, PoliticalMovement, Position
from apps.field_surveys.forms import FieldSurveyQuickForm
from apps.field_surveys.models import (
    AdvertisingType,
    Competitor,
    CompetitorAdvertisingDetection,
    FieldSurvey,
    OwnAdvertisingPlacement,
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
        self.survey = FieldSurvey.objects.create(
            campaign=self.campaign,
            brigadier=self.user,
            latitude=Decimal("-2.170998"),
            longitude=Decimal("-79.922359"),
            created_by=self.user,
        )

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

    def test_own_advertising_requires_photo_and_coordinates(self):
        placement = OwnAdvertisingPlacement(
            field_survey=self.survey,
            advertising_type=AdvertisingType.AFICHE,
            created_by=self.user,
        )

        with self.assertRaises(ValidationError):
            placement.full_clean()

    def test_own_advertising_accepts_photo_and_coordinates(self):
        photo = SimpleUploadedFile("evidence.jpg", b"file-content", content_type="image/jpeg")
        placement = OwnAdvertisingPlacement(
            field_survey=self.survey,
            advertising_type=AdvertisingType.AFICHE,
            photo=photo,
            latitude=Decimal("-2.170998"),
            longitude=Decimal("-79.922359"),
            created_by=self.user,
        )

        placement.full_clean()

    def test_competitor_detection_photo_is_optional(self):
        competitor = Competitor.objects.create(
            campaign=self.campaign,
            list_number="1",
            political_organization="Lista Test",
        )
        detection = CompetitorAdvertisingDetection(
            campaign=self.campaign,
            competitor=competitor,
            brigadier=self.user,
            advertising_type="AFICHE",
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
