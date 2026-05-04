"""Template helpers for the user permission matrix."""
from django import template

register = template.Library()


@register.filter
def get_item(mapping, key):
    """Return ``mapping[key]`` or ``None`` if missing.

    Useful when the template needs to look up a value in a dict by a
    variable (e.g. ``{{ standard_labels|get_item:action }}``).
    """
    if mapping is None:
        return None
    try:
        return mapping.get(key)
    except AttributeError:
        return None
