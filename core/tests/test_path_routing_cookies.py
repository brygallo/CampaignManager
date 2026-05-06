"""Verify TenantPathRoutingMiddleware scopes cookies to the slug prefix.

Without this scoping, two tenants sharing the root domain (mode C in
docs/05_MULTITENANT_SPRINT1.md) would also share session cookies.
"""
from http.cookies import SimpleCookie
from types import SimpleNamespace

from django.http import HttpResponse

from core.middleware import TenantPathRoutingMiddleware
from core.templatetags.menu_tags import url_active


def _mw():
    return TenantPathRoutingMiddleware(get_response=lambda r: HttpResponse())


def test_cookie_path_rewritten_to_tenant_prefix():
    response = HttpResponse()
    response.set_cookie("sessionid", "abc")
    request = SimpleNamespace(tenant_path_prefix="/alpha")

    _mw()._scope_cookies_to_tenant(request, response)

    assert response.cookies["sessionid"]["path"] == "/alpha/"


def test_cookie_already_scoped_is_not_double_prefixed():
    response = HttpResponse()
    response.cookies = SimpleCookie()
    response.set_cookie("sessionid", "abc", path="/alpha/sub")
    request = SimpleNamespace(tenant_path_prefix="/alpha")

    _mw()._scope_cookies_to_tenant(request, response)

    assert response.cookies["sessionid"]["path"] == "/alpha/sub"


def test_no_op_when_no_tenant_prefix():
    response = HttpResponse()
    response.set_cookie("sessionid", "abc")
    request = SimpleNamespace()

    _mw()._scope_cookies_to_tenant(request, response)

    assert response.cookies["sessionid"]["path"] == "/"


def test_url_active_accepts_path_routed_tenant_prefix():
    assert url_active(
        "/alpha/publicidad-territorial/mapa/",
        "/publicidad-territorial/mapa/",
    )
