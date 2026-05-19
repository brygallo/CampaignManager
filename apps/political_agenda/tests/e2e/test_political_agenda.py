"""End-to-end tests for the political_agenda app."""
from __future__ import annotations

import json

import pytest

from apps.political_agenda.tests.factories import (
    AgendaEventTypeFactory,
    PoliticalAgendaEventFactory,
    PoliticalAgendaRequestFactory,
)

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def test_calendar_view_renders(logged_in_superuser_page, live_server):
    # Authenticated superuser should reach the calendar view.
    # The view requires political_agenda.view_politicalagendaevent.
    response = logged_in_superuser_page.goto(f"{live_server.url}/agenda/calendario/")
    assert response.status == 200


def test_calendar_filters_use_select2(logged_in_superuser_page, live_server):
    logged_in_superuser_page.goto(f"{live_server.url}/agenda/calendario/")
    assert logged_in_superuser_page.locator("#ag-cal-campaign.django-select2").count() == 1
    assert logged_in_superuser_page.locator("#ag-cal-event-type.django-select2").count() == 1
    assert logged_in_superuser_page.locator("#ag-cal-state.django-select2").count() == 1
    assert logged_in_superuser_page.locator("#ag-cal-responsible.django-select2").count() == 1


def test_calendar_view_requires_login(page, live_server):
    # Anonymous request should be redirected to the login page
    response = page.goto(f"{live_server.url}/agenda/calendario/")
    assert response.status == 200
    assert "/login/" in page.url


def test_calendar_data_returns_json(logged_in_superuser_page, live_server):
    # Calendar AJAX endpoint should return JSON content.
    # Uses superuser because the view requires the view_politicalagendaevent perm.
    response = logged_in_superuser_page.context.request.get(
        f"{live_server.url}/agenda/calendario/datos/"
    )
    assert response.status == 200
    content_type = response.headers.get("content-type", "")
    assert "json" in content_type.lower()
    # Body must be valid JSON
    data = json.loads(response.body())
    assert data is not None


def test_calendar_data_includes_events(logged_in_superuser_page, live_server):
    # An existing event should be present in the calendar data payload.
    # Uses superuser because the endpoint requires the view perm.
    event = PoliticalAgendaEventFactory(title="Mi evento")
    response = logged_in_superuser_page.context.request.get(
        f"{live_server.url}/agenda/calendario/datos/"
    )
    assert response.status == 200
    body = response.body().decode("utf-8")
    assert "Mi evento" in body or str(event.pk) in body


def test_event_popup_renders(logged_in_superuser_page, live_server):
    # Popup endpoint should return the event detail content.
    # Uses superuser because the view requires the view perm.
    event = PoliticalAgendaEventFactory(title="Reunion barrial")
    response = logged_in_superuser_page.goto(
        f"{live_server.url}/agenda/calendario/popup/{event.pk}/"
    )
    assert response.status == 200
    assert "Reunion barrial" in logged_in_superuser_page.content()


def test_event_popup_404_for_unknown(logged_in_superuser_page, live_server):
    # Unknown primary key should return 404.
    # Uses superuser to ensure we hit the 404 branch and not 403 from PermissionRequiredMixin.
    response = logged_in_superuser_page.goto(
        f"{live_server.url}/agenda/calendario/popup/999999/"
    )
    assert response.status == 404


def test_superadmin_event_list_renders(logged_in_superuser_page, live_server):
    # Superadmin list view should be reachable
    response = logged_in_superuser_page.goto(
        f"{live_server.url}/political_agenda/politicalagendaevent/"
    )
    assert response.status == 200


def test_superadmin_event_detail_renders(logged_in_superuser_page, live_server):
    # Detail page should render for an existing event
    event = PoliticalAgendaEventFactory(title="Caravana central")
    response = logged_in_superuser_page.goto(
        f"{live_server.url}/political_agenda/politicalagendaevent/{event.pk}/"
    )
    assert response.status == 200
    assert "Caravana central" in logged_in_superuser_page.content()


def test_superadmin_event_create_form_renders(
    logged_in_superuser_page, live_server
):
    # Ensure related catalog records exist so the form has options
    AgendaEventTypeFactory()

    response = logged_in_superuser_page.goto(
        f"{live_server.url}/political_agenda/politicalagendaevent/crear/"
    )
    assert response.status == 200
    assert logged_in_superuser_page.locator("input[name=title]").count() >= 1


def test_superadmin_request_list_renders(logged_in_superuser_page, live_server):
    # Request list view should render with an existing record
    PoliticalAgendaRequestFactory()
    response = logged_in_superuser_page.goto(
        f"{live_server.url}/political_agenda/politicalagendarequest/"
    )
    assert response.status == 200


def test_superadmin_agendaeventtype_list_renders(
    logged_in_superuser_page, live_server
):
    # Event type catalog should render
    AgendaEventTypeFactory()
    response = logged_in_superuser_page.goto(
        f"{live_server.url}/political_agenda/agendaeventtype/"
    )
    assert response.status == 200


@pytest.mark.parametrize(
    "slug",
    [
        "politicalagendaevent",
        "politicalagendarequest",
        "agendaeventtype",
    ],
)
def test_superadmin_catalog_list_renders(
    logged_in_superuser_page, live_server, slug
):
    # Each catalog list view under superadmin should render
    response = logged_in_superuser_page.goto(
        f"{live_server.url}/political_agenda/{slug}/"
    )
    assert response.status == 200


def test_superadmin_event_list_requires_superuser(logged_in_page, live_server):
    # Non-superuser should not be able to access the superadmin list
    response = logged_in_page.goto(
        f"{live_server.url}/political_agenda/politicalagendaevent/"
    )
    assert response.status in (302, 403) or "/login/" in logged_in_page.url
