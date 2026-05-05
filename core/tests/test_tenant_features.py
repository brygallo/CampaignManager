"""Tests for the ``feature_enabled`` menu filter and ``tenant_features`` CP."""
from core.context_processors import GATED_MENU_SECTIONS
from core.templatetags.menu_tags import feature_enabled


def test_non_gated_section_always_visible():
    node = {"name": "Sistema"}
    assert feature_enabled(node, set()) is True
    assert feature_enabled(node, {"Campañas"}) is True


def test_gated_section_hidden_when_flag_off():
    node = {"name": "Campañas"}
    assert feature_enabled(node, set()) is False


def test_gated_section_visible_when_flag_on():
    node = {"name": "Campañas"}
    assert feature_enabled(node, {"Campañas"}) is True


def test_no_tenant_features_falls_back_to_visible():
    """``tenant_features`` is ``None`` for the public schema and pre-migration
    legacy tenants — the menu must keep working in that case."""
    node = {"name": "Campañas"}
    assert feature_enabled(node, None) is True


def test_empty_node_returns_false():
    assert feature_enabled(None, set()) is False
    assert feature_enabled({}, set()) is False


def test_all_gated_sections_documented():
    """Catch-22: when a new TenantSettings flag is added, the corresponding
    menu name must also be added to GATED_MENU_SECTIONS or it won't be
    enforceable. This test documents that contract."""
    expected = {
        "Campañas",
        "Agenda política",
        "Levantamientos de campo",
        "Publicidad territorial",
        "Geografía",
    }
    assert GATED_MENU_SECTIONS == expected
