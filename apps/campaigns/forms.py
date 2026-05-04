"""Forms de la app campaigns."""
from superadmin.forms import ModelForm

from core.forms import Select2ModelFormMixin

from .models import Campaign, Candidate, Election, PoliticalMovement, Position


class ElectionForm(ModelForm):
    class Meta:
        model = Election
        fieldsets = {
            "Elección": (
                ("name", "election_date"),
                ("description",),
            ),
        }


class PoliticalMovementForm(ModelForm):
    class Meta:
        model = PoliticalMovement
        fieldsets = {
            "Movimiento": (
                ("name", "acronym"),
                ("list_number", "color"),
                ("logo",),
            ),
        }


class PositionForm(ModelForm):
    class Meta:
        model = Position
        fieldsets = {
            "Cargo": (
                ("name", "scope"),
            ),
        }


class CandidateForm(ModelForm):
    class Meta:
        model = Candidate
        fieldsets = {
            "Datos personales": (
                ("full_name", "identification"),
                ("email", "phone"),
                ("photo",),
            ),
            "Biografía": (
                ("bio",),
            ),
        }


class CampaignForm(Select2ModelFormMixin, ModelForm):
    class Meta:
        model = Campaign
        fieldsets = {
            "Identificación": (
                ("name",),
                ("election", "candidate"),
                ("movement", "position"),
            ),
            "Vigencia": (
                ("start_date", "end_date"),
            ),
            "Detalle": (
                ("description",),
            ),
        }
        select2_fields = {
            "election": {
                "model": Election,
                "search_fields": ["name__icontains"],
            },
            "candidate": {
                "model": Candidate,
                "search_fields": [
                    "full_name__icontains",
                    "identification__icontains",
                    "email__icontains",
                ],
            },
            "movement": {
                "model": PoliticalMovement,
                "search_fields": [
                    "name__icontains",
                    "acronym__icontains",
                    "list_number__icontains",
                ],
            },
            "position": {
                "model": Position,
                "search_fields": [
                    "name__icontains",
                    "scope__icontains",
                ],
            },
        }
