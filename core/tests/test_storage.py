from unittest.mock import patch

from core.storage import TenantS3Storage


def _fake_connection(schema_name):
    return type("C", (), {"schema_name": schema_name})()


def test_tenant_name_prefixes_under_tenant_schema():
    storage = TenantS3Storage()
    with patch("django.db.connection", _fake_connection("alpha")):
        result = storage._tenant_name("territorial_ads/installations/photo.jpg")
    assert result == "tenants/alpha/territorial_ads/installations/photo.jpg"


def test_tenant_name_skips_public_schema():
    storage = TenantS3Storage()
    with patch("django.db.connection", _fake_connection("public")):
        result = storage._tenant_name("tenant_branding/foo/logo.png")
    assert result == "tenant_branding/foo/logo.png"


def test_tenant_name_does_not_double_prefix():
    storage = TenantS3Storage()
    with patch("django.db.connection", _fake_connection("alpha")):
        result = storage._tenant_name("tenants/alpha/already/prefixed.jpg")
    assert result == "tenants/alpha/already/prefixed.jpg"


def test_url_delegates_with_tenant_prefixed_name():
    storage = TenantS3Storage()
    with patch("django.db.connection", _fake_connection("alpha")), patch(
        "storages.backends.s3boto3.S3Boto3Storage.url",
        return_value="http://example/tenants/alpha/foo.jpg",
    ) as parent_url:
        result = storage.url("foo.jpg")
    parent_url.assert_called_once_with("tenants/alpha/foo.jpg")
    assert result == "http://example/tenants/alpha/foo.jpg"
