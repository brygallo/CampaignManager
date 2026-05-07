from django import forms
from django_select2.forms import ModelSelect2Widget, ModelSelect2MultipleWidget
from superadmin.forms import ModelForm

from core.widgets import LeafletMapWidget
from apps.campaigns.models import Campaign
from apps.locations.models import Parish, Sector

from .models import (
    AdvertisingType,
    Competitor,
    CompetitorAdvertisingDetection,
    FieldSurvey,
    OwnAdvertisingPlacement,
    SurveyResultOption,
)


class SurveyResultOptionForm(ModelForm):
    class Meta:
        model = SurveyResultOption
        fieldsets = {
            "Resultado": (
                ("code", "name"),
                ("order", "is_active"),
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
                attrs={"data-minimum-input-length": 0, "data-app": "campaigns", "data-model": "Campaign"},
            )
        }


class FieldSurveyForm(ModelForm):
    location = forms.CharField(
        label="Ubicación GPS",
        required=False,
        widget=LeafletMapWidget(
            lat_field="latitude",
            lng_field="longitude",
            attrs={"column": 12, "data-manual-field": "location_was_manually_adjusted", "data-accuracy-field": "gps_accuracy"},
        ),
    )

    class Meta:
        model = FieldSurvey
        fieldsets = {
            "Campaña y ubicación": (
                ("campaign", "brigadier"),
                ("location",),
                ("latitude", "longitude"),
                ("gps_accuracy", "location_was_manually_adjusted"),
            ),
            "Territorio": (
                ("parish", "neighborhood"),
                ("address",),
                ("reference",),
            ),
            "Persona o vivienda": (
                ("person_name", "person_phone"),
                ("voters_count",),
                ("results",),
                ("notes",),
            ),
        }
        widgets = {
            "campaign": ModelSelect2Widget(
                model=Campaign,
                search_fields=["name__icontains", "candidate__full_name__icontains"],
                max_results=100,
                attrs={"data-minimum-input-length": 0, "data-app": "campaigns", "data-model": "Campaign"},
            ),
            "parish": ModelSelect2Widget(
                model=Parish,
                search_fields=["name__icontains", "canton__name__icontains"],
                max_results=100,
                attrs={"data-minimum-input-length": 0, "data-app": "locations", "data-model": "Parish"},
            ),
            "neighborhood": ModelSelect2Widget(
                model=Sector,
                search_fields=["name__icontains", "parish__name__icontains"],
                max_results=100,
                attrs={"data-minimum-input-length": 0, "data-app": "locations", "data-model": "Sector"},
            ),
            "results": ModelSelect2MultipleWidget(
                model=SurveyResultOption,
                search_fields=["name__icontains", "code__icontains"],
                max_results=100,
                attrs={"data-minimum-input-length": 0, "data-app": "field_surveys", "data-model": "SurveyResultOption"},
            ),
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
            "location_was_manually_adjusted": forms.HiddenInput(),
        }

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("latitude") in (None, ""):
            self.add_error("latitude", "La ubicación GPS es obligatoria.")
        if cleaned_data.get("longitude") in (None, ""):
            self.add_error("longitude", "La ubicación GPS es obligatoria.")
        return cleaned_data


