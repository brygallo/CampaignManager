from django import forms
from django.contrib.auth import get_user_model
from django_select2.forms import ModelSelect2Widget, Select2Widget

from superadmin.forms import ModelForm

from core.widgets import LeafletMapWidget
from apps.campaigns.models import Campaign

from .models import PhysicalAdvertisement


class PhysicalAdvertisementForm(ModelForm):
    offered_location = forms.CharField(
        label="Ubicación en mapa",
        required=False,
        widget=LeafletMapWidget(
            lat_field="offered_latitude",
            lng_field="offered_longitude",
            attrs={"column": 12},
        ),
    )

    class Meta:
        model = PhysicalAdvertisement
        fieldsets = {
            "Publicidad": (
                ("campaign", "advertisement_type"),
                ("title", "quantity"),
                ("width_meters", "height_meters"),
            ),
            "Contacto que ofreció el lugar": (
                ("owner_name", "owner_phone"),
                ("offered_notes",),
            ),
            "Ubicación ofrecida": (
                ("province", "canton"),
                ("parish", "sector"),
                ("address",),
                ("reference",),
                ("offered_location",),
                ("offered_latitude", "offered_longitude"),
            ),
        }
        widgets = {
            "campaign": ModelSelect2Widget(
                model=Campaign,
                search_fields=[
                    "name__icontains",
                    "candidate__full_name__icontains",
                    "election__name__icontains",
                ],
                max_results=100,
                attrs={
                    "data-minimum-input-length": 0,
                    "data-app": "campaigns",
                    "data-model": "Campaign",
                },
            ),
            "advertisement_type": Select2Widget(
                attrs={
                    "data-minimum-input-length": 0,
                },
            ),
            "offered_latitude": forms.HiddenInput(),
            "offered_longitude": forms.HiddenInput(),
        }


class AssignInstallationForm(forms.Form):
    assigned_installer = forms.ModelChoiceField(
        label="Instalador",
        queryset=get_user_model().objects.filter(is_active=True).order_by(
            "first_name", "last_name", "username"
        ),
        required=False,
        widget=ModelSelect2Widget(
            model="authentication.User",
            search_fields=[
                "first_name__icontains",
                "last_name__icontains",
                "username__icontains",
                "email__icontains",
            ],
            max_results=100,
            attrs={
                "data-minimum-input-length": 0,
                "data-app": "authentication",
                "data-model": "User",
            },
        ),
    )
    installer_team = forms.CharField(label="Equipo instalador", max_length=180, required=False)

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("assigned_installer") and not cleaned_data.get("installer_team"):
            raise forms.ValidationError("Selecciona un instalador o registra un equipo instalador.")
        return cleaned_data


class InstallationEvidenceForm(forms.Form):
    installation_photo = forms.ImageField(label="Foto de evidencia", required=True)
    installation_location = forms.CharField(
        label="Ubicación GPS de instalación",
        required=False,
        widget=LeafletMapWidget(
            lat_field="installed_latitude",
            lng_field="installed_longitude",
            attrs={"column": 12},
        ),
    )
    installed_latitude = forms.DecimalField(
        label="Latitud GPS real",
        max_digits=9,
        decimal_places=6,
        min_value=-90,
        max_value=90,
        required=True,
        widget=forms.HiddenInput(),
    )
    installed_longitude = forms.DecimalField(
        label="Longitud GPS real",
        max_digits=9,
        decimal_places=6,
        min_value=-180,
        max_value=180,
        required=True,
        widget=forms.HiddenInput(),
    )
    installation_notes = forms.CharField(
        label="Notas de instalación",
        widget=forms.Textarea,
        required=False,
    )


class DamageReportForm(forms.Form):
    damage_notes = forms.CharField(
        label="Detalle del daño",
        widget=forms.Textarea,
        required=True,
    )
    damage_photo = forms.ImageField(label="Foto del daño", required=False)


class RetirementForm(forms.Form):
    retirement_notes = forms.CharField(
        label="Notas de retiro",
        widget=forms.Textarea,
        required=True,
    )
    retirement_photo = forms.ImageField(label="Foto del retiro", required=False)
