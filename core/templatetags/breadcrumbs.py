"""Auto-derive Metronic breadcrumbs from request, superadmin ``site`` and menu tree.

Renders ``[(label, url_or_None), ...]`` consumed by ``templates/base/base.html``.
Order: Inicio > Sección (menu) > Modelo (lista) > Acción (Crear / Editar / Eliminar
/ str(object)).

Views may bypass autodetection by setting ``breadcrumbs`` in context.
"""
from django import template
from django.urls import NoReverseMatch, reverse

register = template.Library()


def _normalize(path: str) -> str:
    return (path or "").rstrip("/")


def _find_section_for_url(menu_tree, target_url):
    """Return the top-level menu node whose subtree contains ``target_url``."""
    if not menu_tree or not target_url:
        return None
    target = _normalize(target_url)

    def contains(node):
        if _normalize(node.get("url") or "") == target:
            return True
        for sub in node.get("submenus") or []:
            if contains(sub):
                return True
        return False

    for top in menu_tree:
        if contains(top):
            return top
    return None


def _action_from_path(path, site_urls):
    """Identify the current action by URL suffix; ``None`` for list."""
    p = _normalize(path)
    list_url = _normalize(site_urls.get("list") or "")
    if list_url and p == list_url:
        return None
    if p.endswith("/crear"):
        return "Nuevo"
    if p.endswith("/editar"):
        return "Editar"
    if p.endswith("/eliminar"):
        return "Eliminar"
    return None


@register.simple_tag(takes_context=True)
def breadcrumb_trail(context):
    """Return the breadcrumb trail for the current page.

    Honors a manually provided ``breadcrumbs`` context var; otherwise derives
    it from ``request``, ``site`` (superadmin) and ``menu_tree``.
    """
    manual = context.get("breadcrumbs")
    if manual:
        return list(manual)

    request = context.get("request")
    if request is None:
        return []

    try:
        home_url = reverse("home")
    except NoReverseMatch:
        home_url = "/"

    trail = [("Inicio", home_url)]

    site = context.get("site") or {}
    site_urls = site.get("urls") or {} if isinstance(site, dict) else {}
    list_url = site_urls.get("list")

    section = _find_section_for_url(context.get("menu_tree"), list_url)
    if section:
        trail.append((section.get("name"), None))

    title = site.get("title") if isinstance(site, dict) else None
    if title:
        trail.append((str(title).capitalize(), list_url))

    action = _action_from_path(request.path, site_urls)
    obj = context.get("object")
    if action in ("Editar", "Eliminar"):
        if obj:
            trail.append((str(obj), site_urls.get("detail")))
        trail.append((action, None))
    elif action == "Nuevo":
        trail.append((action, None))
    elif obj is not None:
        trail.append((str(obj), None))

    return trail
