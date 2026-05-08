from django import forms
from django_select2.forms import ModelSelect2Widget, Select2Widget
from superadmin.forms import ModelForm

from apps.campaigns.models import Campaign
from apps.locations.models import Canton, Parish, Province, Sector
from core.widgets import LeafletMapWidget

from .models import AgendaEventType, PoliticalAgendaEvent, PoliticalAgendaRequest


class RejectAgendaRequestForm(forms.Form):
    rejection_reason = forms.CharField(
        label="Motivo de rechazo",
        widget=forms.Textarea(attrs={"rows": 3}),
        required=True,
    )


class PoliticalAgendaRequestForm(ModelForm):
    location = forms.CharField(
        label="Ubicación tentativa en mapa",
        required=False,
        widget=LeafletMapWidget(
            lat_field="latitude",
            lng_field="longitude",
            attrs={"column": 12},
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "event_type" in self.fields:
            active_types = AgendaEventType.objects.filter(is_active=True).order_by("order", "name")
            self.fields["event_type"].queryset = active_types
            self.fields["event_type"].widget.queryset = active_types

    class Meta:
        model = PoliticalAgendaRequest
        fieldsets = {
            "Solicitud": (
                ("campaign", "title"),
                ("event_type",),
                ("priority",),
            ),
            "Solicitante": (
                ("requester_name", "requester_phone"),
                ("requester_email", "organization"),
            ),
            "Fecha tentativa": (
                ("proposed_start_at", "proposed_end_at"),
                ("alternative_dates",),
            ),
            "Ubicación tentativa": (
                ("province", "canton"),
                ("parish", "sector"),
                ("address",),
                ("reference",),
                ("location",),
                ("latitude", "longitude"),
            ),
            "Detalle": (
                ("objective",),
                ("expected_attendees",),
                ("notes",),
            ),
            "Revisión": (
                ("reviewed_by", "reviewed_at"),
                ("rejection_reason",),
            ),
        }
        widgets = {
            "campaign": ModelSelect2Widget(
                model=Campaign,
                search_fields=["name__icontains", "candidate__full_name__icontains"],
                max_results=100,
                attrs={"data-minimum-input-length": 0, "data-app": "campaigns", "data-model": "Campaign"},
            ),
            "event_type": ModelSelect2Widget(
                model=AgendaEventType,
                search_fields=["name__icontains", "code__icontains"],
                max_results=100,
                attrs={"data-minimum-input-length": 0, "data-app": "political_agenda", "data-model": "AgendaEventType"},
            ),
            "province": ModelSelect2Widget(
                model=Province,
                search_fields=["name__icontains", "code__icontains"],
                max_results=100,
                attrs={"data-minimum-input-length": 0, "data-app": "locations", "data-model": "Province"},
            ),
            "canton": ModelSelect2Widget(
                model=Canton,
                search_fields=["name__icontains", "province__name__icontains"],
                dependent_fields={"province": "province"},
                max_results=100,
                attrs={"data-minimum-input-length": 0, "data-app": "locations", "data-model": "Canton"},
            ),
            "parish": ModelSelect2Widget(
                model=Parish,
                search_fields=["name__icontains", "canton__name__icontains"],
                dependent_fields={"canton": "canton"},
                max_results=100,
                attrs={"data-minimum-input-length": 0, "data-app": "locations", "data-model": "Parish"},
            ),
            "sector": ModelSelect2Widget(
                model=Sector,
                search_fields=["name__icontains", "parish__name__icontains"],
                dependent_fields={"parish": "parish"},
                max_results=100,
                attrs={"data-minimum-input-length": 0, "data-app": "locations", "data-model": "Sector"},
            ),
            "priority": Select2Widget(attrs={"data-minimum-input-length": 0}),
            "proposed_start_at": forms.DateTimeInput(),
            "proposed_end_at": forms.DateTimeInput(),
            "reviewed_at": forms.DateTimeInput(),
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
        }


class PoliticalAgendaEventForm(ModelForm):
    location = forms.CharField(
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
        if "event_type" in self.fields:
            active_types = AgendaEventType.objects.filter(is_active=True).order_by("order", "name")
            self.fields["event_type"].queryset = active_types
            self.fields["event_type"].widget.queryset = active_types

    class Meta:
        model = PoliticalAgendaEvent
        fieldsets = {
            "Evento": (
                ("campaign", "source_request"),
                ("title", "event_type"),
                ("start_at", "end_at"),
            ),
            "Ubicación": (
                ("province", "canton"),
                ("parish", "sector"),
                ("address",),
                ("reference",),
                ("location",),
                ("latitude", "longitude"),
            ),
            "Organización": (
                ("organizer_name", "organizer_phone"),
                ("responsible", "expected_attendees"),
            ),
            "Detalle": (
                ("objective",),
                ("logistics_notes",),
                ("result_notes",),
            ),
        }
        widgets = {
            "campaign": ModelSelect2Widget(
                model=Campaign,
                search_fields=["name__icontains", "candidate__full_name__icontains"],
                max_results=100,
                attrs={"data-minimum-input-length": 0, "data-app": "campaigns", "data-model": "Campaign"},
            ),
            "event_type": ModelSelect2Widget(
                model=AgendaEventType,
                search_fields=["name__icontains", "code__icontains"],
                max_results=100,
                attrs={"data-minimum-input-length": 0, "data-app": "political_agenda", "data-model": "AgendaEventType"},
            ),
            "source_request": ModelSelect2Widget(
                model=PoliticalAgendaRequest,
                search_fields=["title__icontains", "requester_name__icontains", "organization__icontains"],
                dependent_fields={"campaign": "campaign"},
                max_results=100,
                attrs={"data-minimum-input-length": 0, "data-app": "political_agenda", "data-model": "PoliticalAgendaRequest"},
            ),
            "province": ModelSelect2Widget(
                model=Province,
                search_fields=["name__icontains", "code__icontains"],
                max_results=100,
                attrs={"data-minimum-input-length": 0, "data-app": "locations", "data-model": "Province"},
            ),
            "canton": ModelSelect2Widget(
                model=Canton,
                search_fields=["name__icontains", "province__name__icontains"],
                dependent_fields={"province": "province"},
                max_results=100,
                attrs={"data-minimum-input-length": 0, "data-app": "locations", "data-model": "Canton"},
            ),
            "parish": ModelSelect2Widget(
                model=Parish,
                search_fields=["name__icontains", "canton__name__icontains"],
                dependent_fields={"canton": "canton"},
                max_results=100,
                attrs={"data-minimum-input-length": 0, "data-app": "locations", "data-model": "Parish"},
            ),
            "sector": ModelSelect2Widget(
                model=Sector,
                search_fields=["name__icontains", "parish__name__icontains"],
                dependent_fields={"parish": "parish"},
                max_results=100,
                attrs={"data-minimum-input-length": 0, "data-app": "locations", "data-model": "Sector"},
            ),
            "start_at": forms.DateTimeInput(),
            "end_at": forms.DateTimeInput(),
            "latitude": forms.HiddenInput(),
            "longitude": forms.HiddenInput(),
        }
