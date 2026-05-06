from unittest.mock import patch

from django.urls import set_script_prefix

from core.storage import TenantFileSystemStorage


def test_tenant_storage_url_includes_path_routing_prefix(settings):
    settings.MEDIA_URL = "/media/"
    storage = TenantFileSystemStorage()
    fake_connection = type("C", (), {"schema_name": "alpha"})()

    old_prefix = "/"
    set_script_prefix("/alpha/")
    try:
        with patch("django.db.connection", fake_connection):
            url = storage.url("territorial_ads/installations/photo.jpg")
    finally:
        set_script_prefix(old_prefix)

    assert url == "/alpha/media/tenants/alpha/territorial_ads/installations/photo.jpg"


def test_tenant_storage_url_is_unchanged_without_path_prefix(settings):
    settings.MEDIA_URL = "/media/"
    storage = TenantFileSystemStorage()
    fake_connection = type("C", (), {"schema_name": "alpha"})()

    set_script_prefix("/")
    with patch("django.db.connection", fake_connection):
        url = storage.url("territorial_ads/installations/photo.jpg")

    assert url == "/media/tenants/alpha/territorial_ads/installations/photo.jpg"
