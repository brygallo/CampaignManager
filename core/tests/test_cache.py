"""Tests for the tenant-aware Redis key function."""
from unittest.mock import patch

from core.cache import tenant_cache_key


def test_key_uses_active_schema():
    fake_connection = type("C", (), {"schema_name": "partido_alpha"})()
    with patch("core.cache.connection", fake_connection):
        key = tenant_cache_key("widget:42", "select2", 1)
    assert key.startswith("partido_alpha:")
    assert "widget:42" in key


def test_key_falls_back_to_public_when_schema_missing():
    fake_connection = type("C", (), {"schema_name": None})()
    with patch("core.cache.connection", fake_connection):
        key = tenant_cache_key("k", "p", 1)
    assert key.startswith("public:")


def test_two_schemas_produce_different_keys():
    a = type("C", (), {"schema_name": "a"})()
    b = type("C", (), {"schema_name": "b"})()
    with patch("core.cache.connection", a):
        ka = tenant_cache_key("same-key", "same-prefix", 1)
    with patch("core.cache.connection", b):
        kb = tenant_cache_key("same-key", "same-prefix", 1)
    assert ka != kb
