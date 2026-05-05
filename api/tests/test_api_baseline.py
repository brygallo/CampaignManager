"""Baseline checks for the API surface.

These tests don't depend on any specific ViewSet — they verify the
plumbing (auth, schema, docs) is wired correctly so future endpoints
inherit the right defaults.
"""
import pytest
from django.urls import reverse
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_schema_requires_authentication():
    """An anonymous client must not be able to harvest the API schema."""
    client = APIClient()
    response = client.get(reverse("api_schema"))
    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_schema_served_to_authenticated_user(django_user_model):
    user = django_user_model.objects.create_user(username="u", password="x")
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.get(reverse("api_schema"))
    assert response.status_code == 200
    assert b"openapi" in response.content.lower()


@pytest.mark.django_db
def test_docs_requires_authentication():
    client = APIClient()
    response = client.get(reverse("api_docs"))
    assert response.status_code in (401, 403)
