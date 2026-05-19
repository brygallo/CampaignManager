"""End-to-end tests for the territorial_ads app."""
from __future__ import annotations

import json

import pytest

from apps.territorial_ads.tests.factories import (
    AdvertisingCostTypeFactory,
    AdvertisingRefusalFactory,
    PhysicalAdvertisementFactory,
)

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def test_map_view_renders(logged_in_superuser_page, live_server):
    # Map view should load for an authenticated superuser.
    # The view requires territorial_ads.view_physicaladvertisement.
    response = logged_in_superuser_page.goto(f"{live_server.url}/publicidad-territorial/mapa/")
    assert response.status == 200


def test_map_filters_use_select2(logged_in_superuser_page, live_server):
    logged_in_superuser_page.goto(f"{live_server.url}/publicidad-territorial/mapa/")
    assert logged_in_superuser_page.locator("#pa-map-filter-campaign.django-select2").count() == 1
    assert logged_in_superuser_page.locator("#pa-map-filter-state.django-select2").count() == 1


def test_map_view_requires_login(page, live_server):
    # Anonymous users should be redirected to the login page.
    response = page.goto(f"{live_server.url}/publicidad-territorial/mapa/")
    assert response.status == 200
    assert "/login/" in page.url


def test_map_data_returns_json(logged_in_superuser_page, live_server):
    # Map data endpoint should return JSON payload.
    # Uses superuser because the view requires the view perm.
    response = logged_in_superuser_page.context.request.get(
        f"{live_server.url}/publicidad-territorial/mapa/datos/"
    )
    assert response.status == 200
    data = json.loads(response.body())
    assert isinstance(data, (list, dict))


def test_map_data_includes_existing_ad(logged_in_superuser_page, live_server):
    # Newly created advertisement should appear in the map data feed.
    # Uses superuser because the view requires the view perm.
    ad = PhysicalAdvertisementFactory(address="Av. Test 123")
    response = logged_in_superuser_page.context.request.get(
        f"{live_server.url}/publicidad-territorial/mapa/datos/"
    )
    assert response.status == 200
    body = response.body().decode("utf-8")
    assert str(ad.pk) in body or ad.address in body


def test_ad_popup_renders(logged_in_superuser_page, live_server):
    # Popup view for an existing ad should render with its address.
    # Uses superuser because the view requires the view perm.
    ad = PhysicalAdvertisementFactory(address="Calle Popup 456")
    response = logged_in_superuser_page.goto(
        f"{live_server.url}/publicidad-territorial/mapa/popup/{ad.pk}/"
    )
    assert response.status == 200
    assert ad.address in logged_in_superuser_page.content()


def test_ad_popup_404_for_unknown(logged_in_superuser_page, live_server):
    # Unknown ad pk should return 404.
    # Uses superuser so we hit the 404 branch instead of 403.
    response = logged_in_superuser_page.goto(
        f"{live_server.url}/publicidad-territorial/mapa/popup/999999/"
    )
    assert response.status == 404


def test_refusal_create_get_form_renders(logged_in_superuser_page, live_server):
    # ``AdvertisingRefusalCreateView`` is AJAX-only: GET returns a
    # ``JsonResponse`` whose ``html`` key holds the rendered form fragment.
    # We hit it via the request API rather than page navigation so the
    # response body stays JSON.
    response = logged_in_superuser_page.context.request.get(
        f"{live_server.url}/publicidad-territorial/mapa/rechazo/crear/"
    )
    assert response.status == 200
    payload = json.loads(response.body())
    assert "html" in payload
    # The rendered fragment must include the reason field.
    assert 'name="reason"' in payload["html"]


def test_refusal_popup_renders(logged_in_superuser_page, live_server):
    # Refusal popup should render for an existing refusal.
    # Uses superuser because the view requires the view perm.
    refusal = AdvertisingRefusalFactory()
    response = logged_in_superuser_page.goto(
        f"{live_server.url}/publicidad-territorial/mapa/rechazo/popup/{refusal.pk}/"
    )
    assert response.status == 200


def test_map_ad_detail_modal_renders_lucide_icons(logged_in_superuser_page, live_server):
    ad = PhysicalAdvertisementFactory(address="Av. Modal Iconos 101")

    logged_in_superuser_page.goto(f"{live_server.url}/publicidad-territorial/mapa/")
    logged_in_superuser_page.wait_for_selector(".map-type-pin", timeout=10_000)
    logged_in_superuser_page.locator(".map-type-pin").first.click(force=True)

    modal = logged_in_superuser_page.locator("#physical-ad-modal")
    modal.wait_for(state="visible", timeout=10_000)
    modal.locator("[data-modal-body]").wait_for(timeout=10_000)
    assert ad.address in modal.text_content()
    assert modal.locator("[data-modal-body] svg.lucide").count() >= 1


def test_map_refusal_detail_modal_renders_lucide_icons(logged_in_superuser_page, live_server):
    refusal = AdvertisingRefusalFactory(
        owner_reference="QA-ADS-Refusal-Owner",
        reason="QA-ADS-Refusal-Test - no autoriza publicidad por conviccion religiosa",
    )

    logged_in_superuser_page.goto(f"{live_server.url}/publicidad-territorial/mapa/")
    logged_in_superuser_page.wait_for_selector(".map-type-pin--refusal", timeout=10_000)
    logged_in_superuser_page.locator(".map-type-pin--refusal").first.click(force=True)

    modal = logged_in_superuser_page.locator("#physical-ad-modal")
    modal.wait_for(state="visible", timeout=10_000)
    modal.locator("[data-modal-body]").wait_for(timeout=10_000)
    assert refusal.owner_reference in modal.text_content()
    assert modal.locator("[data-modal-body] svg.lucide").count() >= 1


def test_superadmin_physicaladvertisement_list_renders(logged_in_superuser_page, live_server):
    # Superadmin list view should render.
    response = logged_in_superuser_page.goto(
        f"{live_server.url}/territorial_ads/physicaladvertisement/"
    )
    assert response.status == 200


def test_superadmin_physicaladvertisement_detail_renders(logged_in_superuser_page, live_server):
    # Superadmin detail view should render and contain the address.
    ad = PhysicalAdvertisementFactory(address="Detalle Av. 789")
    response = logged_in_superuser_page.goto(
        f"{live_server.url}/territorial_ads/physicaladvertisement/{ad.pk}/"
    )
    assert response.status == 200
    assert ad.address in logged_in_superuser_page.content()


def test_superadmin_physicaladvertisement_create_form_renders(logged_in_superuser_page, live_server):
    # Superadmin create form should render with owner_name input.
    response = logged_in_superuser_page.goto(
        f"{live_server.url}/territorial_ads/physicaladvertisement/crear/"
    )
    assert response.status == 200
    assert logged_in_superuser_page.locator("input[name=owner_name]").count() >= 1


def test_superadmin_advertisingcosttype_list_renders(logged_in_superuser_page, live_server):
    # Superadmin cost-type catalog list should render with existing entries.
    AdvertisingCostTypeFactory()
    response = logged_in_superuser_page.goto(
        f"{live_server.url}/territorial_ads/advertisingcosttype/"
    )
    assert response.status == 200
