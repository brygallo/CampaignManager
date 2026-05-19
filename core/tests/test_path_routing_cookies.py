"""Verify TenantPathRoutingMiddleware scopes cookies to the slug prefix.

Without this scoping, two tenants sharing the root domain (mode C in
docs/05_MULTITENANT_SPRINT1.md) would also share session cookies.
"""
from http.cookies import SimpleCookie
from types import SimpleNamespace

from django.http import HttpResponse

from core.middleware import (
    TenantAwareSessionMiddleware,
    TenantPathRoutingMiddleware,
)
from core.templatetags.menu_tags import url_active


def _mw():
    return TenantPathRoutingMiddleware(get_response=lambda r: HttpResponse())


class _DummySession:
    def __init__(self, session_key="tenant-key", empty=False):
        self.session_key = session_key
        self.accessed = True
        self.modified = True
        self._empty = empty

    def is_empty(self):
        return self._empty

    def get_expire_at_browser_close(self):
        return True

    def get_expiry_age(self):
        return 1200

    def save(self):
        return None


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


def test_tenant_session_cookie_name_is_slug_specific():
    request = SimpleNamespace(
        tenant_path_prefix="/alpha",
        COOKIES={},
        _session_cookie_name="sessionid_alpha",
        _session_cookie_path="/alpha/",
        session=_DummySession(),
    )
    response = TenantAwareSessionMiddleware(lambda req: HttpResponse()).process_response(
        request,
        HttpResponse(),
    )

    assert "sessionid_alpha" in response.cookies
    assert response.cookies["sessionid_alpha"]["path"] == "/alpha/"


def test_tenant_session_cookie_clears_legacy_shared_name():
    request = SimpleNamespace(
        tenant_path_prefix="/alpha",
        COOKIES={"sessionid": "legacy"},
        _session_cookie_name="sessionid_alpha",
        _session_cookie_path="/alpha/",
        session=_DummySession(),
    )
    response = TenantAwareSessionMiddleware(lambda req: HttpResponse()).process_response(
        request,
        HttpResponse(),
    )

    assert response.cookies["sessionid"]["max-age"] == 0 or response.cookies["sessionid"]["max-age"] == "0"
