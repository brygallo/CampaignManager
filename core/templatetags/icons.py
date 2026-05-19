"""Template helpers for the Keenicons → Lucide migration.

Use cases that the bulk migration script (tools/migrate_icons.py) cannot
cover:

* Dynamic icon names that come from the database (sidebar items, agenda
  event types, state-filter chips). They were emitted as
  ``<i class="ki-outline ki-{{ item.icon }}">`` and we now need to map
  the stored Keenicon name to its Lucide equivalent before rendering.

Usage in templates::

    {% load icons %}
    <i data-lucide="{{ item.icon|lucide }}" class="fs-2"></i>
"""
from django import template

register = template.Library()

# Keep this map in sync with tools/migrate_icons.py (KEENICON → LUCIDE).
_KEENICON_TO_LUCIDE = {
    "abstract-14":          "menu",
    "abstract-26":          "circle-dashed",
    "add-files":            "file-plus",
    "arrow-left":           "arrow-left",
    "arrow-right":          "arrow-right",
    "arrow-up-right":       "arrow-up-right",
    "arrows-circle":        "rotate-cw",
    "calendar":             "calendar",
    "calendar-tick":        "calendar-check",
    "category":             "layout-grid",
    "chart-line":           "trending-up",
    "chart-line-up":        "trending-up",
    "chart-pie-simple":     "pie-chart",
    "chart-simple":         "bar-chart-3",
    "check":                "check",
    "check-circle":         "check-circle-2",
    "check-square":         "check-square",
    "cross":                "x",
    "cross-circle":         "x-circle",
    "cross-square":         "x-square",
    "cube-2":               "package",
    "document":             "file-text",
    "dollar":               "dollar-sign",
    "dots-circle":          "more-horizontal",
    "double-check":         "check-check",
    "down":                 "chevron-down",
    "element-11":           "layout-dashboard",
    "entrance-right":       "log-in",
    "eraser":               "eraser",
    "exit-right":           "log-out",
    "exit-down":            "log-out",
    "exit-up":              "external-link",
    "eye":                  "eye",
    "eye-slash":            "eye-off",
    "filter":               "filter",
    "flag":                 "flag",
    "folder-up":            "folder-up",
    "geolocation":          "map-pin",
    "gift":                 "gift",
    "handcart":             "shopping-cart",
    "home":                 "home",
    "home-2":               "home",
    "information":          "info",
    "information-2":        "info",
    "information-5":        "info",
    "left":                 "chevron-left",
    "lock":                 "lock",
    "lock-2":               "lock",
    "magnifier":            "search",
    "map":                  "map",
    "message-text-2":       "message-square",
    "microphone-2":         "mic",
    "minus":                "minus",
    "moon":                 "moon",
    "night-day":            "sun",
    "notepad-edit":         "notebook-pen",
    "notification-status":  "bell",
    "pencil":               "pencil",
    "people":               "users",
    "phone":                "phone",
    "picture":              "image",
    "pin":                  "map-pin",
    "plus":                 "plus",
    "plus-square":          "square-plus",
    "plus-squared":         "square-plus",
    "profile-circle":       "user-circle-2",
    "profile-user":         "user",
    "question-2":           "help-circle",
    "questionnaire-tablet": "clipboard-list",
    "ranking":              "trophy",
    "right":                "chevron-right",
    "rocket":               "rocket",
    "row-horizontal":       "rows-3",
    "screen":               "monitor",
    "send":                 "send",
    "setting-2":            "settings",
    "setting-3":            "settings",
    "setting-4":            "sliders-horizontal",
    "shield-cross":         "shield-x",
    "shield-tick":          "shield-check",
    "sms":                  "mail",
    "star":                 "star",
    "star-2":               "star",
    "tag":                  "tag",
    "time":                 "clock",
    "trash":                "trash-2",
    "user":                 "user",
    "user-tick":            "user-check",
    "verify":               "badge-check",
    "wifi":                 "wifi",
    "wrench":               "wrench",
}


@register.filter(name="lucide")
def lucide(value):
    """Map a stored Keenicon name (without the ``ki-`` prefix) to Lucide."""
    if not value:
        return "circle"
    return _KEENICON_TO_LUCIDE.get(value, value)
