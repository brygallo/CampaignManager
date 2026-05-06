from django import forms
from django.contrib.auth import get_user_model
from django_select2.forms import ModelSelect2Widget, Select2Widget

from superadmin.forms import ModelForm

from core.widgets import LeafletMapWidget
from apps.campaigns.models import Campaign

from .models import AdvertisingCostType, PhysicalAdvertisement


class CostTypeSelect2Widget(Select2Widget):
    """Select2 widget that exposes ``requires_amount`` as a data attribute per option."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._requires_amount_map = None

    def _requires_amount_lookup(self):
        if self._requires_amount_map is None:
            self._requires_amount_map = dict(
                AdvertisingCostType.objects.values_list("pk", "requires_amount")
            )
        return self._requires_amount_map

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        raw = getattr(value, "value", value)
        try:
            pk = int(raw)
        except (TypeError, ValueError):
            return option
        flags = self._requires_amount_lookup()
        if pk in flags:
            option["attrs"]["data-requires-amount"] = "1" if flags[pk] else "0"
        return option


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "campaign" in self.fields:
            active_campaigns = Campaign.objects.filter(is_active=True).order_by(
                "-start_date", "name"
            )
            self.fields["campaign"].queryset = active_campaigns
            self.fields["campaign"].widget.queryset = active_campaigns

    class Meta:
        model = PhysicalAdvertisement
        fieldsets = {
            "Publicidad": (
                ("campaign", "advertisement_type"),
                ("quantity",),
            ),
            "Contacto que ofreció el lugar": (
                ("owner_name", "owner_phone"),
                ("cost_type", "cost_amount"),
                ("offered_notes",),
            ),
            "Ubicación ofrecida": (
                ("address",),
                ("reference",),
                ("offered_location",),
                ("offered_latitude", "offered_longitude"),
                ("offered_photo",),
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
            "cost_type": CostTypeSelect2Widget(
                attrs={
                    "data-minimum-input-length": 0,
                    "data-cost-type-select": "1",
                },
            ),
            "cost_amount": forms.NumberInput(
                attrs={
                    "data-cost-amount-input": "1",
                    "step": "0.01",
                    "min": "0",
                },
            ),
            "offered_latitude": forms.HiddenInput(),
            "offered_longitude": forms.HiddenInput(),
        }

    def clean(self):
        cleaned_data = super().clean()
        cost_type = cleaned_data.get("cost_type")
        cost_amount = cleaned_data.get("cost_amount")
        requires_amount = bool(cost_type and cost_type.requires_amount)
        if requires_amount and not cost_amount:
            self.add_error(
                "cost_amount",
                f"Indica el monto acordado para el tipo '{cost_type.name}'.",
            )
        if not requires_amount and cost_amount:
            self.add_error(
                "cost_amount",
                "Este tipo de costo no permite registrar monto.",
            )
        return cleaned_data


class ApprovalForm(forms.Form):
    width_meters = forms.DecimalField(
        label="Ancho (m)",
        max_digits=6,
        decimal_places=2,
        min_value=0,
        required=True,
    )
    height_meters = forms.DecimalField(
        label="Alto (m)",
        max_digits=6,
        decimal_places=2,
        min_value=0,
        required=True,
    )
    installation_instructions = forms.CharField(
        label="Instrucciones para instalación",
        help_text="Indica qué se requiere: escalera, andamio, permisos, etc.",
        widget=forms.Textarea(attrs={"rows": 3}),
        required=True,
    )


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


class RejectPhysicalAdForm(forms.Form):
    rejection_reason = forms.CharField(
        label="Motivo de rechazo",
        help_text="Detalla por qué no se acepta esta oferta.",
        widget=forms.Textarea(attrs={"rows": 3}),
        required=True,
    )


class RetirementForm(forms.Form):
    retirement_notes = forms.CharField(
        label="Notas de retiro",
        widget=forms.Textarea,
        required=True,
    )
    retirement_photo = forms.ImageField(label="Foto del retiro", required=False)
