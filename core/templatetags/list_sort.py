"""Template helpers for the sortable list-column headers."""
from urllib.parse import urlencode

from django import template

register = template.Library()


def _field_name(value):
    """Strip the ``field:Label`` shorthand down to the field name.

    Also translates Django's ``get_<field>_display`` convention back to the
    underlying field, since the user sorts by the enum value, not the label
    that the helper method renders.
    """
    raw = str(value).split(":", 1)[0]
    if raw.startswith("get_") and raw.endswith("_display"):
        return raw[len("get_"):-len("_display")]
    return raw


@register.simple_tag(takes_context=True)
def sort_url(context, field):
    """Build the URL for a sortable column header.

    Toggles ascending/descending/none against the current request:

    - No current sort on this field → ascending (``?ordering=<field>``)
    - Currently ascending           → descending (``?ordering=-<field>``)
    - Currently descending          → unsorted (drops ``ordering``)

    All other query string params (filters, search, page) are preserved.
    """
    field = _field_name(field)
    request = context.get("request")
    if request is None:
        return f"?ordering={field}"
    params = request.GET.copy()
    current = (params.get("ordering") or "").strip()
    current_field = current.lstrip("-")
    descending = current.startswith("-")

    if current_field != field:
        new_value = field  # start ascending
    elif not descending:
        new_value = f"-{field}"
    else:
        new_value = None  # clear

    if new_value is None:
        params.pop("ordering", None)
    else:
        params["ordering"] = new_value
    # Drop pagination — switching sort lands the user back on page 1.
    params.pop("page", None)
    qs = params.urlencode()
    return f"?{qs}" if qs else request.path


@register.simple_tag(takes_context=True)
def sort_indicator(context, field):
    """Return a short text indicator for the current sort direction on a field.

    Used inside the column header label so screen readers and visual users
    both see whether the column is currently sorting the table. Returns
    ``""`` when the column is not the active sort.
    """
    field = _field_name(field)
    ordering_ctx = (context.get("site") or {}).get("ordering") or {}
    if ordering_ctx.get("field") != field:
        return ""
    return "desc" if ordering_ctx.get("direction") == "desc" else "asc"


@register.simple_tag
def is_orderable(field, orderable_fields):
    """Return True when the field appears in the orderable allowlist.

    Used by the column header template to render either a plain ``<th>`` or
    a clickable ``<a>``. Compares against the site's ``orderable_fields``
    (or ``list_fields`` as fallback) after stripping the ``field:Label``
    shorthand.
    """
    if not orderable_fields:
        return False
    return _field_name(field) in set(orderable_fields)