class FieldSurveyQuickForm(FieldSurveyForm):
    own_advertising_type = forms.ModelChoiceField(
        label="Tipo de publicidad propia",
        queryset=AdvertisingType.objects.none(),
        required=False,
        widget=ModelSelect2Widget(
            model=AdvertisingType,
            search_fields=["name__icontains", "code__icontains"],
            max_results=100,
            attrs={"data-minimum-input-length": 0, "data-app": "field_surveys", "data-model": "AdvertisingType"},
        ),
    )
    own_photo = forms.ImageField(label="Foto de publicidad propia", required=False)
    own_observation = forms.CharField(label="Observación", widget=forms.Textarea, required=False)

    competitor = forms.ModelChoiceField(
        label="Competidor",
        queryset=Competitor.objects.none(),
        required=False,
        widget=ModelSelect2Widget(
            model=Competitor,
            search_fields=["list_number__icontains", "political_organization__icontains", "candidate_name__icontains"],
            max_results=100,
            attrs={"data-minimum-input-length": 0, "data-app": "field_surveys", "data-model": "Competitor"},
        ),
    )
    competitor_advertising_type = forms.ModelChoiceField(
        label="Tipo de publicidad competencia",
        queryset=AdvertisingType.objects.none(),
        required=False,
        widget=ModelSelect2Widget(
            model=AdvertisingType,
            search_fields=["name__icontains", "code__icontains"],
            max_results=100,
            attrs={"data-minimum-input-length": 0, "data-app": "field_surveys", "data-model": "AdvertisingType"},
        ),
    )
    competitor_photo = forms.ImageField(label="Foto competencia", required=False)
    competitor_observation = forms.CharField(label="Observación competencia", widget=forms.Textarea, required=False)

    class Meta(FieldSurveyForm.Meta):
        model = FieldSurvey
        fieldsets = {
            "Campaña y ubicación": (
                ("campaign",),
                ("location",),
                ("latitude", "longitude"),
                ("gps_accuracy", "location_was_manually_adjusted"),
            ),
            "Persona o vivienda": (
                ("person_name", "person_phone"),
                ("voters_count",),
                ("parish", "neighborhood"),
                ("address",),
                ("reference",),
                ("results",),
                ("notes",),
            ),
            "Publicidad propia colocada": (
                ("own_advertising_type",),
                ("own_photo",),
                ("own_observation",),
            ),
            "Publicidad de competencia detectada": (
                ("competitor",),
                ("competitor_advertising_type",),
                ("competitor_photo",),
                ("competitor_observation",),
            ),
        }
        widgets = FieldSurveyForm.Meta.widgets

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("brigadier", None)
        self.fields["results"].queryset = SurveyResultOption.objects.filter(is_active=True).order_by("order", "name")
        self.fields["own_advertising_type"].queryset = AdvertisingType.objects.filter(is_active=True).order_by("order", "name")
        self.fields["competitor_advertising_type"].queryset = AdvertisingType.objects.filter(is_active=True).order_by("order", "name")
        self.fields["competitor"].queryset = Competitor.objects.filter(is_active=True).order_by(
            "campaign__name", "list_number", "political_organization"
        )
        for field_name in ("own_observation", "competitor_observation"):
            self.fields[field_name].widget.attrs.setdefault("rows", 2)

    def clean(self):
        cleaned_data = super().clean()
        own_fields = [
            cleaned_data.get("own_advertising_type"),
            cleaned_data.get("own_photo"),
            cleaned_data.get("own_observation"),
        ]
        if any(own_fields):
            if not cleaned_data.get("own_advertising_type"):
                self.add_error("own_advertising_type", "Selecciona el tipo de publicidad propia.")
            if not cleaned_data.get("own_photo"):
                self.add_error("own_photo", "La foto es obligatoria para publicidad propia colocada.")

        competitor_fields = [
            cleaned_data.get("competitor"),
            cleaned_data.get("competitor_advertising_type"),
            cleaned_data.get("competitor_photo"),
            cleaned_data.get("competitor_observation"),
        ]
        if any(competitor_fields):
            if not cleaned_data.get("competitor"):
                self.add_error("competitor", "Selecciona el competidor.")
            if not cleaned_data.get("competitor_advertising_type"):
                self.add_error("competitor_advertising_type", "Selecciona el tipo de publicidad detectada.")
            competitor = cleaned_data.get("competitor")
            campaign = cleaned_data.get("campaign")
            if competitor and campaign and competitor.campaign_id != campaign.id:
                self.add_error("competitor", "El competidor debe pertenecer a la campaña seleccionada.")
        return cleaned_data

    def save_related_records(self, field_survey, user):
        if self.cleaned_data.get("own_advertising_type"):
            OwnAdvertisingPlacement.objects.create(
                field_survey=field_survey,
                advertising_type=self.cleaned_data["own_advertising_type"],
                photo=self.cleaned_data["own_photo"],
                latitude=field_survey.latitude,
                longitude=field_survey.longitude,
                observation=self.cleaned_data.get("own_observation", ""),
                created_by=user,
            )
        if self.cleaned_data.get("competitor"):
            CompetitorAdvertisingDetection.objects.create(
                campaign=field_survey.campaign,
                competitor=self.cleaned_data["competitor"],
                brigadier=field_survey.brigadier,
                field_survey=field_survey,
                advertising_type=self.cleaned_data["competitor_advertising_type"],
                latitude=field_survey.latitude,
                longitude=field_survey.longitude,
                gps_accuracy=field_survey.gps_accuracy,
                location_was_manually_adjusted=field_survey.location_was_manually_adjusted,
                address=field_survey.address,
                reference=field_survey.reference,
                photo=self.cleaned_data.get("competitor_photo"),
                observation=self.cleaned_data.get("competitor_observation", ""),
                created_by=user,
            )


class OwnAdvertisingPlacementForm(ModelForm):
    location = forms.CharField(
        label="Ubicación GPS",
        required=False,
        widget=LeafletMapWidget(
            lat_field="latitude",
            lng_field="longitude",
            attrs={"column": 12},
        ),
    )

    class Meta:
        model = OwnAdvertisingPlacement
        fieldsets = {
            "Publicidad": (
                ("field_survey", "advertising_type"),
                ("photo",),
                ("location",),
                ("latitude", "longitude"),
                ("observation",),
            ),
        }
        widgets = {
            "advertising_type": ModelSelect2Widget(
                model=AdvertisingType,
                search_fields=["name__icontains", "code__icontains"],
                max_results=100,
                attrs={"data-minimum-input-length": 0, "data-app": "field_surveys", "data-model": "AdvertisingType"},
            ),
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
        }

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
            attrs={"column": 12, "data-manual-field": "location_was_manually_adjusted", "data-accuracy-field": "gps_accuracy"},
        ),
    )

    class Meta:
        model = CompetitorAdvertisingDetection
        fieldsets = {
            "Competencia": (
                ("campaign", "competitor"),
                ("brigadier", "advertising_type"),
            ),
            "Ubicación": (
                ("location",),
                ("latitude", "longitude"),
                ("gps_accuracy", "location_was_manually_adjusted"),
                ("address",),
                ("reference",),
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
                attrs={"data-minimum-input-length": 0, "data-app": "campaigns", "data-model": "Campaign"},
            ),
            "competitor": ModelSelect2Widget(
                model=Competitor,
                search_fields=["list_number__icontains", "political_organization__icontains", "candidate_name__icontains"],
                max_results=100,
                attrs={"data-minimum-input-length": 0, "data-app": "field_surveys", "data-model": "Competitor"},
            ),
            "advertising_type": ModelSelect2Widget(
                model=AdvertisingType,
                search_fields=["name__icontains", "code__icontains"],
                max_results=100,
                attrs={"data-minimum-input-length": 0, "data-app": "field_surveys", "data-model": "AdvertisingType"},
            ),
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
            "location_was_manually_adjusted": forms.HiddenInput(),
        }
