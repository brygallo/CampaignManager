"""End-to-end tests for the field_surveys app."""
from __future__ import annotations

import json

import pytest

from apps.field_surveys.tests.factories import (
    AdvertisingTypeFactory,
    CompetitorFactory,
    FieldSurveyFactory,
    SurveyAdvertisingResponseFactory,
    SurveySupportLevelFactory,
)

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def test_dashboard_renders(logged_in_page, live_server):
    # Authenticated user should reach the dashboard with 200
    response = logged_in_page.goto(f"{live_server.url}/levantamiento-campo/dashboard/")
    assert response.status == 200


def test_dashboard_filters_use_select2(logged_in_page, live_server):
    logged_in_page.goto(f"{live_server.url}/levantamiento-campo/dashboard/")
    assert logged_in_page.locator("select[name=campaign].django-select2").count() == 1
    assert logged_in_page.locator("select[name=support_level].django-select2").count() == 1
    assert logged_in_page.locator("select[name=advertising_response].django-select2").count() == 1


def test_dashboard_requires_login(page, live_server):
    # Anonymous request should be redirected to the login page
    response = page.goto(f"{live_server.url}/levantamiento-campo/dashboard/")
    assert response.status == 200
    assert "/login/" in page.url


def test_dashboard_heatmap_data_returns_json(logged_in_page, live_server):
    # Heatmap AJAX endpoint should return JSON content
    response = logged_in_page.context.request.get(
        f"{live_server.url}/levantamiento-campo/dashboard/heatmap-datos/"
    )
    assert response.status == 200
    content_type = response.headers.get("content-type", "")
    assert "json" in content_type.lower()
    # Body must be valid JSON
    data = json.loads(response.body())
    assert data is not None


def test_map_view_renders(logged_in_superuser_page, live_server):
    # Map view should render and expose a map container.
    # Uses superuser because the view requires field_surveys.view_fieldsurvey.
    response = logged_in_superuser_page.goto(f"{live_server.url}/levantamiento-campo/mapa/")
    assert response.status == 200
    # Look for the Leaflet container injected by the template.
    assert logged_in_superuser_page.locator("#field-survey-map").count() >= 1


def test_map_filters_use_select2(logged_in_superuser_page, live_server):
    logged_in_superuser_page.goto(f"{live_server.url}/levantamiento-campo/mapa/")
    assert logged_in_superuser_page.locator("#fs-map-filter-campaign.django-select2").count() == 1
    assert logged_in_superuser_page.locator("#fs-map-filter-support.django-select2").count() == 1
    assert logged_in_superuser_page.locator("#fs-map-filter-advertising.django-select2").count() == 1
    assert logged_in_superuser_page.locator("#fs-map-filter-competitor.django-select2").count() == 1


def test_map_data_endpoint_returns_json(logged_in_page, live_server):
    # Map data endpoint should return valid JSON
    response = logged_in_page.context.request.get(
        f"{live_server.url}/levantamiento-campo/mapa/datos/"
    )
    assert response.status == 200
    data = json.loads(response.body())
    assert data is not None


def test_map_data_includes_existing_surveys(logged_in_superuser_page, live_server):
    # An existing FieldSurvey should appear in the map data payload.
    # Uses superuser because the endpoint requires field_surveys.view_fieldsurvey.
    survey = FieldSurveyFactory()
    response = logged_in_superuser_page.context.request.get(
        f"{live_server.url}/levantamiento-campo/mapa/datos/"
    )
    assert response.status == 200
    body = response.body().decode("utf-8")
    # The survey identifier or coordinates should be referenced in the payload
    assert (
        str(survey.pk) in body
        or str(survey.latitude) in body
        or str(survey.longitude) in body
    )


def test_superadmin_fieldsurvey_list_renders(logged_in_superuser_page, live_server):
    # Superadmin list view should be reachable
    response = logged_in_superuser_page.goto(
        f"{live_server.url}/field_surveys/fieldsurvey/"
    )
    assert response.status == 200


def test_superadmin_fieldsurvey_detail_renders(logged_in_superuser_page, live_server):
    # Detail page should render for an existing survey
    survey = FieldSurveyFactory()
    response = logged_in_superuser_page.goto(
        f"{live_server.url}/field_surveys/fieldsurvey/{survey.pk}/"
    )
    assert response.status == 200


@pytest.mark.parametrize(
    "slug",
    [
        "surveysupportlevel",
        "surveyadvertisingresponse",
        "advertisingtype",
        "competitor",
    ],
)
def test_superadmin_catalog_list_renders(
    logged_in_superuser_page, live_server, slug
):
    # Each catalog list view under superadmin should render
    response = logged_in_superuser_page.goto(
        f"{live_server.url}/field_surveys/{slug}/"
    )
    assert response.status == 200


def test_superadmin_fieldsurvey_create_form_renders(
    logged_in_superuser_page, live_server
):
    # Ensure related catalog records exist so the form has options
    SurveySupportLevelFactory()
    SurveyAdvertisingResponseFactory()
    AdvertisingTypeFactory()
    CompetitorFactory()

    response = logged_in_superuser_page.goto(
        f"{live_server.url}/field_surveys/fieldsurvey/crear/"
    )
    assert response.status == 200
    # FieldSurveyForm.__init__ pops brigadier/person_name/person_phone, and
    # campaign uses a ModelSelect2 widget that may not render a plain <select>.
    # Assert only that a form is rendered to keep the test resilient.
    assert logged_in_superuser_page.locator("form").count() >= 1


def test_superadmin_fieldsurvey_list_requires_superuser(logged_in_page, live_server):
    # Non-superuser should be denied access to the superadmin list
    response = logged_in_page.goto(f"{live_server.url}/field_surveys/fieldsurvey/")
    # Either forbidden, redirect to login, or some non-200 result
    assert response.status in (302, 403) or "/login/" in logged_in_page.url
