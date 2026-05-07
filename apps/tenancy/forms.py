from django import forms

from core.widgets import LeafletMapWidget

from .models import TenantSettings


class TenantMapSettingsForm(forms.ModelForm):
    """Form to set the default map center and zoom for the active tenant."""

    location = forms.CharField(
        label="Centro del mapa",
        required=False,
        widget=LeafletMapWidget(
            lat_field="map_center_latitude",
            lng_field="map_center_longitude",
            attrs={"column": 12},
        ),
    )

    class Meta:
        model = TenantSettings
        fields = ("map_center_latitude", "map_center_longitude", "map_default_zoom")
        widgets = {
            "map_center_latitude": forms.NumberInput(
                attrs={"step": "0.000001", "class": "form-control form-control-sm"}
            ),
            "map_center_longitude": forms.NumberInput(
                attrs={"step": "0.000001", "class": "form-control form-control-sm"}
            ),
            "map_default_zoom": forms.NumberInput(
                attrs={"min": 1, "max": 20, "class": "form-control form-control-sm"}
            ),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("map_center_latitude") in (None, ""):
            self.add_error("map_center_latitude", "Marca un punto en el mapa.")
        if cleaned.get("map_center_longitude") in (None, ""):
            self.add_error("map_center_longitude", "Marca un punto en el mapa.")
        return cleaned
