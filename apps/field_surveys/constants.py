"""Static color palettes and tuning values for field surveys.

Plain, side-effect-free data only (sim's ``constants.py`` convention): the
fallback marker colors used when a catalog row has no color configured, and the
map point ceiling. No business logic lives here.
"""

# Fallback colors used when a catalog row has no color configured.
SUPPORT_FALLBACK_COLORS = {
    "APOYA": "#50cd89",
    "INDECISO": "#ffc700",
    "NO_APOYA": "#f1416c",
    "NO_ATENDIO": "#7e8299",
}
ADVERTISING_FALLBACK_COLORS = {
    "ACEPTA": "#3e97ff",
    "RECHAZA": "#7e8299",
}
DEFAULT_VISIT_COLOR = "#3e97ff"

# Fallback marker color for a competitor with no color configured.
COMPETITOR_FALLBACK_COLOR = "#d9214e"

# Hard ceiling on map points returned per response. Beyond this, the client
# struggles (Leaflet rendering + cluster math) and the payload grows past what's
# reasonable to ship over the wire. The frontend shows a banner asking the user
# to narrow filters when truncation kicks in. Long-term fix is viewport-based
# loading (audit A11 option 1).
MAX_MAP_POINTS = 5000
