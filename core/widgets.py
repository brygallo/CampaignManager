from django import forms
from django.utils.html import format_html


class ColorPickerWidget(forms.TextInput):
    # Rendering lives in templates/widgets/colorpickerinput.html, resolved via
    # settings.TEMPLATE_WIDGETS["colorpicker"] (matches BoundField.widget_type).

    def __init__(self, attrs=None):
        defaults = {"class": "form-control form-control-sm form-control-solid cm-color-picker"}
        if attrs:
            defaults.update(attrs)
        super().__init__(attrs=defaults)


class JsonWidget(forms.Textarea):
    """Textarea that signals JSON content to the frontend."""

    def __init__(self, attrs=None):
        defaults = {"class": "form-control font-monospace", "rows": 6}
        if attrs:
            defaults.update(attrs)
        super().__init__(attrs=defaults)


class TextSearchWidget(forms.TextInput):
    """Text input with the CSS hook the frontend uses to attach a search button."""

    def __init__(self, attrs=None):
        defaults = {"class": "form-control text-search-control"}
        if attrs:
            defaults.update(attrs)
        super().__init__(attrs=defaults)


class LeafletMapWidget(forms.Widget):
    """Map picker that writes latitude and longitude into sibling form fields.

    Default lat/lng/zoom are *intentionally* not emitted unless explicitly
    overridden — the JS reads ``window.TENANT_MAP_CENTER`` (set per-tenant
    via ``TenantSettings``) as the fallback so every form respects the
    tenant's preferred starting view without each form having to plumb it.
    """

    def __init__(
        self,
        *,
        lat_field,
        lng_field,
        default_lat=None,
        default_lng=None,
        default_zoom=None,
        attrs=None,
    ):
        self.lat_field = lat_field
        self.lng_field = lng_field
        self.default_lat = default_lat
        self.default_lng = default_lng
        self.default_zoom = default_zoom
        defaults = {
            "data-leaflet-map": "true",
            "data-lat-field": lat_field,
            "data-lng-field": lng_field,
        }
        if default_lat is not None:
            defaults["data-default-lat"] = default_lat
        if default_lng is not None:
            defaults["data-default-lng"] = default_lng
        if default_zoom is not None:
            defaults["data-default-zoom"] = default_zoom
        if attrs:
            defaults.update(attrs)
        super().__init__(attrs=defaults)

    def value_from_datadict(self, data, files, name):
        return ""

    def render(self, name, value, attrs=None, renderer=None):
        attrs = self.build_attrs(self.attrs, attrs)
        widget_id = attrs.get("id") or f"id_{name}"
        return format_html(
            """
            <div class="leaflet-map-widget"
                 id="{}_map"
                 data-leaflet-map="true"
                 data-lat-field="{}"
                 data-lng-field="{}"
                 data-manual-field="{}"
                 data-accuracy-field="{}"
                 data-default-lat="{}"
                 data-default-lng="{}"
                 data-default-zoom="{}"
                 data-default-basemap="{}">
              <div class="leaflet-map-widget__toolbar">
                <button type="button" class="btn btn-sm btn-light-primary" data-leaflet-current-location>
                  <i data-lucide="map-pin" class="fs-3"></i>Usar ubicación actual
                </button>
                <button type="button" class="btn btn-sm btn-light" data-leaflet-clear>
                  <i data-lucide="x" class="fs-3"></i>Limpiar
                </button>
              </div>
              <div class="leaflet-map-widget__canvas"></div>
              <div class="leaflet-map-widget__status text-muted small mt-2" data-leaflet-status>
                Haz clic en el mapa o usa tu ubicación actual.
              </div>
            </div>
            """,
            widget_id,
            self.lat_field,
            self.lng_field,
            attrs.get("data-manual-field", ""),
            attrs.get("data-accuracy-field", ""),
            attrs.get("data-default-lat", ""),
            attrs.get("data-default-lng", ""),
            attrs.get("data-default-zoom", ""),
            attrs.get("data-default-basemap", "carto"),
        )
