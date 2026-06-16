from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q
from django_select2.forms import ModelSelect2Widget, Select2Widget

from superadmin.forms import ModelForm

from core.widgets import LeafletMapWidget
from apps.campaigns.models import Campaign
from apps.field_surveys.models import AdvertisingType

from .models import (
    AdvertisingCostType,
    AdvertisingRefusal,
    AdvertisingTypeSize,
    PhysicalAdvertisement,
    PhysicalAdvertisementItem,
    PhysicalAdvertisementUnit,
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


class UnitConfigForm(forms.Form):
    """Configure ONE physical advertisement (unit): size + instructions.

    Used as the ``custom.form`` of the unit ``configure`` transition (PENDIENTE
    → CONFIGURADA): it only validates; the fields are written in the transition
    method from the POST kwargs (same contract as the other unit forms).
    """

    needs_object = True

    size = forms.ModelChoiceField(
        label="Tamaño",
        queryset=AdvertisingTypeSize.objects.none(),
        required=False,
        empty_label="Selecciona un tamaño…",
    )
    installation_instructions = forms.CharField(
        label="Indicaciones",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    def __init__(self, *args, obj=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.obj = obj
        ad_type = obj.item.advertisement_type if obj is not None else None
        sizes = (
            AdvertisingTypeSize.objects.filter(
                advertisement_type=ad_type, is_active=True
            ).order_by("order", "name")
            if ad_type is not None
            else AdvertisingTypeSize.objects.none()
        )
        self.fields["size"].queryset = sizes
        # Size is required only when the type actually has a size catalog.
        self.fields["size"].required = sizes.exists()
        # Pre-fill with the unit's current configuration so re-opening the form
        # edits the existing values instead of starting blank.
        if obj is not None:
            self.fields["size"].initial = obj.size_id
            self.fields["installation_instructions"].initial = (
                obj.installation_instructions
            )

class AddAdvertisementForm(forms.Form):
    """Add one new advertisement (type + quantity + size + instructions) to an
    existing request — usable even after approval (the new units are born
    PENDIENTE, ready to install).

    Used as the ``custom.form`` of the ``add_advertisement`` request
    transition: this form only validates; the units are created in the
    transition method from the POST kwargs (same contract as ``approve``).
    """

    needs_object = True

    advertisement_type = forms.ModelChoiceField(
        label="Tipo de publicidad",
        queryset=AdvertisingType.objects.none(),
        empty_label="Selecciona un tipo…",
    )
    quantity = forms.IntegerField(label="Cantidad", min_value=1, initial=1)
    size = forms.ModelChoiceField(
        label="Tamaño",
        queryset=AdvertisingTypeSize.objects.none(),
        required=False,
        empty_label="Sin tamaño / asignar luego",
    )
    instructions = forms.CharField(
        label="Indicaciones",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    assigned_installer = forms.ModelChoiceField(
        label="Instalador",
        queryset=get_user_model().objects.none(),
        required=False,
        empty_label="Sin instalador interno",
    )
    installer_team = forms.CharField(
        label="Instalador externo", max_length=180, required=False
    )

    def __init__(self, *args, obj=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.obj = obj
        self.fields["advertisement_type"].queryset = (
            obj.addable_advertisement_types
            if obj is not None
            else AdvertisingType.objects.none()
        )
        self.fields["size"].queryset = (
            obj.addable_advertisement_sizes
            if obj is not None
            else AdvertisingTypeSize.objects.none()
        )
        # The request is already approved when a publicidad is added (the
        # add_advertisement transition is only available from APROBADA onward),
        # and every publicidad needs an installer before the request can move to
        # installation — so ask who installs this new one right away.
        self.installer_required = obj is not None and obj.approved_at is not None
        if self.installer_required:
            self.fields["assigned_installer"].queryset = installer_users_queryset()
        else:
            del self.fields["assigned_installer"]
            del self.fields["installer_team"]

    def clean(self):
        cleaned = super().clean()
        type_obj = cleaned.get("advertisement_type")
        size = cleaned.get("size")
        if type_obj and size and size.advertisement_type_id != type_obj.pk:
            self.add_error("size", "El tamaño no corresponde al tipo elegido.")
        if (
            self.installer_required
            and not cleaned.get("assigned_installer")
            and not cleaned.get("installer_team")
        ):
            raise forms.ValidationError(
                "Selecciona un instalador o registra un instalador externo."
            )
        return cleaned


def installer_users_queryset():
    """Active users that can actually register installations.

    Filters by the ``install_physicaladvertisement`` permission (held
    directly, via a group, or implicitly as superuser) so coordinators
    can't assign someone who would later hit a 403 when installing.
    """
    has_perm = (
        Q(
            user_permissions__codename="install_physicaladvertisement",
            user_permissions__content_type__app_label="territorial_ads",
        )
        | Q(
            groups__permissions__codename="install_physicaladvertisement",
            groups__permissions__content_type__app_label="territorial_ads",
        )
        | Q(is_superuser=True)
    )
    return (
        get_user_model()
        .objects.filter(is_active=True)
        .filter(has_perm)
        .distinct()
        .order_by("first_name", "last_name", "username")
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        queryset = installer_users_queryset()
        field = self.fields["assigned_installer"]
        field.queryset = queryset
        if hasattr(field.widget, "queryset"):
            field.widget.queryset = queryset

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("assigned_installer") and not cleaned_data.get("installer_team"):
            raise forms.ValidationError("Selecciona un instalador o registra un instalador externo.")
        return cleaned_data


class BulkAssignInstallationForm(AssignInstallationForm):
    """Assign one installer to several approved advertisements at once."""

    advertisements = forms.ModelMultipleChoiceField(
        label="Publicidades aprobadas",
        queryset=PhysicalAdvertisement.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        error_messages={"required": "Selecciona al menos una publicidad."},
    )

    def __init__(self, *args, queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if queryset is not None:
            self.fields["advertisements"].queryset = queryset
        # The bulk modal renders the form manually (no select2 bootstrap),
        # so swap the AJAX widget for a plain select. Choices must be
        # re-bound by hand: ChoiceField only syncs them at __init__ time.
        installer_field = self.fields["assigned_installer"]
        plain_select = forms.Select(
            attrs={"class": "form-select form-select-sm form-select-solid"}
        )
        installer_field.widget = plain_select
        plain_select.choices = installer_field.choices
        self.fields["installer_team"].widget.attrs.update(
            {"class": "form-control form-control-sm form-control-solid"}
        )


class AssignUnitInstallerForm(forms.Form):
    """Assign an installer/team to ONE physical unit.

    Used as the ``custom.form`` of the ``assign_installer`` unit transition
    (CONFIGURADA → ASIGNADA). This form only validates; the fields are written
    in the transition method from the POST kwargs.
    """

    needs_object = True

    assigned_installer = forms.ModelChoiceField(
        label="Instalador",
        queryset=get_user_model().objects.none(),
        required=False,
        empty_label="Sin instalador interno",
    )
    installer_team = forms.CharField(
        label="Instalador externo", max_length=180, required=False
    )

    def __init__(self, *args, obj=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_installer"].queryset = installer_users_queryset()
        # Pre-fill the current installer so re-opening the form edits it.
        if obj is not None:
            self.fields["assigned_installer"].initial = obj.assigned_installer_id
            self.fields["installer_team"].initial = obj.installer_team

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("assigned_installer") and not cleaned_data.get(
            "installer_team"
        ):
            raise forms.ValidationError(
                "Selecciona un instalador o registra un instalador externo."
            )
        return cleaned_data


class UnitInstallForm(forms.Form):
    """Installation evidence for ONE physical unit: photo + GPS + notes."""

    needs_object = True

    photo = forms.ImageField(
        label="Foto de evidencia",
        required=True,
        help_text="Foto que verifica la instalación de esta publicidad.",
    )
    location = forms.CharField(
        label="Ubicación GPS",
        required=False,
        widget=LeafletMapWidget(
            lat_field="latitude",
            lng_field="longitude",
            attrs={"column": 12},
        ),
    )
    latitude = forms.DecimalField(
        max_digits=9,
        decimal_places=6,
        min_value=-90,
        max_value=90,
        required=False,
        widget=forms.HiddenInput(),
    )
    longitude = forms.DecimalField(
        max_digits=9,
        decimal_places=6,
        min_value=-180,
        max_value=180,
        required=False,
        widget=forms.HiddenInput(),
    )
    notes = forms.CharField(
        label="Notas de instalación",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    def __init__(self, *args, obj=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.obj = obj
        if obj is not None:
            self.fields["photo"].label = f"Foto — {obj.display_label}"
            # Pre-fill location + notes so re-opening edits the existing
            # evidence (the photo itself can't be pre-loaded into a file input).
            if obj.latitude is not None:
                self.fields["latitude"].initial = obj.latitude
            if obj.longitude is not None:
                self.fields["longitude"].initial = obj.longitude
            self.fields["notes"].initial = obj.notes

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("latitude") in (None, "") or cleaned_data.get(
            "longitude"
        ) in (None, ""):
            self.add_error(
                "location",
                "Marca la ubicación real de esta publicidad en el mapa o usa "
                "tu ubicación actual.",
            )
        return cleaned_data


class ContactUpdateForm(forms.Form):
    """Fix contact data without reopening a read-only workflow state."""

    needs_object = True

    owner_name = forms.CharField(label="Propietario / contacto", max_length=180)
    owner_phone = forms.CharField(label="Teléfono contacto", max_length=32)
    reference = forms.CharField(label="Referencia", max_length=255, required=False)

    def __init__(self, *args, obj=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.obj = obj
        if obj is not None:
            self.fields["owner_name"].initial = obj.owner_name
            self.fields["owner_phone"].initial = obj.owner_phone
            self.fields["reference"].initial = obj.reference


class TypeSizeSelect(forms.Select):
    """Select whose options expose ``data-type-id`` so the direct-install
    form can filter sizes client-side by the chosen advertising type."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._type_map = None

    def _type_lookup(self):
        if self._type_map is None:
            self._type_map = dict(
                AdvertisingTypeSize.objects.values_list("pk", "advertisement_type_id")
            )
        return self._type_map

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        raw = getattr(value, "value", value)
        try:
            pk = int(raw)
        except (TypeError, ValueError):
            return option
        type_id = self._type_lookup().get(pk)
        if type_id:
            option["attrs"]["data-type-id"] = str(type_id)
        return option


class DirectInstallForm(forms.Form):
    """Register an already-installed advertisement in one step.

    Creates a fast-tracked request (so contact data and audit trail are
    preserved) plus its installed unit with photo + GPS + notes.
    """

    campaign = forms.ModelChoiceField(
        label="Campaña",
        queryset=Campaign.objects.filter(is_active=True).order_by("-start_date", "name"),
    )
    address = forms.CharField(label="Dirección", max_length=255)
    reference = forms.CharField(label="Referencia", max_length=255, required=False)
    owner_name = forms.CharField(label="Propietario / contacto", max_length=180)
    owner_phone = forms.CharField(label="Teléfono contacto", max_length=32)
    advertisement_type = forms.ModelChoiceField(
        label="Tipo de publicidad",
        queryset=AdvertisingType.objects.filter(is_active=True).order_by("order", "name"),
        widget=forms.Select(attrs={"data-direct-type-select": "1"}),
    )
    size = forms.ModelChoiceField(
        label="Tamaño",
        queryset=AdvertisingTypeSize.objects.filter(is_active=True),
        required=False,
        widget=TypeSizeSelect(attrs={"data-direct-size-select": "1"}),
        help_text="Opcional: según el tipo seleccionado.",
    )
    photo = forms.ImageField(
        label="Foto de evidencia",
        required=True,
        help_text="Foto de la publicidad ya instalada.",
    )
    notes = forms.CharField(
        label="Notas de instalación",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    location = forms.CharField(
        label="Ubicación en mapa",
        required=False,
        widget=LeafletMapWidget(
            lat_field="latitude",
            lng_field="longitude",
            attrs={"column": 12},
        ),
    )
    latitude = forms.DecimalField(
        max_digits=9,
        decimal_places=6,
        min_value=-90,
        max_value=90,
        required=False,
        widget=forms.HiddenInput(),
    )
    longitude = forms.DecimalField(
        max_digits=9,
        decimal_places=6,
        min_value=-180,
        max_value=180,
        required=False,
        widget=forms.HiddenInput(),
    )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("latitude") in (None, "") or cleaned_data.get(
            "longitude"
        ) in (None, ""):
            self.add_error(
                "location",
                "Marca la ubicación de la publicidad en el mapa o usa tu "
                "ubicación actual.",
            )
        size = cleaned_data.get("size")
        ad_type = cleaned_data.get("advertisement_type")
        if size and ad_type and size.advertisement_type_id != ad_type.pk:
            self.add_error("size", "El tamaño no corresponde al tipo seleccionado.")
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


class DiscardUnitForm(forms.Form):
    """Reason a physical unit won't be installed (optional)."""

    notes = forms.CharField(
        label="Motivo (opcional)",
        help_text="Ej.: no se necesitó, no había espacio, el dueño se retractó.",
        widget=forms.Textarea(attrs={"rows": 2}),
        required=False,
    )
