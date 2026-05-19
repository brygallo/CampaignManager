"""Regression tests for active-campaign behavior in territorial-ads special views."""
import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import Http404
from django.test import RequestFactory
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.campaigns.active import SESSION_KEY
from apps.campaigns.models import Campaign, Candidate, Election, PoliticalMovement, Position
from apps.field_surveys.models import AdvertisingType
from apps.territorial_ads.models import AdvertisingRefusal, PhysicalAdvertisement
from apps.territorial_ads.views import (
    AdvertisingRefusalCreateView,
    AdvertisingRefusalPopupView,
    PhysicalAdMapDataView,
    PhysicalAdMapPopupView,
    PhysicalAdMapView,
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
        start_date=(timezone.now() + timedelta(days=1)).date(),
        end_date=(timezone.now() + timedelta(days=30)).date(),
    )


@override_settings(PUBLIC_SCHEMA_URLCONF="core.urls")
class TerritorialAdsActiveCampaignViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        User = get_user_model()
        self.user = User.objects.create_user(
            username="ads-ac",
            email="ads-ac@example.com",
            password="testpass123",
        )
        for codename in (
            "view_physicaladvertisement",
            "view_advertisingrefusal",
            "add_advertisingrefusal",
        ):
            self.user.user_permissions.add(Permission.objects.get(codename=codename))
        self.client.force_login(self.user)

        self.first_campaign = _make_campaign("Campaña A")
        self.second_campaign = _make_campaign("Campaña B")
        self.ad_type = AdvertisingType.objects.create(code="LONA", name="Lona", icon="picture")
        self.first_ad = PhysicalAdvertisement.objects.create(
            campaign=self.first_campaign,
            advertisement_type=self.ad_type,
            owner_name="Dueño A",
            owner_phone="0999999999",
            address="Av. A",
            offered_latitude="-2.31",
            offered_longitude="-78.12",
        )
        self.second_ad = PhysicalAdvertisement.objects.create(
            campaign=self.second_campaign,
            advertisement_type=self.ad_type,
            owner_name="Dueño B",
            owner_phone="0988888888",
            address="Av. B",
            offered_latitude="-2.32",
            offered_longitude="-78.13",
        )
        self.second_refusal = AdvertisingRefusal.objects.create(
            campaign=self.second_campaign,
            owner_reference="Casa B",
            reason="No le interesa",
            latitude="-2.33",
            longitude="-78.14",
            reported_by=self.user,
        )
        session = self.client.session
        session[SESSION_KEY] = self.first_campaign.pk
        session.save()

    def _request(self, path, method="get", data=None):
        request = getattr(self.factory, method)(path, data=data or {})
        request.user = self.user
        request.active_campaign = self.first_campaign
        SessionMiddleware(lambda req: None).process_request(request)
        request.session.save()
        return request

    def test_map_data_falls_back_to_active_campaign(self):
        request = self._request(reverse("territorial_ads:map_data"))
        response = PhysicalAdMapDataView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertEqual({row["id"] for row in payload["ads"]}, {self.first_ad.id})

    def test_map_data_explicit_campaign_overrides_active_campaign(self):
        request = self._request(
            reverse("territorial_ads:map_data"),
            data={"campaign": self.second_campaign.pk},
        )
        response = PhysicalAdMapDataView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        ad_ids = {row["id"] for row in payload["ads"] if row["marker_kind"] == "ad"}
        self.assertEqual(ad_ids, {self.second_ad.id})

    def test_ad_popup_rejects_other_campaign(self):
        request = self._request(
            reverse("territorial_ads:map_popup", kwargs={"pk": self.second_ad.pk})
        )
        with self.assertRaises(Http404):
            PhysicalAdMapPopupView.as_view()(request, pk=self.second_ad.pk)

    def test_refusal_popup_rejects_other_campaign(self):
        request = self._request(
            reverse("territorial_ads:refusal_popup", kwargs={"pk": self.second_refusal.pk})
        )
        with self.assertRaises(Http404):
            AdvertisingRefusalPopupView.as_view()(request, pk=self.second_refusal.pk)

    def test_refusal_create_locks_campaign_to_active(self):
        request = self._request(
            reverse("territorial_ads:refusal_create"),
            method="post",
            data={
                "campaign": self.second_campaign.pk,
                "owner_reference": "Casa X",
                "reason": "Sin permiso",
                "latitude": "-2.35",
                "longitude": "-78.16",
            },
        )
        response = AdvertisingRefusalCreateView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content)
        self.assertTrue(payload["ok"])
        refusal = AdvertisingRefusal.objects.get(pk=payload["id"])
        self.assertEqual(refusal.campaign_id, self.first_campaign.pk)

    def test_map_view_marks_active_campaign_as_selected(self):
        request = self._request(reverse("territorial_ads:map"))
        response = PhysicalAdMapView.as_view()(request)
        response.render()
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'<option value="{self.first_campaign.pk}" selected>',
            html=False,
        )
