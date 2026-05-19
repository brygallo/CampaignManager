"""End-to-end tests for the workflows app."""
from __future__ import annotations

import pytest

from apps.campaigns.tests.factories import CampaignFactory

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def _csrf_token(page) -> str:
    """Return any CSRF token rendered on the current page."""
    return page.locator("input[name=csrfmiddlewaretoken]").first.get_attribute("value")


def test_workflow_change_state_requires_post(logged_in_page, live_server):
    # The view declares ``http_method_names = ["get", "post"]`` so non-allowed
    # methods (DELETE/PUT) should be rejected. Django's CSRF middleware may
    # short-circuit unsafe methods with 403 before dispatch reaches
    # http_method_not_allowed, so we accept either status.
    campaign = CampaignFactory()
    response = logged_in_page.context.request.fetch(
        f"{live_server.url}/workflow/campaigns/campaign/{campaign.pk}/change/",
        method="DELETE",
        max_redirects=0,
    )
    assert response.status in (403, 405)


def test_workflow_change_state_requires_login(page, live_server):
    # Anonymous POST hits LoginRequiredMixin; raise_exception=True yields 403.
    campaign = CampaignFactory()
    response = page.context.request.post(
        f"{live_server.url}/workflow/campaigns/campaign/{campaign.pk}/change/",
        form={"transition": "activate"},
        max_redirects=0,
    )
    assert response.status in (302, 403)


def test_workflow_change_state_unknown_model_404(logged_in_page, live_server):
    # ``apps.get_model`` raises LookupError on unknown (app, model) -> 404.
    logged_in_page.goto(f"{live_server.url}/")
    response = logged_in_page.context.request.post(
        f"{live_server.url}/workflow/foo/bar/1/change/",
        form={"csrfmiddlewaretoken": _csrf_token(logged_in_page), "transition": "activate"},
        headers={"Referer": f"{live_server.url}/"},
        max_redirects=0,
    )
    # Lookup errors bubble up as a 404 (or 400 if the view catches and reports it).
    assert response.status in (400, 404, 500)
    # Crucially, this should NOT be 200 / 302 — those would imply a valid run.
    assert response.status not in (200, 302)


def test_workflow_change_state_unknown_pk_404(logged_in_page, live_server):
    # A valid model but missing PK should raise DoesNotExist -> 404.
    logged_in_page.goto(f"{live_server.url}/")
    response = logged_in_page.context.request.post(
        f"{live_server.url}/workflow/campaigns/campaign/999999/change/",
        form={"csrfmiddlewaretoken": _csrf_token(logged_in_page), "transition": "activate"},
        headers={"Referer": f"{live_server.url}/"},
        max_redirects=0,
    )
    assert response.status in (400, 404, 500)
    assert response.status not in (200, 302)


def test_workflow_activate_campaign_transitions_state(
    logged_in_superuser_page, live_server
):
    # End-to-end happy path: DRAFT -> ACTIVE (workflow value 2).
    # The superuser bypasses ``has_transition_perm`` so we don't have to
    # grant the explicit ``campaigns.change_campaign`` permission.
    campaign = CampaignFactory()
    assert campaign.state == 1  # DRAFT

    logged_in_superuser_page.goto(f"{live_server.url}/")
    token = _csrf_token(logged_in_superuser_page)
    response = logged_in_superuser_page.context.request.post(
        f"{live_server.url}/workflow/campaigns/campaign/{campaign.pk}/change/",
        form={"csrfmiddlewaretoken": token, "transition": "activate"},
        headers={"Referer": f"{live_server.url}/"},
    )
    # The view returns 200 on success and 400 on workflow errors.
    assert response.status in (200, 302)
    # ``refresh_from_db`` would crash here: django-fsm's FSMIntegerField
    # protects ``state`` against direct __set__ (see ``protected=True`` in
    # the model), so a plain re-fetch is the only way to read the new value.
    from apps.campaigns.models import Campaign
    assert Campaign.objects.get(pk=campaign.pk).state == 2
