from types import SimpleNamespace
from unittest.mock import patch

from core.context_processors import tenant_path_menu


def test_tenant_path_menu_prefixes_sidebar_urls():
    request = SimpleNamespace(tenant_path_prefix="/alpha", user=object())
    menu = [
        {
            "name": "Publicidad territorial",
            "url": "/publicidad-territorial",
            "submenus": [
                {
                    "name": "Publicidad",
                    "url": "/publicidad-territorial/mapa/",
                    "submenus": [],
                }
            ],
        }
    ]

    with patch("superadmin.context_processors.build_user_menu", return_value=menu):
        context = tenant_path_menu(request)

    item = context["menu_tree"][0]
    assert item["url"] == "/alpha/publicidad-territorial"
    assert item["submenus"][0]["url"] == "/alpha/publicidad-territorial/mapa/"


def test_tenant_path_menu_does_not_double_prefix():
    request = SimpleNamespace(tenant_path_prefix="/alpha", user=object())
    menu = [{"name": "Inicio", "url": "/alpha/home/", "submenus": []}]

    with patch("superadmin.context_processors.build_user_menu", return_value=menu):
        context = tenant_path_menu(request)

    assert context["menu_tree"][0]["url"] == "/alpha/home/"
