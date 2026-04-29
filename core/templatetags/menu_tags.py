"""Helpers para resaltar el item activo del sidebar Metronic.

El árbol de menú producido por `superadmin.context_processors.menu`
tiene la forma:

    {"name": ..., "icon": ..., "url": ..., "submenus": [...]}

Cada ítem-hoja apunta a una URL de listado (típicamente `/<app>/<model>/listar/`).
Las páginas de detalle / formulario quedan bajo `/<app>/<model>/<pk>/...`.

Para que el sidebar marque correctamente:
  - el `<a>` hoja con `active`
  - los acordeones padre con `here show`

ofrecemos dos filtros:

  - `url_active`     → True si `request.path` cae dentro de la URL del ítem.
  - `branch_active`  → True si cualquier descendiente del ítem está activo.
"""
from django import template

register = template.Library()


def _normalize(path: str) -> str:
    return (path or "").rstrip("/")


@register.filter
def url_active(item_url: str, current_path: str) -> bool:
    """Compara la URL del ítem con la ruta actual considerando hijos."""
    if not item_url or not current_path:
        return False

    url = _normalize(item_url)
    path = _normalize(current_path)

    if path == url:
        return True

    # Las URLs de listado de superadmin terminan en "/listar".
    # Sus detalles/formularios viven bajo el mismo prefijo
    # (ej. /sites_mgmt/site/listar  →  /sites_mgmt/site/123/editar).
    if url.endswith("/listar"):
        base = url[: -len("/listar")]
        return path == base or path.startswith(base + "/")

    return path.startswith(url + "/")


@register.filter
def branch_active(node: dict, current_path: str) -> bool:
    """True si el nodo o algún descendiente apunta a la ruta actual."""
    if not node:
        return False

    if url_active(node.get("url") or "", current_path):
        return True

    for sub in node.get("submenus") or []:
        if branch_active(sub, current_path):
            return True

    return False
