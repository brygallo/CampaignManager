from django import forms
from django_select2.forms import ModelSelect2Widget, Select2Widget
from superadmin.forms import ModelForm

from apps.campaigns.models import Campaign

from .models import PoliticalAgendaEvent, PoliticalAgendaRequest


class RejectAgendaRequestForm(forms.Form):
    rejection_reason = forms.CharField(
        label="Motivo de rechazo",
        widget=forms.Textarea(attrs={"rows": 3}),
        required=True,
    )


class PoliticalAgendaRequestForm(ModelForm):
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
            "event_type": Select2Widget(attrs={"data-minimum-input-length": 0}),
            "priority": Select2Widget(attrs={"data-minimum-input-length": 0}),
            "proposed_start_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "proposed_end_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "reviewed_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class PoliticalAgendaEventForm(ModelForm):
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
            "source_request": ModelSelect2Widget(
                model=PoliticalAgendaRequest,
                search_fields=["title__icontains", "requester_name__icontains", "organization__icontains"],
                max_results=100,
                attrs={"data-minimum-input-length": 0, "data-app": "political_agenda", "data-model": "PoliticalAgendaRequest"},
            ),
            "event_type": Select2Widget(attrs={"data-minimum-input-length": 0}),
            "start_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "end_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }
