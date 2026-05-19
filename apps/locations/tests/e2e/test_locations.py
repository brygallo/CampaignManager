"""End-to-end tests for the locations app."""
from __future__ import annotations

import pytest

from apps.locations.tests.factories import (
    CantonFactory,
    ParishFactory,
    ProvinceFactory,
    SectorFactory,
)

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


# ---------------------------------------------------------------------------
# Province
# ---------------------------------------------------------------------------

def test_province_list_renders(logged_in_superuser_page, live_server):
    # Superadmin list view returns HTML 200 for a superuser.
    response = logged_in_superuser_page.goto(f"{live_server.url}/locations/province/")
    assert response.status == 200


def test_province_create_form_renders(logged_in_superuser_page, live_server):
    # Create page exposes the basic Province fields.
    response = logged_in_superuser_page.goto(
        f"{live_server.url}/locations/province/crear/"
    )
    assert response.status == 200
    assert logged_in_superuser_page.locator("input[name=code]").count() >= 1
    assert logged_in_superuser_page.locator("input[name=name]").count() >= 1


def test_province_detail_renders(logged_in_superuser_page, live_server):
    province = ProvinceFactory(name="Pichincha")
    response = logged_in_superuser_page.goto(
        f"{live_server.url}/locations/province/{province.pk}/"
    )
    assert response.status == 200
    assert "Pichincha" in logged_in_superuser_page.content()


# ---------------------------------------------------------------------------
# Canton
# ---------------------------------------------------------------------------

def test_canton_list_renders(logged_in_superuser_page, live_server):
    response = logged_in_superuser_page.goto(f"{live_server.url}/locations/canton/")
    assert response.status == 200


def test_canton_detail_renders_with_province(logged_in_superuser_page, live_server):
    # Detail view should display the canton name (and implicitly its province).
    canton = CantonFactory(name="Quito")
    response = logged_in_superuser_page.goto(
        f"{live_server.url}/locations/canton/{canton.pk}/"
    )
    assert response.status == 200
    assert "Quito" in logged_in_superuser_page.content()


# ---------------------------------------------------------------------------
# Parish
# ---------------------------------------------------------------------------

def test_parish_list_renders(logged_in_superuser_page, live_server):
    response = logged_in_superuser_page.goto(f"{live_server.url}/locations/parish/")
    assert response.status == 200


def test_parish_detail_renders(logged_in_superuser_page, live_server):
    parish = ParishFactory(name="La Magdalena")
    response = logged_in_superuser_page.goto(
        f"{live_server.url}/locations/parish/{parish.pk}/"
    )
    assert response.status == 200
    assert "La Magdalena" in logged_in_superuser_page.content()


# ---------------------------------------------------------------------------
# Sector
# ---------------------------------------------------------------------------

def test_sector_list_renders(logged_in_superuser_page, live_server):
    response = logged_in_superuser_page.goto(f"{live_server.url}/locations/sector/")
    assert response.status == 200


def test_sector_create_form_renders(logged_in_superuser_page, live_server):
    # Parent parish FK is rendered as a select.
    response = logged_in_superuser_page.goto(
        f"{live_server.url}/locations/sector/crear/"
    )
    assert response.status == 200
    assert logged_in_superuser_page.locator("select[name=parish]").count() >= 1


def test_sector_detail_renders(logged_in_superuser_page, live_server):
    sector = SectorFactory(name="Barrio El Carmen")
    response = logged_in_superuser_page.goto(
        f"{live_server.url}/locations/sector/{sector.pk}/"
    )
    assert response.status == 200
    assert "Barrio El Carmen" in logged_in_superuser_page.content()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def test_locations_require_login(page, live_server):
    # Anonymous traffic is redirected to /login/ by superadmin's auth guards.
    page.goto(f"{live_server.url}/locations/province/")
    assert "/login/" in page.url
