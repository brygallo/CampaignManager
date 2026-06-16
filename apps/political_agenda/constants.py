"""Static color maps and permission strings for political agenda.

Plain, side-effect-free data only (sim's ``constants.py`` convention): the
calendar's state-border palette, the masked/default fill colors and the
view-private permission string. No business logic lives here.
"""

# Permission that lets a user see private events in full (title, place,
# details) instead of just the masked "Ocupado" slot.
VIEW_PRIVATE_EVENT_PERM = "political_agenda.view_private_politicalagendaevent"

# Border encodes workflow state. Fill comes from AgendaEventType.color, so the
# border has to remain readable on top of any catalog color.
STATE_BORDERS = {
    0: "#9aa0a6",   # CANCELED (hidden by default)
    1: "#3e97ff",   # DRAFT
    2: "#50cd89",   # SCHEDULED
    3: "#ffc700",   # RESCHEDULED
    4: "#7e8299",   # DONE
}

# Neutral gray used for private events shown as "Ocupado" to users without
# the view-private permission.
MASKED_EVENT_COLOR = "#7e8299"

# Default fill color used for an event whose type has no color configured.
DEFAULT_EVENT_COLOR = "#3e97ff"
