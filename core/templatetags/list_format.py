"""Template filters for formatting list-cell values.

Used by `templates/base/base_list.html` to render booleans and other values
that arrive from `gmcm-django-superadmin`'s `FieldService.get_field_value()`
in a more user-friendly form (e.g. ``True`` -> green ``Sí`` badge,
``#50cd89`` -> color swatch, ``"Activa"`` -> success-coloured pill).
"""
import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

# `FieldService.get_field_value()` may return either Python booleans (when the
# field is a `BooleanField`) or their string representation. Match both.
_TRUTHY = {True, "True", "true"}
_FALSY = {False, "False", "false"}

# Hex color literal (3, 6 or 8 digits, with leading "#").
_HEX_COLOR_RE = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$")

# Mapping: workflow state label -> (Bootstrap color, optional Keenicon).
# When a list cell renders one of these values, it gets a coloured pill that
# matches the filter chip palette at the top of the same list. Aggregated
# from CampaignWorkflow, PhysicalAdWorkflow, PoliticalAgendaRequestWorkflow,
# and PoliticalAgendaEventWorkflow.
_STATE_BADGE_MAP = {
    # Negative / cancelled / rejected
    "anulada": ("danger", "shield-cross"),
    "cancelada": ("danger", "shield-cross"),
    "cancelado": ("danger", "shield-cross"),
    "rechazada": ("danger", "cross-circle"),
    "rechazado": ("danger", "cross-circle"),
    "dañada": ("danger", "abstract-26"),
    # In progress / pending review
    "borrador": ("warning", "notepad-edit"),
    "pendiente": ("warning", "time"),
    "pendiente instalación": ("warning", "wrench"),
    "en revisión": ("warning", "eye"),
    "reprogramado": ("warning", "arrows-circle"),
    "retirada": ("warning", "exit-down"),
    # Active / approved / running
    "activa": ("success", "check-circle"),
    "activo": ("success", "check-circle"),
    "aprobada": ("success", "verify"),
    "aprobado": ("success", "verify"),
    "agendado": ("success", "calendar-tick"),
    "instalada": ("success", "check-square"),
    "realizado": ("success", "check"),
    # Offered / informational
    "ofrecida": ("info", "send"),
    "ofrecido": ("info", "send"),
    # Closed / archived (neutral, finished)
    "cerrada": ("dark", "lock"),
    "cerrado": ("dark", "lock"),
    "donada": ("info", "gift"),
}


def _state_badge(value):
    """Return the matching state badge (color, icon) tuple, or None."""
    if not isinstance(value, str):
        return None
    return _STATE_BADGE_MAP.get(value.strip().lower())


@register.filter(name="list_cell")
def list_cell(value):
    """Render a list-cell value with light formatting.

    - Booleans render as colored "Sí"/"No" badges.
    - Hex color strings render as a small swatch alongside the literal,
      so catalogs that store a hex (e.g. ``#50cd89``) become legible at a
      glance instead of forcing the user to mentally translate the code.
    - Workflow state labels (``"Activa"``, ``"Borrador"``, ``"Aprobada"``…)
      render as a coloured pill that matches the filter chips above.
    - Everything else passes through unchanged.
    """
    if value is None or value == "":
        return ""
    if value is True or value is False or value in _TRUTHY or value in _FALSY:
        truthy = value in _TRUTHY or value is True
        css = "success" if truthy else "secondary"
        label = "Sí" if truthy else "No"
        return mark_safe(
            f'<span class="badge badge-light-{css} fw-semibold">{label}</span>'
        )
    if isinstance(value, str) and _HEX_COLOR_RE.match(value):
        safe_hex = escape(value)
        return mark_safe(
            f'<span class="cm-color-swatch">'
            f'<span class="cm-color-swatch__dot" style="background:{safe_hex};"></span>'
            f'{safe_hex}'
            f'</span>'
        )
    state = _state_badge(value)
    if state:
        css, icon = state
        safe_label = escape(value)
        icon_html = (
            f'<i class="ki-outline ki-{icon} fs-7 me-1" aria-hidden="true"></i>'
            if icon else ""
        )
        return mark_safe(
            f'<span class="badge badge-light-{css} fw-semibold d-inline-flex align-items-center">'
            f'{icon_html}{safe_label}</span>'
        )
    return value
