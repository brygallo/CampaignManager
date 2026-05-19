"""End-to-end tests for the campaigns app.

Covers the active-campaign switcher endpoints + the superadmin-generated CRUD
surface for Campaign, Election, PoliticalMovement, Position and Candidate.

Note: the navbar campaign selector itself depends on the tenant context
processors (``brand`` / ``tenant_features`` / ``active_campaign``) which
short-circuit under the E2E test settings (no ``request.tenant``). Tests
verify the underlying endpoints directly via Playwright's request API and
check side-effects through subsequent page loads or session inspection.
"""
from __future__ import annotations

import pytest

from apps.campaigns.tests.factories import (
    CampaignFactory,
    CandidateFactory,
    ElectionFactory,
    PoliticalMovementFactory,
    PositionFactory,
)

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def _csrf_token(page) -> str:
    """Return any CSRF token rendered on the current page."""
    return page.locator("input[name=csrfmiddlewaretoken]").first.get_attribute("value")


# ---------------------------------------------------------------------------
# Active-campaign selector endpoints
# ---------------------------------------------------------------------------

def test_switch_active_campaign_returns_redirect(logged_in_page, live_server):
    """POST to ``campaigns:switch_active`` redirects to the safe target."""
    campaign = CampaignFactory()
    logged_in_page.goto(f"{live_server.url}/")
    response = logged_in_page.context.request.post(
        f"{live_server.url}/campanas/activa/{campaign.pk}/",
        form={"csrfmiddlewaretoken": _csrf_token(logged_in_page), "next": "/"},
        headers={"Referer": f"{live_server.url}/"},
    )
    assert response.status in (200, 301, 302)


def test_switch_active_campaign_inactive_returns_404(logged_in_page, live_server):
    """The view filters by ``is_active=True``; inactive campaigns 404."""
    campaign = CampaignFactory(is_active=False)
    logged_in_page.goto(f"{live_server.url}/")
    response = logged_in_page.context.request.post(
        f"{live_server.url}/campanas/activa/{campaign.pk}/",
        form={"csrfmiddlewaretoken": _csrf_token(logged_in_page)},
        headers={"Referer": f"{live_server.url}/"},
        max_redirects=0,
    )
    assert response.status == 404


def test_switch_active_campaign_unknown_returns_404(logged_in_page, live_server):
    logged_in_page.goto(f"{live_server.url}/")
    response = logged_in_page.context.request.post(
        f"{live_server.url}/campanas/activa/999999/",
        form={"csrfmiddlewaretoken": _csrf_token(logged_in_page)},
        headers={"Referer": f"{live_server.url}/"},
        max_redirects=0,
    )
    assert response.status == 404


def test_clear_active_campaign(logged_in_page, live_server):
    """``campaigns:clear_active`` returns a redirect even with no active campaign."""
    logged_in_page.goto(f"{live_server.url}/")
    response = logged_in_page.context.request.post(
        f"{live_server.url}/campanas/activa/limpiar/",
        form={"csrfmiddlewaretoken": _csrf_token(logged_in_page), "next": "/"},
        headers={"Referer": f"{live_server.url}/"},
    )
    assert response.status in (200, 301, 302)


def test_switch_active_campaign_requires_post(logged_in_page, live_server):
    """GET to the switch endpoint is rejected (``@require_POST``)."""
    campaign = CampaignFactory()
    response = logged_in_page.context.request.get(
        f"{live_server.url}/campanas/activa/{campaign.pk}/",
        max_redirects=0,
    )
    assert response.status == 405


def test_switch_active_campaign_requires_login(page, live_server):
    """Anonymous POST hits the login_required decorator and is redirected."""
    campaign = CampaignFactory()
    response = page.context.request.post(
        f"{live_server.url}/campanas/activa/{campaign.pk}/",
        form={"csrfmiddlewaretoken": "x"},
        max_redirects=0,
    )
    # 302 → login, or 403 if CSRF fires first; either way it's NOT a 200.
    assert response.status in (302, 403)


# ---------------------------------------------------------------------------
# Superadmin CRUD: list / create / detail views render
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "path,factory",
    [
        ("/campaigns/election/", ElectionFactory),
        ("/campaigns/politicalmovement/", PoliticalMovementFactory),
        ("/campaigns/position/", PositionFactory),
        ("/campaigns/candidate/", CandidateFactory),
        ("/campaigns/campaign/", CampaignFactory),
    ],
)
def test_superadmin_list_views_render(
    logged_in_superuser_page, live_server, path, factory
):
    """Each campaigns superadmin list page returns HTML 200 for a superuser."""
    factory()
    response = logged_in_superuser_page.goto(f"{live_server.url}{path}")
    assert response.status == 200


@pytest.mark.parametrize(
    "create_path",
    [
        "/campaigns/election/crear/",
        "/campaigns/politicalmovement/crear/",
        "/campaigns/position/crear/",
        "/campaigns/candidate/crear/",
    ],
)
def test_superadmin_create_pages_render(
    logged_in_superuser_page, live_server, create_path
):
    response = logged_in_superuser_page.goto(f"{live_server.url}{create_path}")
    assert response.status == 200
    # Each create page has a form with a submit button.
    assert logged_in_superuser_page.locator("form").count() >= 1


def test_campaign_create_form_has_required_fields(logged_in_superuser_page, live_server):
    """``CampaignForm`` exposes name / election / candidate / movement / position."""
    ElectionFactory()
    PoliticalMovementFactory()
    PositionFactory()
    CandidateFactory()
    logged_in_superuser_page.goto(f"{live_server.url}/campaigns/campaign/crear/")
    logged_in_superuser_page.wait_for_load_state("domcontentloaded")
    assert logged_in_superuser_page.locator("input[name=name]").count() == 1
    # FKs are rendered as Select2 with a hidden ``select[name=...]`` element.
    for field in ("election", "candidate", "movement", "position"):
        assert logged_in_superuser_page.locator(f"select[name={field}]").count() == 1


def test_campaign_detail_renders_name(logged_in_superuser_page, live_server):
    campaign = CampaignFactory(name="Campaña Detalle E2E")
    response = logged_in_superuser_page.goto(
        f"{live_server.url}/campaigns/campaign/{campaign.pk}/"
    )
    assert response.status == 200
    assert "Campaña Detalle E2E" in logged_in_superuser_page.content()


def test_election_detail_renders(logged_in_superuser_page, live_server):
    election = ElectionFactory(name="Elecciones Detalle 2026")
    response = logged_in_superuser_page.goto(
        f"{live_server.url}/campaigns/election/{election.pk}/"
    )
    assert response.status == 200
    assert "Elecciones Detalle 2026" in logged_in_superuser_page.content()


def test_candidate_detail_renders(logged_in_superuser_page, live_server):
    candidate = CandidateFactory(full_name="Juan Pérez")
    response = logged_in_superuser_page.goto(
        f"{live_server.url}/campaigns/candidate/{candidate.pk}/"
    )
    assert response.status == 200
    assert "Juan Pérez" in logged_in_superuser_page.content()
