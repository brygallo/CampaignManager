import json
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.models import Permission
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.campaigns.models import Campaign, Candidate, Election, PoliticalMovement, Position
from apps.field_surveys.models import AdvertisingType
from apps.territorial_ads.models import AdvertisingRefusal, PhysicalAdvertisement
from apps.territorial_ads.views import (
    AdvertisingRefusalCreateView,
    AdvertisingRefusalPopupView,
    PhysicalAdMapDataView,
    PhysicalAdMapPopupView,
)


def _make_campaign(name):
    election = Election.objects.create(name=f"E {name}")
    candidate = Candidate.objects.create(full_name=f"C {name}")
    movement = PoliticalMovement.objects.create(name=f"M {name}")
    position = Position.objects.create(name=f"P {name}")
    return Campaign.objects.create(
        name=name,
        election=election,
        candidate=candidate,
        movement=movement,
        position=position,
        start_date=(timezone.now() + timedelta(days=1)).date(),
        end_date=(timezone.now() + timedelta(days=30)).date(),
    )


class TerritorialAdsViewHelperTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        User = get_user_model()
        self.user = User.objects.create_user(username="ta1", email="ta1@example.com", password="x")
        for codename in ("view_physicaladvertisement", "view_advertisingrefusal", "add_advertisingrefusal"):
            self.user.user_permissions.add(Permission.objects.get(codename=codename))
        self.campaign = _make_campaign("A")
        self.ad_type = AdvertisingType.objects.create(code="T1", name="Tipo", icon="picture")

    def _request(self, path="/", method="get", data=None, active=True):
        request = getattr(self.factory, method)(path, data=data or {})
        request.user = self.user
        request.active_campaign = self.campaign if active else None
        SessionMiddleware(lambda req: None).process_request(request)
        request.session.save()
        return request

    def test_map_popup_and_refusal_popup_success_paths(self):
        ad = PhysicalAdvertisement.objects.create(
            campaign=self.campaign,
            advertisement_type=self.ad_type,
            owner_name="Dueño",
            owner_phone="099",
            address="Dir",
            installed_latitude=Decimal("-2.1"),
            installed_longitude=Decimal("-79.9"),
        )
        request = self._request(reverse("territorial_ads:map_popup", kwargs={"pk": ad.pk}))
        response = PhysicalAdMapPopupView.as_view()(request, pk=ad.pk)
        payload = json.loads(response.content)
        self.assertIn("html", payload)
        self.assertEqual(payload["url"], reverse("site:territorial_ads_physicaladvertisement_", kwargs={"pk": ad.pk}))

        refusal = AdvertisingRefusal.objects.create(
            campaign=self.campaign,
            owner_reference="Casa",
            reason="No",
            latitude=Decimal("-2.2"),
            longitude=Decimal("-79.8"),
            reported_by=self.user,
        )
        request = self._request(reverse("territorial_ads:refusal_popup", kwargs={"pk": refusal.pk}))
        response = AdvertisingRefusalPopupView.as_view()(request, pk=refusal.pk)
        self.assertEqual(json.loads(response.content)["title"], "Casa")

    def test_refusal_create_get_prefills_and_post_invalid_returns_400(self):
        request = self._request(
            reverse("territorial_ads:refusal_create"),
            data={"offered_latitude": "-2.1", "offered_longitude": "-79.9"},
        )
        response = AdvertisingRefusalCreateView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("html", json.loads(response.content))

        bad_request = self._request(
            reverse("territorial_ads:refusal_create"),
            method="post",
            data={"reason": "", "owner_reference": ""},
        )
        bad_response = AdvertisingRefusalCreateView.as_view()(bad_request)
        self.assertEqual(bad_response.status_code, 400)

    def test_refusal_create_get_without_active_campaign_keeps_campaign_unset(self):
        request = self._request(
            reverse("territorial_ads:refusal_create"),
            data={"latitude": "-2.1", "longitude": "-79.9"},
            active=False,
        )
        response = AdvertisingRefusalCreateView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("html", json.loads(response.content))

    def test_map_data_state_filter_excludes_refusals(self):
        ad = PhysicalAdvertisement.objects.create(
            campaign=self.campaign,
            advertisement_type=self.ad_type,
            owner_name="Dueño",
            owner_phone="099",
            address="Dir",
            offered_latitude=Decimal("-2.1"),
            offered_longitude=Decimal("-79.9"),
        )
        AdvertisingRefusal.objects.create(
            campaign=self.campaign,
            owner_reference="Casa",
            reason="No",
            latitude=Decimal("-2.2"),
            longitude=Decimal("-79.8"),
            reported_by=self.user,
        )
        request = self._request(reverse("territorial_ads:map_data"), data={"state": ad.state})
        response = PhysicalAdMapDataView.as_view()(request)
        payload = json.loads(response.content)
        self.assertEqual(len(payload["ads"]), 1)
        self.assertEqual(payload["ads"][0]["marker_kind"], "ad")

    def test_map_data_truncates_and_emits_edit_urls_for_staff(self):
        self.user.user_permissions.add(Permission.objects.get(codename="change_physicaladvertisement"))
        self.user.user_permissions.add(Permission.objects.get(codename="delete_physicaladvertisement"))
        self.user.user_permissions.add(Permission.objects.get(codename="change_advertisingrefusal"))
        self.user.user_permissions.add(Permission.objects.get(codename="delete_advertisingrefusal"))
        ad = PhysicalAdvertisement.objects.create(
            campaign=self.campaign,
            advertisement_type=self.ad_type,
            owner_name="Dueño",
            owner_phone="099",
            address="Dir",
            installed_latitude=Decimal("-2.05"),
            installed_longitude=Decimal("-79.85"),
        )
        refusal = AdvertisingRefusal.objects.create(
            campaign=self.campaign,
            owner_reference="Casa truncada",
            reason="No",
            latitude=Decimal("-2.20"),
            longitude=Decimal("-79.80"),
            reported_by=self.user,
        )
        original = PhysicalAdMapDataView.MAX_POINTS
        PhysicalAdMapDataView.MAX_POINTS = 1
        try:
            request = self._request(reverse("territorial_ads:map_data"))
            response = PhysicalAdMapDataView.as_view()(request)
        finally:
            PhysicalAdMapDataView.MAX_POINTS = original
        payload = json.loads(response.content)
        self.assertTrue(payload["truncated"])
        self.assertEqual(payload["returned"], 1)
        marker = payload["ads"][0]
        self.assertIn(marker["marker_kind"], {"ad", "refusal"})
        if marker["marker_kind"] == "ad":
            self.assertEqual(marker["kind"], "instalada")
            self.assertIn("update_url", marker)
            self.assertIn("delete_url", marker)
        else:
            self.assertEqual(marker["id"], refusal.id)
            self.assertIn("update_url", marker)
            self.assertIn("delete_url", marker)

    def test_map_data_without_campaign_uses_installed_coordinates_and_edit_urls(self):
        self.user.user_permissions.add(Permission.objects.get(codename="change_physicaladvertisement"))
        self.user.user_permissions.add(Permission.objects.get(codename="delete_physicaladvertisement"))
        ad = PhysicalAdvertisement.objects.create(
            campaign=self.campaign,
            advertisement_type=self.ad_type,
            owner_name="Instalada",
            owner_phone="099",
            address="Dir 2",
            offered_latitude=Decimal("-2.10"),
            offered_longitude=Decimal("-79.90"),
            installed_latitude=Decimal("-2.11"),
            installed_longitude=Decimal("-79.91"),
        )
        request = self._request(reverse("territorial_ads:map_data"), active=False)
        response = PhysicalAdMapDataView.as_view()(request)
        payload = json.loads(response.content)
        marker = next(item for item in payload["ads"] if item["id"] == ad.id)
        self.assertEqual(marker["kind"], "instalada")
        self.assertIn("update_url", marker)
        self.assertIn("delete_url", marker)

    def test_map_data_hides_edit_url_outside_initial_state(self):
        self.user.user_permissions.add(Permission.objects.get(codename="change_physicaladvertisement"))
        ad = PhysicalAdvertisement.objects.create(
            campaign=self.campaign,
            advertisement_type=self.ad_type,
            owner_name="Aprobada",
            owner_phone="099",
            address="Dir 4",
            state=PhysicalAdvertisement.workflow.APROBADA,
            offered_latitude=Decimal("-2.13"),
            offered_longitude=Decimal("-79.93"),
        )
        request = self._request(reverse("territorial_ads:map_data"))
        response = PhysicalAdMapDataView.as_view()(request)
        payload = json.loads(response.content)
        marker = next(item for item in payload["ads"] if item["id"] == ad.id)
        self.assertNotIn("update_url", marker)

    def test_map_data_truncation_with_state_filter_skips_refusal_slice_branch(self):
        for idx in range(2):
            PhysicalAdvertisement.objects.create(
                campaign=self.campaign,
                advertisement_type=self.ad_type,
                owner_name=f"Dueño {idx}",
                owner_phone="099",
                address=f"Dir {idx}",
                offered_latitude=Decimal(f"-2.4{idx}"),
                offered_longitude=Decimal(f"-79.7{idx}"),
            )
        original = PhysicalAdMapDataView.MAX_POINTS
        PhysicalAdMapDataView.MAX_POINTS = 1
        try:
            request = self._request(
                reverse("territorial_ads:map_data"),
                data={"state": PhysicalAdvertisement.workflow.OFRECIDA},
                active=False,
            )
            response = PhysicalAdMapDataView.as_view()(request)
        finally:
            PhysicalAdMapDataView.MAX_POINTS = original
        payload = json.loads(response.content)
        self.assertTrue(payload["truncated"])
        self.assertEqual(payload["returned"], 1)

    def test_map_popup_without_coordinates_returns_null_pin(self):
        ad = PhysicalAdvertisement.objects.create(
            campaign=self.campaign,
            advertisement_type=self.ad_type,
            owner_name="Sin pin",
            owner_phone="099",
            address="Dir",
        )
        request = self._request(reverse("territorial_ads:map_popup", kwargs={"pk": ad.pk}))
        response = PhysicalAdMapPopupView.as_view()(request, pk=ad.pk)
        payload = json.loads(response.content)
        self.assertEqual(payload["title"], str(ad))
        self.assertIn("html", payload)

    def test_map_popup_with_offered_coordinates_uses_offered_pin(self):
        ad = PhysicalAdvertisement.objects.create(
            campaign=self.campaign,
            advertisement_type=self.ad_type,
            owner_name="Con oferta",
            owner_phone="099",
            address="Dir 3",
            offered_latitude=Decimal("-2.12"),
            offered_longitude=Decimal("-79.92"),
        )
        request = self._request(reverse("territorial_ads:map_popup", kwargs={"pk": ad.pk}))
        response = PhysicalAdMapPopupView.as_view()(request, pk=ad.pk)
        payload = json.loads(response.content)
        self.assertEqual(payload["title"], ad.code)
        self.assertIn("html", payload)

    def test_refusal_create_without_active_campaign_uses_posted_campaign(self):
        other_campaign = _make_campaign("B")
        request = self._request(
            reverse("territorial_ads:refusal_create"),
            method="post",
            data={
                "campaign": other_campaign.pk,
                "owner_reference": "Casa libre",
                "reason": "No",
                "latitude": "-2.30",
                "longitude": "-79.70",
            },
            active=False,
        )
        response = AdvertisingRefusalCreateView.as_view()(request)
        payload = json.loads(response.content)
        self.assertTrue(payload["ok"])
        refusal = AdvertisingRefusal.objects.get(pk=payload["id"])
        self.assertEqual(refusal.campaign_id, other_campaign.pk)
        self.assertEqual(refusal.reported_by_id, self.user.pk)

    def test_refusal_create_internal_branches_with_missing_campaign_field_and_anonymous_user(self):
        view = AdvertisingRefusalCreateView()
        request = self._request(reverse("territorial_ads:refusal_create"), active=True)
        fake_field = SimpleNamespace(queryset=Campaign.objects.all(), widget=SimpleNamespace())
        fake_form = SimpleNamespace(fields={"campaign": fake_field})
        with patch("apps.territorial_ads.views.AdvertisingRefusalForm", return_value=fake_form):
            bound = view._bind_form(request)
        self.assertIs(bound, fake_form)
        self.assertEqual(fake_field.initial, self.campaign.pk)
        self.assertTrue(fake_field.required)

        fake_form_without_campaign = SimpleNamespace(fields={})
        with patch(
            "apps.territorial_ads.views.AdvertisingRefusalForm",
            return_value=fake_form_without_campaign,
        ):
            self.assertIs(view._bind_form(request), fake_form_without_campaign)

        anonymous_request = self.factory.post(
            reverse("territorial_ads:refusal_create"),
            data={
                "campaign": self.campaign.pk,
                "owner_reference": "Casa anónima",
                "reason": "No",
                "latitude": "-2.33",
                "longitude": "-79.66",
            },
        )
        anonymous_request.user = AnonymousUser()
        anonymous_request.active_campaign = None
        form = SimpleNamespace(
            is_valid=lambda: True,
            save=lambda commit=False: AdvertisingRefusal(
                campaign=self.campaign,
                owner_reference="Casa anónima",
                reason="No",
                latitude=Decimal("-2.33"),
                longitude=Decimal("-79.66"),
            ),
        )
        view.request = anonymous_request
        with patch.object(AdvertisingRefusalCreateView, "_bind_form", return_value=form):
            response = view.post(anonymous_request)
        payload = json.loads(response.content)
        refusal = AdvertisingRefusal.objects.get(pk=payload["id"])
        self.assertIsNone(refusal.reported_by_id)
