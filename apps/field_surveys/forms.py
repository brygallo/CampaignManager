from django import forms
from django_select2.forms import ModelSelect2Widget, ModelSelect2MultipleWidget
from superadmin.forms import ModelForm

from core.widgets import LeafletMapWidget
from apps.campaigns.models import Campaign
from apps.locations.models import Parish, Sector
from apps.territorial_ads.models import AdvertisingCostType, PhysicalAdvertisement

from .models import (
    AdvertisingType,
    Competitor,
    CompetitorAdvertisingDetection,
    FieldSurvey,
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
        # brigadier, parish, neighborhood, address, reference, person_name and
        # person_phone are intentionally absent from the form: brigadier is
        # auto-stamped from the request user; the rest are derivable from GPS
        # and not worth asking the user for in the field.
        fieldsets = {
            "Campaña y ubicación": (
                ("campaign",),
                ("location",),
                ("latitude", "longitude"),
                ("gps_accuracy", "location_was_manually_adjusted"),
            ),
            "Visita": (
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("brigadier", None)
        self.fields.pop("parish", None)
        self.fields.pop("neighborhood", None)
        self.fields.pop("address", None)
        self.fields.pop("reference", None)
        self.fields.pop("person_name", None)
        self.fields.pop("person_phone", None)

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("latitude") in (None, ""):
            self.add_error("latitude", "La ubicación GPS es obligatoria.")
        if cleaned_data.get("longitude") in (None, ""):
            self.add_error("longitude", "La ubicación GPS es obligatoria.")
        return cleaned_data


class FieldSurveyQuickForm(FieldSurveyForm):
    """Quick brigadier form. Optionally chains:

    - Creating a ``PhysicalAdvertisement`` in OFRECIDA when the brigadier offers a
      placement at the visited location.
    - Creating a ``CompetitorAdvertisingDetection`` when competitor advertising is
      observed.
    """

    offer_advertising = forms.BooleanField(
        label="Ofrecer publicidad en este punto",
        required=False,
        help_text="Marca para registrar una propuesta de publicidad propia ligada a esta visita.",
    )
    offered_advertisement_type = forms.ModelChoiceField(
        label="Tipo de publicidad ofrecida",
        queryset=AdvertisingType.objects.none(),
        required=False,
        widget=ModelSelect2Widget(
            model=AdvertisingType,
            search_fields=["name__icontains", "code__icontains"],
            max_results=100,
            attrs={"data-minimum-input-length": 0, "data-app": "field_surveys", "data-model": "AdvertisingType"},
        ),
    )
    offered_owner_name = forms.CharField(label="Propietario / contacto", max_length=180, required=False)
    offered_owner_phone = forms.CharField(label="Teléfono contacto", max_length=32, required=False)
    offered_cost_type = forms.ModelChoiceField(
        label="Tipo de costo",
        queryset=AdvertisingCostType.objects.none(),
        required=False,
    )
    offered_cost_amount = forms.DecimalField(
        label="Monto acordado",
        max_digits=10,
        decimal_places=2,
        min_value=0,
        required=False,
    )
    offered_photo = forms.ImageField(label="Foto del lugar ofrecido", required=False)
    offered_notes = forms.CharField(label="Condiciones ofrecidas", widget=forms.Textarea, required=False)

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
            "Visita": (
                ("voters_count",),
                ("results",),
                ("notes",),
            ),
            "Ofrecer publicidad": (
                ("offer_advertising",),
                ("offered_advertisement_type",),
                ("offered_owner_name", "offered_owner_phone"),
                ("offered_cost_type", "offered_cost_amount"),
                ("offered_photo",),
                ("offered_notes",),
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
        self.fields["offered_advertisement_type"].queryset = AdvertisingType.objects.filter(is_active=True).order_by("order", "name")
        self.fields["offered_cost_type"].queryset = AdvertisingCostType.objects.filter(is_active=True).order_by("order", "name")
        self.fields["competitor_advertising_type"].queryset = AdvertisingType.objects.filter(is_active=True).order_by("order", "name")
        self.fields["competitor"].queryset = Competitor.objects.filter(is_active=True).order_by(
            "campaign__name", "list_number", "political_organization"
        )
        self.fields["offered_notes"].widget.attrs.setdefault("rows", 2)
        self.fields["competitor_observation"].widget.attrs.setdefault("rows", 2)

    def clean(self):
        cleaned_data = super().clean()

        if cleaned_data.get("offer_advertising"):
            required = {
                "offered_advertisement_type": "Selecciona el tipo de publicidad.",
                "offered_owner_name": "Indica el nombre del propietario.",
                "offered_owner_phone": "Indica el teléfono del propietario.",
            }
            for field, message in required.items():
                if not cleaned_data.get(field):
                    self.add_error(field, message)
            cost_type = cleaned_data.get("offered_cost_type")
            cost_amount = cleaned_data.get("offered_cost_amount")
            if cost_type and cost_type.requires_amount and not cost_amount:
                self.add_error(
                    "offered_cost_amount",
                    f"Indica el monto acordado para el tipo '{cost_type.name}'.",
                )
            if cost_type and not cost_type.requires_amount and cost_amount:
                self.add_error(
                    "offered_cost_amount",
                    "Este tipo de costo no permite registrar monto.",
                )

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
        if self.cleaned_data.get("offer_advertising") and self.cleaned_data.get("offered_advertisement_type"):
            PhysicalAdvertisement.objects.create(
                campaign=field_survey.campaign,
                advertisement_type=self.cleaned_data["offered_advertisement_type"],
                owner_name=self.cleaned_data.get("offered_owner_name", ""),
                owner_phone=self.cleaned_data.get("offered_owner_phone", ""),
                cost_type=self.cleaned_data.get("offered_cost_type"),
                cost_amount=self.cleaned_data.get("offered_cost_amount"),
                offered_notes=self.cleaned_data.get("offered_notes", ""),
                address=field_survey.address or self.cleaned_data.get("offered_owner_name", ""),
                reference=field_survey.reference,
                offered_latitude=field_survey.latitude,
                offered_longitude=field_survey.longitude,
                offered_photo=self.cleaned_data.get("offered_photo"),
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
        # ``brigadier`` is intentionally absent: stamped from the request
        # user via ``BrigadierAutoAssignMixin``. Address / reference are
        # also dropped — GPS already pinpoints the spot.
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop("brigadier", None)
        self.fields.pop("address", None)
        self.fields.pop("reference", None)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("latitude") in (None, ""):
            self.add_error("latitude", "La ubicación GPS es obligatoria.")
        if cleaned.get("longitude") in (None, ""):
            self.add_error("longitude", "La ubicación GPS es obligatoria.")
        return cleaned
