"""Helpers for highlighting the active Metronic sidebar item.

The menu tree produced by `superadmin.context_processors.menu` has this shape:

    {"name": ..., "icon": ..., "url": ..., "submenus": [...]}

Each leaf item points to a list URL, usually `/<app>/<model>/listar/`.
Detail and form pages live under `/<app>/<model>/<pk>/...`.

To let the sidebar mark these elements correctly:
  - the leaf `<a>` with `active`
  - parent accordions with `here show`

two filters are exposed:

  - `url_active`     -> True when `request.path` falls within the item URL.
  - `branch_active`  -> True when any descendant item is active.
"""
from django import template

register = template.Library()


def _normalize(path: str) -> str:
    return (path or "").rstrip("/")


def _without_first_segment(path: str) -> str:
    parts = _normalize(path).lstrip("/").split("/", 1)
    if len(parts) != 2:
        return path
    return "/" + parts[1]


@register.filter
def url_active(item_url: str, current_path: str) -> bool:
    """Compare an item URL with the current path, including child pages."""
    if not item_url or not current_path:
        return False

    url = _normalize(item_url)
    path = _normalize(current_path)

    if _url_matches(url, path):
        return True

    # Path-routed tenants render hrefs as /<tenant>/..., while middleware
    # exposes request.path to templates without that first tenant segment.
    unprefixed_url = _without_first_segment(url)
    return unprefixed_url != url and _url_matches(unprefixed_url, path)


def _url_matches(url: str, path: str) -> bool:
    if path == url:
        return True

    # Superadmin list URLs end in "/listar".
    # Their detail and form pages live under the same prefix
    # (for example, /campaigns/campaign/listar -> /campaigns/campaign/123/editar).
    if url.endswith("/listar"):
        base = url[: -len("/listar")]
        return path == base or path.startswith(base + "/")

    return path.startswith(url + "/")



@register.filter
def branch_active(node: dict, current_path: str) -> bool:
    """Return True when the node or any descendant points to the current path."""
    if not node:
        return False

    if url_active(node.get("url") or "", current_path):
        return True

    for sub in node.get("submenus") or []:
        if branch_active(sub, current_path):
            return True

    return False


@register.filter
def feature_enabled(node: dict, tenant_features) -> bool:
    """Return True if a top-level menu node is enabled for the tenant.

    A node is considered "gated" only when its name appears in
    ``GATED_MENU_SECTIONS`` (see ``core.context_processors``); other
    sections (e.g. ``Sistema``, ``Catálogos``) are always shown.
    """
    from core.context_processors import GATED_MENU_SECTIONS

    if not node:
        return False
    name = node.get("name")
    if name not in GATED_MENU_SECTIONS:
        return True
    if tenant_features is None:
        return True
    return name in tenant_features
