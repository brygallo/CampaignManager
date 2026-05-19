"""End-to-end tests for the insoles app."""
from __future__ import annotations

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def test_insoles_form_requires_login(page, live_server):
    # Anonymous request should bounce to the login flow.
    response = page.context.request.get(
        f"{live_server.url}/insoles/forms/campaigns/election/",
        max_redirects=0,
    )
    # LoginRequiredMixin returns a 302 to /login/ for unauthenticated users.
    assert response.status in (302, 401, 403)
    if response.status == 302:
        assert "/login/" in (response.headers.get("location") or "")


def test_insoles_form_for_existing_model_renders_or_404(
    logged_in_superuser_page, live_server
):
    # The view dispatches to a superadmin-registered model; success or 404 is
    # acceptable, but a 500 indicates a regression in the generic renderer.
    response = logged_in_superuser_page.context.request.get(
        f"{live_server.url}/insoles/forms/campaigns/election/"
    )
    assert response.status in (200, 404)


def test_insoles_form_unknown_model_404(logged_in_page, live_server):
    # Bogus (app, model) pair must be rejected with a JSON 404 (see _InsolesPermMixin).
    response = logged_in_page.context.request.get(
        f"{live_server.url}/insoles/forms/nonexistent/noModel/"
    )
    assert response.status == 404


def test_insoles_detail_unknown_404(logged_in_superuser_page, live_server):
    # An unknown slug for a registered model returns 404 from RenderDetailView.
    # Uses superuser so we bypass the `view_election` perm check in
    # `_InsolesPermMixin` and actually hit the 404 branch in `get_data`.
    response = logged_in_superuser_page.context.request.get(
        f"{live_server.url}/insoles/detail/campaigns/election/abc/name/"
    )
    assert response.status == 404


def test_insoles_field_endpoint_unknown_model_404(logged_in_page, live_server):
    # The single-field renderer shares the same permission/lookup guard.
    response = logged_in_page.context.request.get(
        f"{live_server.url}/insoles/forms/nonexistent/noModel/name/"
    )
    assert response.status == 404
