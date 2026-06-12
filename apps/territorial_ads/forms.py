from django import forms
from django.contrib.auth import get_user_model
from django_select2.forms import ModelSelect2Widget, Select2Widget

from superadmin.forms import ModelForm

from core.widgets import LeafletMapWidget
from apps.campaigns.models import Campaign
from apps.field_surveys.models import AdvertisingType

from .models import (
    AdvertisingCostType,
    AdvertisingRefusal,
    PhysicalAdvertisement,
    PhysicalAdvertisementItem,
)


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


class PhysicalAdvertisementItemForm(forms.ModelForm):
    """Row form for the items inline: one advertising type + quantity."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        active_types = AdvertisingType.objects.filter(is_active=True).order_by(
            "order", "name"
        )
        self.fields["advertisement_type"].queryset = active_types
        self.fields["quantity"].min_value = 1
        self.fields["quantity"].widget.attrs.update({"min": 1, "step": 1})

    class Meta:
        model = PhysicalAdvertisementItem
        fields = ("advertisement_type", "quantity")


PhysicalAdvertisementItemFormSet = forms.inlineformset_factory(
    PhysicalAdvertisement,
    PhysicalAdvertisementItem,
    form=PhysicalAdvertisementItemForm,
    extra=1,
    min_num=1,
    validate_min=True,
    can_delete=True,
)


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
            "Ubicación ofrecida": (
                ("offered_location",),
                ("address",),
                ("reference",),
                ("offered_latitude", "offered_longitude"),
                ("offered_photo",),
            ),
            "Publicidad": (
                ("campaign",),
            ),
            "Contacto que ofreció el lugar": (
                ("owner_name", "owner_phone"),
                ("cost_type", "cost_amount"),
                ("offered_notes",),
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
        if cleaned_data.get("offered_latitude") in (None, "") or cleaned_data.get(
            "offered_longitude"
        ) in (None, ""):
            self.add_error(
                "offered_location",
                "Marca el lugar ofrecido en el mapa o usa tu ubicación actual.",
            )
        return cleaned_data


class AdvertisingRefusalForm(ModelForm):
    """Minimal form to log a place where the owner refuses advertising.

    Coordinates come from the map click (hidden inputs); the user only fills
    the reason and an optional owner reference.
    """

    refusal_location = forms.CharField(
        label="Ubicación en mapa",
        required=False,
        widget=LeafletMapWidget(
            lat_field="latitude",
            lng_field="longitude",
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
        model = AdvertisingRefusal
        fieldsets = {
            "Ubicación": (
                ("refusal_location",),
                ("latitude", "longitude"),
            ),
            "Detalle del rechazo": (
                ("campaign",),
                ("owner_reference",),
                ("reason",),
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
            "reason": forms.Textarea(attrs={"rows": 3}),
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
        }

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("latitude") in (None, "") or cleaned_data.get(
            "longitude"
        ) in (None, ""):
            self.add_error(
                "refusal_location",
                "Marca el lugar en el mapa o usa tu ubicación actual.",
            )
        return cleaned_data


class ApprovalForm(forms.Form):
    # ChangeStateView passes the advertisement so one instructions textarea
    # can be built per registered advertising type.
    needs_object = True

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

    def __init__(self, *args, obj=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.obj = obj
        items = (
            obj.items.select_related("advertisement_type") if obj is not None else []
        )
        for item in items:
            self.fields[f"item_instructions_{item.pk}"] = forms.CharField(
                label=f"Indicaciones — {item.quantity}× {item.advertisement_type.name}",
                help_text="Indica qué se requiere: escalera, andamio, permisos, etc.",
                widget=forms.Textarea(attrs={"rows": 2}),
                required=True,
                initial=item.installation_instructions,
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
    installer_team = forms.CharField(label="Instalador externo", max_length=180, required=False)

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("assigned_installer") and not cleaned_data.get("installer_team"):
            raise forms.ValidationError("Selecciona un instalador o registra un instalador externo.")
        return cleaned_data


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    """ImageField that accepts several files from one ``multiple`` input."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_clean(item, initial) for item in data]
        return [single_clean(data, initial)]


class InstallationEvidenceForm(forms.Form):
    # ChangeStateView passes the advertisement so the photo count can be
    # validated against the total of installed units.
    needs_object = True

    installation_photos = MultipleImageField(
        label="Fotos de evidencia",
        required=True,
        help_text="Sube una foto por cada unidad instalada.",
    )
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
        required=False,
        widget=forms.HiddenInput(),
    )
    installed_longitude = forms.DecimalField(
        label="Longitud GPS real",
        max_digits=9,
        decimal_places=6,
        min_value=-180,
        max_value=180,
        required=False,
        widget=forms.HiddenInput(),
    )
    installation_notes = forms.CharField(
        label="Notas de instalación",
        widget=forms.Textarea,
        required=False,
    )

    def __init__(self, *args, obj=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.obj = obj
        if obj is not None:
            total = obj.total_units
            self.fields["installation_photos"].help_text = (
                f"Sube exactamente {total} foto(s): una por cada unidad instalada "
                f"({obj.items_summary})."
            )

    def clean(self):
        cleaned_data = super().clean()
        photos = cleaned_data.get("installation_photos") or []
        if self.obj is not None and photos:
            total = self.obj.total_units
            if len(photos) != total:
                self.add_error(
                    "installation_photos",
                    f"Debes subir exactamente {total} foto(s): una por cada unidad "
                    f"instalada (subiste {len(photos)}).",
                )
        if cleaned_data.get("installed_latitude") in (None, "") or cleaned_data.get(
            "installed_longitude"
        ) in (None, ""):
            self.add_error(
                "installation_location",
                "Marca la ubicación real de instalación en el mapa o usa tu ubicación actual.",
            )
        return cleaned_data


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
