from types import SimpleNamespace

from core.views import _select2_url_matches_request


def test_select2_url_matches_request_path():
    request = SimpleNamespace(path="/select2/fields/auto.json")

    assert _select2_url_matches_request("/select2/fields/auto.json", request) is True


def test_select2_url_matches_path_routed_tenant_prefix():
    request = SimpleNamespace(
        path="/select2/fields/auto.json",
        tenant_path_prefix="/pachackutik",
    )

    assert _select2_url_matches_request(
        "/pachackutik/select2/fields/auto.json",
        request,
    ) is True


def test_select2_url_rejects_different_path():
    request = SimpleNamespace(
        path="/select2/fields/auto.json",
        tenant_path_prefix="/pachackutik",
    )

    assert (
        _select2_url_matches_request("/otro/select2/fields/auto.json", request)
        is False
    )
