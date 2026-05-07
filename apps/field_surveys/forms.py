from django import forms
from django_select2.forms import ModelSelect2Widget
from superadmin.forms import ModelForm

from core.widgets import LeafletMapWidget
from apps.campaigns.models import Campaign

from .models import (
    AdvertisingType,
    Competitor,
    CompetitorAdvertisingDetection,
    FieldSurvey,
    SurveyAdvertisingResponse,
    SurveySupportLevel,
)


class SurveySupportLevelForm(ModelForm):
    class Meta:
        model = SurveySupportLevel
        fieldsets = {
            "Nivel de apoyo": (
                ("code", "name"),
                ("color", "order"),
                ("is_active",),
            ),
        }


class SurveyAdvertisingResponseForm(ModelForm):
    class Meta:
        model = SurveyAdvertisingResponse
        fieldsets = {
            "Respuesta a publicidad": (
                ("code", "name"),
                ("color", "order"),
                ("is_active",),
            ),
        }


class AdvertisingTypeForm(ModelForm):
    class Meta:
        model = AdvertisingType
        fieldsets = {
            "Tipo de publicidad": (
                ("code", "name"),
                ("icon", "order"),
                ("is_active",),
            ),
        }


class CompetitorForm(ModelForm):
    class Meta:
        model = Competitor
        fieldsets = {
            "Competidor": (
                ("campaign", "list_number"),
                ("political_organization", "candidate_name"),
                ("color", "is_active"),
                ("notes",),
            ),
        }
        widgets = {
            "campaign": ModelSelect2Widget(
                model=Campaign,
                search_fields=["name__icontains", "candidate__full_name__icontains"],
                max_results=100,
                attrs={
                    "data-minimum-input-length": 0,
                    "data-app": "campaigns",
                    "data-model": "Campaign",
                },
            )
        }


class FieldSurveyForm(ModelForm):
    location = forms.CharField(
        label="Ubicación GPS",
        required=False,
        widget=LeafletMapWidget(
            lat_field="latitude",
            lng_field="longitude",
            attrs={
                "column": 12,
                "data-manual-field": "location_was_manually_adjusted",
                "data-accuracy-field": "gps_accuracy",
            },
        ),
    )

    class Meta:
        model = FieldSurvey
        # brigadier, person_name and person_phone are intentionally absent
        # from the form; brigadier is auto-stamped from the request user.
        fieldsets = {
            "Campaña y ubicación": (
                ("campaign",),
                ("location",),
                ("latitude", "longitude"),
                ("gps_accuracy", "location_was_manually_adjusted"),
            ),
            "Visita": (
                ("voters_count",),
                ("support_level", "advertising_response"),
                ("photo",),
                ("notes",),
            ),
        }
        widgets = {
            "campaign": ModelSelect2Widget(
                model=Campaign,
                search_fields=["name__icontains", "candidate__full_name__icontains"],
                max_results=100,
                attrs={
                    "data-minimum-input-length": 0,
                    "data-app": "campaigns",
                    "data-model": "Campaign",
                },
            ),
            "support_level": ModelSelect2Widget(
                model=SurveySupportLevel,
                search_fields=["name__icontains", "code__icontains"],
                max_results=100,
                attrs={
                    "data-minimum-input-length": 0,
                    "data-app": "field_surveys",
                    "data-model": "SurveySupportLevel",
                },
            ),
            "advertising_response": ModelSelect2Widget(
                model=SurveyAdvertisingResponse,
                search_fields=["name__icontains", "code__icontains"],
                max_results=100,
                attrs={
                    "data-minimum-input-length": 0,
                    "data-app": "field_surveys",
                    "data-model": "SurveyAdvertisingResponse",
                },
            ),
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
            "location_was_manually_adjusted": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("brigadier", None)
        self.fields.pop("person_name", None)
        self.fields.pop("person_phone", None)
        if "photo" in self.fields:
            self.fields["photo"].required = False

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("latitude") in (None, ""):
            self.add_error("latitude", "La ubicación GPS es obligatoria.")
        if cleaned_data.get("longitude") in (None, ""):
            self.add_error("longitude", "La ubicación GPS es obligatoria.")
        return cleaned_data


class CompetitorAdvertisingDetectionForm(ModelForm):
    location = forms.CharField(
        label="Ubicación GPS",
        required=False,
        widget=LeafletMapWidget(
            lat_field="latitude",
            lng_field="longitude",
            attrs={
                "column": 12,
                "data-manual-field": "location_was_manually_adjusted",
                "data-accuracy-field": "gps_accuracy",
            },
        ),
    )

    class Meta:
        model = CompetitorAdvertisingDetection
        # ``brigadier`` is intentionally absent: stamped from the request
        # user via ``BrigadierAutoAssignMixin``.
        fieldsets = {
            "Competencia": (
                ("campaign", "competitor"),
                ("advertising_type",),
            ),
            "Ubicación": (
                ("location",),
                ("latitude", "longitude"),
                ("gps_accuracy", "location_was_manually_adjusted"),
            ),
            "Evidencia": (
                ("photo",),
                ("observation",),
            ),
        }
        widgets = {
            "campaign": ModelSelect2Widget(
                model=Campaign,
                search_fields=["name__icontains", "candidate__full_name__icontains"],
                max_results=100,
                attrs={
                    "data-minimum-input-length": 0,
                    "data-app": "campaigns",
                    "data-model": "Campaign",
                },
            ),
            "competitor": ModelSelect2Widget(
                model=Competitor,
                search_fields=[
                    "list_number__icontains",
                    "political_organization__icontains",
                    "candidate_name__icontains",
                ],
                dependent_fields={"campaign": "campaign"},
                max_results=100,
                attrs={
                    "data-minimum-input-length": 0,
                    "data-app": "field_surveys",
                    "data-model": "Competitor",
                },
            ),
            "advertising_type": ModelSelect2Widget(
                model=AdvertisingType,
                search_fields=["name__icontains", "code__icontains"],
                max_results=100,
                attrs={
                    "data-minimum-input-length": 0,
                    "data-app": "field_surveys",
                    "data-model": "AdvertisingType",
                },
            ),
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
            "location_was_manually_adjusted": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("brigadier", None)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("latitude") in (None, ""):
            self.add_error("latitude", "La ubicación GPS es obligatoria.")
        if cleaned.get("longitude") in (None, ""):
            self.add_error("longitude", "La ubicación GPS es obligatoria.")
        return cleaned
