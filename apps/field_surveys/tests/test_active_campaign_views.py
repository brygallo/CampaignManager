"""Regression tests for active-campaign behavior in field-survey special views."""
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from apps.campaigns.active import SESSION_ALL_KEY, SESSION_KEY
from apps.campaigns.models import Campaign, Candidate, Election, PoliticalMovement, Position
from apps.field_surveys.models import (
    AdvertisingType,
    CompetitorAdvertisingDetection,
    Competitor,
    FieldSurvey,
)
from apps.field_surveys.views import (
    FieldSurveyDashboardView,
    FieldSurveyMapDataView,
    FieldSurveyMapView,
)


def _make_campaign(name):
    election = Election.objects.create(name=f"Elección {name}")
    candidate = Candidate.objects.create(full_name=f"Candidato {name}")
    movement = PoliticalMovement.objects.create(name=f"Movimiento {name}")
    position = Position.objects.create(name=f"Cargo {name}")
    return Campaign.objects.create(
        name=name,
        election=election,
        candidate=candidate,
        movement=movement,
        position=position,
    )


@override_settings(PUBLIC_SCHEMA_URLCONF="core.urls")
class FieldSurveyActiveCampaignViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        User = get_user_model()
        self.user = User.objects.create_user(
            username="fs-ac",
            email="fs-ac@example.com",
            password="testpass123",
        )
        for codename in ("view_fieldsurvey",):
            self.user.user_permissions.add(Permission.objects.get(codename=codename))
        self.client.force_login(self.user)

        self.first_campaign = _make_campaign("Campaña A")
        self.second_campaign = _make_campaign("Campaña B")
        self.ad_type = AdvertisingType.objects.create(
            code="VALLA",
            name="Valla",
            icon="picture",
        )

        self.first_survey = FieldSurvey.objects.create(
            campaign=self.first_campaign,
            brigadier=self.user,
            latitude=Decimal("-2.170998"),
            longitude=Decimal("-79.922359"),
            created_by=self.user,
            voters_count=3,
        )
        self.second_survey = FieldSurvey.objects.create(
            campaign=self.second_campaign,
            brigadier=self.user,
            latitude=Decimal("-2.171998"),
            longitude=Decimal("-79.923359"),
            created_by=self.user,
            voters_count=5,
        )
        self.first_competitor = Competitor.objects.create(
            campaign=self.first_campaign,
            list_number="1",
            political_organization="Lista A",
        )
        self.second_competitor = Competitor.objects.create(
            campaign=self.second_campaign,
            list_number="2",
            political_organization="Lista B",
        )
        self.first_detection = CompetitorAdvertisingDetection.objects.create(
            campaign=self.first_campaign,
            competitor=self.first_competitor,
            brigadier=self.user,
            advertising_type=self.ad_type,
            latitude=Decimal("-2.175"),
            longitude=Decimal("-79.925"),
            created_by=self.user,
        )
        self.second_detection = CompetitorAdvertisingDetection.objects.create(
            campaign=self.second_campaign,
            competitor=self.second_competitor,
            brigadier=self.user,
            advertising_type=self.ad_type,
            latitude=Decimal("-2.176"),
            longitude=Decimal("-79.926"),
            created_by=self.user,
        )
        session = self.client.session
        session[SESSION_KEY] = self.first_campaign.pk
        session.save()

    def _request(self, path, params=None):
        request = self.factory.get(path, data=params or {})
        request.user = self.user
        request.active_campaign = self.first_campaign
        SessionMiddleware(lambda req: None).process_request(request)
        request.session.save()
        return request

    def test_dashboard_context_uses_active_campaign_fallback(self):
        request = self._request(reverse("field_surveys:dashboard"))
        response = FieldSurveyDashboardView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context_data["metrics"]["total_visits"], 1)
        self.assertEqual(response.context_data["active_campaign_filter_id"], str(self.first_campaign.pk))

    def test_dashboard_explicit_campaign_overrides_active_campaign(self):
        request = self._request(
            reverse("field_surveys:dashboard"),
            {"campaign": self.second_campaign.pk},
        )
        response = FieldSurveyDashboardView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context_data["metrics"]["total_visits"], 1)
        self.assertEqual(response.context_data["active_campaign_filter_id"], str(self.second_campaign.pk))

    def test_map_data_uses_active_campaign_fallback_for_both_layers(self):
        request = self._request(reverse("field_surveys:map_data"))
        response = FieldSurveyMapDataView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual({row["id"] for row in payload["visits"]}, {self.first_survey.id})
        self.assertEqual(
            {row["id"] for row in payload["competitor_ads"]},
            {self.first_detection.id},
        )

    def test_map_data_explicit_campaign_overrides_active_campaign(self):
        request = self._request(
            reverse("field_surveys:map_data"),
            {"campaign": self.second_campaign.pk},
        )
        response = FieldSurveyMapDataView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual({row["id"] for row in payload["visits"]}, {self.second_survey.id})
        self.assertEqual(
            {row["id"] for row in payload["competitor_ads"]},
            {self.second_detection.id},
        )

    def test_map_view_marks_active_campaign_as_selected(self):
        request = self._request(reverse("field_surveys:map"))
        response = FieldSurveyMapView.as_view()(request)
        response.render()
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'<option value="{self.first_campaign.pk}" selected>',
            html=False,
        )

    def test_dashboard_in_all_mode_shows_both_campaigns(self):
        request = self._request(reverse("field_surveys:dashboard"))
        request.active_campaign = None
        request.session.pop(SESSION_KEY, None)
        request.session[SESSION_ALL_KEY] = True
        response = FieldSurveyDashboardView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context_data["metrics"]["total_visits"], 2)
        self.assertEqual(response.context_data["active_campaign_filter_id"], "")
