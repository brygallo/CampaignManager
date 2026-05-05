"""Access-control tests for the protected /media/ view.

The view itself is reached via ``serve_protected_media``; we exercise the
auth + tenant-prefix logic without actually shipping bytes from disk
(``django.views.static.serve`` is patched).
"""
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.http import Http404, HttpResponse
from django.test import RequestFactory


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(username="u", password="x")


@pytest.fixture
def superuser(db):
    return get_user_model().objects.create_superuser(
        username="root", email="r@example.com", password="x"
    )


def _request(factory, path, user, schema):
    request = factory.get(path)
    request.user = user
    fake_connection = type("C", (), {"schema_name": schema})()
    return request, fake_connection


def test_anonymous_redirects_to_login(db):
    from django.contrib.auth.models import AnonymousUser

    from core.views import serve_protected_media

    rf = RequestFactory()
    req = rf.get("/media/tenants/foo/whatever.png")
    req.user = AnonymousUser()
    response = serve_protected_media(req, "tenants/foo/whatever.png")
    assert response.status_code == 302  # @login_required


def test_tenant_user_can_read_own_files(user):
    from core.views import serve_protected_media

    rf = RequestFactory()
    req, fake_conn = _request(rf, "/media/tenants/alpha/x.png", user, "alpha")
    with (
        patch("core.views.connection", fake_conn),
        patch("core.views.static_serve", return_value=HttpResponse(b"ok")),
    ):
        response = serve_protected_media(req, "tenants/alpha/x.png")
    assert response.status_code == 200


def test_tenant_user_cannot_read_other_tenant_files(user):
    from core.views import serve_protected_media

    rf = RequestFactory()
    req, fake_conn = _request(rf, "/media/tenants/beta/x.png", user, "alpha")
    with patch("core.views.connection", fake_conn), pytest.raises(Http404):
        serve_protected_media(req, "tenants/beta/x.png")


def test_branding_files_readable_by_any_authenticated_user(user):
    from core.views import serve_protected_media

    rf = RequestFactory()
    req, fake_conn = _request(rf, "/media/tenant_branding/foo/logo.png", user, "alpha")
    with (
        patch("core.views.connection", fake_conn),
        patch("core.views.static_serve", return_value=HttpResponse(b"ok")),
    ):
        response = serve_protected_media(req, "tenant_branding/foo/logo.png")
    assert response.status_code == 200


def test_legacy_paths_only_accessible_by_superuser(user, superuser):
    from core.views import serve_protected_media

    rf = RequestFactory()
    fake_conn = type("C", (), {"schema_name": "alpha"})()

    # regular user → 404
    req = rf.get("/media/legacy.png")
    req.user = user
    with patch("core.views.connection", fake_conn), pytest.raises(Http404):
        serve_protected_media(req, "legacy.png")

    # superuser → served
    req = rf.get("/media/legacy.png")
    req.user = superuser
    with (
        patch("core.views.connection", fake_conn),
        patch("core.views.static_serve", return_value=HttpResponse(b"ok")),
    ):
        response = serve_protected_media(req, "legacy.png")
    assert response.status_code == 200
