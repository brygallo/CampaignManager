from django import forms
from django.db.models import Q
from superadmin.forms import ModelForm

from apps.locations.models import Parish
from core.widgets import LeafletMapWidget

from .models import (
    ElectoralCandidateOption,
    ElectoralDignity,
    ElectoralDistrict,
    ElectoralResultReport,
    ElectoralTable,
    ElectoralTableAssignment,
    ElectoralVenue,
)


class ElectoralDignityForm(ModelForm):
    class Meta:
        model = ElectoralDignity
        fieldsets = {
            "Dignidad": (
                ("name", "order"),
                ("scope", "parish_kind_rule"),
                ("seats", "is_active"),
            ),
        }


class ElectoralDistrictForm(ModelForm):
    class Meta:
        model = ElectoralDistrict
        fieldsets = {
            "Circunscripción": (
                ("dignity", "name"),
                ("kind", "order"),
                ("province", "canton"),
                ("parishes",),
                ("seats", "is_active"),
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        dignity = cleaned_data.get("dignity")
        province = cleaned_data.get("province")
        canton = cleaned_data.get("canton")
        parishes = cleaned_data.get("parishes")
        if not dignity:
            return cleaned_data

        if dignity.scope == ElectoralDignity.Scope.PROVINCE and not province:
            self.add_error("province", "La circunscripción provincial requiere provincia.")
        if dignity.scope == ElectoralDignity.Scope.CANTON and not canton:
            self.add_error("canton", "La circunscripción cantonal requiere cantón.")
        if dignity.scope in {ElectoralDignity.Scope.DISTRICT, ElectoralDignity.Scope.PARISH}:
            parish_count = parishes.count() if parishes is not None else 0
            if parish_count == 0:
                self.add_error("parishes", "Agrega al menos una parroquia.")
            if dignity.scope == ElectoralDignity.Scope.PARISH and parish_count != 1:
                self.add_error(
                    "parishes",
                    "Las dignidades parroquiales deben configurarse con una sola parroquia.",
                )
            if parishes is not None:
                for parish in parishes:
                    if not parish_matches_dignity_rule(parish, dignity):
                        self.add_error(
                            "parishes",
                            "Las parroquias seleccionadas no cumplen la regla urbana/rural de la dignidad.",
                        )
                        break
        return cleaned_data


class ElectoralCandidateOptionForm(ModelForm):
    class Meta:
        model = ElectoralCandidateOption
        fieldsets = {
            "Candidatura": (
                ("district",),
                ("list_code", "candidate_name"),
                ("order", "is_active"),
            ),
        }


class ElectoralVenueForm(ModelForm):
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
        model = ElectoralVenue
        fieldsets = {
            "Recinto electoral": (
                ("parish",),
                ("location",),
                ("latitude", "longitude"),
                ("name", "is_active"),
            ),
        }


class ElectoralTableForm(ModelForm):
    class Meta:
        model = ElectoralTable
        fieldsets = {
            "Mesa electoral": (
                ("venue",),
                ("number", "gender"),
                ("registered_voters", "is_active"),
            ),
        }


class ElectoralTableAssignmentForm(ModelForm):
    class Meta:
        model = ElectoralTableAssignment
        fieldsets = {
            "Asignación": (
                ("table", "watcher"),
                ("notes",),
                ("is_active",),
            ),
        }


class ElectoralResultReportForm(ModelForm):
    class Meta:
        model = ElectoralResultReport
        fieldsets = {
            "Acta": (
                ("parish", "venue"),
                ("table", "dignity"),
                ("district", "watcher"),
                ("status", "voters_count"),
                ("evidence_file",),
                ("validation_notes",),
                ("is_active",),
            ),
        }


def parish_matches_dignity_rule(parish, dignity):
    if dignity.parish_kind_rule == ElectoralDignity.ParishKindRule.ALL:
        return True
    if dignity.parish_kind_rule == ElectoralDignity.ParishKindRule.URBAN:
        return parish.kind == Parish.ParishKind.URBANA
    if dignity.parish_kind_rule == ElectoralDignity.ParishKindRule.RURAL:
        return parish.kind == Parish.ParishKind.RURAL
    return False


def electoral_districts_for_parish(parish, dignity=None):
    allowed_kind_rules = [ElectoralDignity.ParishKindRule.ALL]
    if parish.kind == Parish.ParishKind.URBANA:
        allowed_kind_rules.append(ElectoralDignity.ParishKindRule.URBAN)
    if parish.kind == Parish.ParishKind.RURAL:
        allowed_kind_rules.append(ElectoralDignity.ParishKindRule.RURAL)

    queryset = ElectoralDistrict.objects.filter(
        is_active=True,
        dignity__is_active=True,
        dignity__parish_kind_rule__in=allowed_kind_rules,
    )
    if dignity is not None:
        if not parish_matches_dignity_rule(parish, dignity):
            return ElectoralDistrict.objects.none()
        queryset = queryset.filter(dignity=dignity)

    return (
        queryset.filter(
            Q(dignity__scope=ElectoralDignity.Scope.PROVINCE, province=parish.canton.province)
            | Q(dignity__scope=ElectoralDignity.Scope.CANTON, canton=parish.canton)
            | Q(
                dignity__scope__in=[
                    ElectoralDignity.Scope.DISTRICT,
                    ElectoralDignity.Scope.PARISH,
                ],
                parishes=parish,
            )
        )
        .select_related("dignity", "province", "canton")
        .prefetch_related("parishes")
        .distinct()
        .order_by("dignity__order", "order", "name")
    )


def resolve_electoral_district(*, parish_id, dignity_id):
    try:
        parish = Parish.objects.select_related("canton__province").get(pk=parish_id)
        dignity = ElectoralDignity.objects.get(pk=dignity_id)
    except (Parish.DoesNotExist, ElectoralDignity.DoesNotExist, ValueError, TypeError):
        return None
    districts = list(electoral_districts_for_parish(parish, dignity))
    if len(districts) != 1:
        return None
    return districts[0]


class ElectoralWatcherForm(forms.Form):
    parish = forms.ModelChoiceField(
        label="Parroquia",
        queryset=Parish.objects.none(),
        widget=forms.Select(attrs={"class": "form-select form-select-solid"}),
    )
    venue = forms.ModelChoiceField(
        label="Recinto electoral",
        queryset=ElectoralVenue.objects.none(),
        widget=forms.Select(attrs={"class": "form-select form-select-solid"}),
    )
    table = forms.ModelChoiceField(
        label="Mesa",
        queryset=ElectoralTable.objects.none(),
        widget=forms.Select(attrs={"class": "form-select form-select-solid"}),
    )
    dignity = forms.ModelChoiceField(
        label="Dignidad a elegir",
        queryset=ElectoralDignity.objects.none(),
        widget=forms.Select(attrs={"class": "form-select form-select-solid"}),
    )
    voters_count = forms.IntegerField(
        label="Sufragantes",
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={"class": "form-control form-control-solid", "min": 0}),
    )
    blank_votes = forms.IntegerField(
        label="Votos blancos",
        min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={"class": "form-control form-control-solid", "min": 0}),
    )
    null_votes = forms.IntegerField(
        label="Votos nulos",
        min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={"class": "form-control form-control-solid", "min": 0}),
    )
    evidence_file = forms.FileField(
        label="Foto/PDF del acta",
        required=False,
        widget=forms.FileInput(
            attrs={
                "class": "form-control form-control-solid",
                "accept": "image/*,application/pdf",
            }
        ),
    )

    def __init__(self, *args, watcher=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.watcher = watcher
        values = self.data if self.is_bound else self.initial
        assigned_tables = ElectoralTable.objects.filter(is_active=True)
        if watcher is not None:
            assigned_tables = assigned_tables.filter(
                assignments__watcher=watcher,
                assignments__is_active=True,
            )
        self.fields["parish"].queryset = (
            Parish.objects.filter(vote_venues__tables__in=assigned_tables, is_active=True)
            .distinct()
            .order_by("canton__name", "name")
        )
        parish_id = values.get("parish")
        venue_id = values.get("venue")
        dignity_id = values.get("dignity")
        if parish_id:
            self.fields["venue"].queryset = ElectoralVenue.objects.filter(
                parish_id=parish_id,
                tables__in=assigned_tables,
                is_active=True,
            ).distinct().order_by("name")
            self.fields["dignity"].queryset = self._dignities_for_parish_id(parish_id)
        if venue_id:
            self.fields["table"].queryset = ElectoralTable.objects.filter(
                venue_id=venue_id,
                pk__in=assigned_tables.values("pk"),
                is_active=True,
            ).order_by("number", "gender")
        self.candidate_options = ElectoralCandidateOption.objects.none()
        self.district = None
        if parish_id and dignity_id:
            self.district = resolve_electoral_district(
                parish_id=parish_id, dignity_id=dignity_id
            )
            if self.district:
                self.candidate_options = self.district.candidate_options.filter(
                    is_active=True
                ).order_by("order", "list_code", "candidate_name")
                for option in self.candidate_options:
                    self.fields[self.vote_field_name(option)] = forms.IntegerField(
                        label=f"{option.list_code} - {option.candidate_name}",
                        min_value=0,
                        initial=0,
                        widget=forms.NumberInput(
                            attrs={"class": "form-control form-control-solid", "min": 0}
                        ),
                    )

    @staticmethod
    def vote_field_name(option):
        return f"candidate_{option.pk}"

    def _dignities_for_parish_id(self, parish_id):
        try:
            parish = Parish.objects.select_related("canton__province").get(pk=parish_id)
        except (Parish.DoesNotExist, ValueError, TypeError):
            return ElectoralDignity.objects.none()
        districts = electoral_districts_for_parish(parish)
        return (
            ElectoralDignity.objects.filter(districts__in=districts, is_active=True)
            .distinct()
            .order_by("order", "name")
        )

    def clean(self):
        cleaned_data = super().clean()
        parish = cleaned_data.get("parish")
        venue = cleaned_data.get("venue")
        table = cleaned_data.get("table")
        dignity = cleaned_data.get("dignity")
        if venue and parish and venue.parish_id != parish.pk:
            self.add_error("venue", "El recinto no pertenece a la parroquia seleccionada.")
        if table and venue and table.venue_id != venue.pk:
            self.add_error("table", "La mesa no pertenece al recinto seleccionado.")
        if table and self.watcher is not None and not ElectoralTableAssignment.objects.filter(
            table=table,
            watcher=self.watcher,
            is_active=True,
        ).exists():
            self.add_error("table", "No tienes asignada esta mesa electoral.")
        if parish and dignity:
            districts = list(electoral_districts_for_parish(parish, dignity))
            if not districts:
                self.add_error("dignity", "No existe una circunscripción configurada para esta parroquia.")
            elif len(districts) > 1:
                self.add_error(
                    "dignity",
                    "Hay más de una circunscripción activa para esta parroquia y dignidad.",
                )
            else:
                self.district = districts[0]
        if self.district and not self.candidate_options.exists():
            self.add_error("dignity", "La circunscripción no tiene candidaturas activas.")
        if self.candidate_options.exists() and cleaned_data.get("voters_count") is not None:
            candidate_votes = sum(
                cleaned_data.get(self.vote_field_name(option)) or 0
                for option in self.candidate_options
            )
            total_votes = candidate_votes + (cleaned_data.get("blank_votes") or 0) + (
                cleaned_data.get("null_votes") or 0
            )
            if total_votes != cleaned_data["voters_count"]:
                self.add_error(
                    "voters_count",
                    "Los votos de candidatos, blancos y nulos deben cuadrar con sufragantes.",
                )
        return cleaned_data


class ElectoralReportFilterForm(forms.Form):
    dignity = forms.ModelChoiceField(
        label="Dignidad",
        queryset=ElectoralDignity.objects.filter(is_active=True).order_by("order", "name"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select form-select-solid"}),
    )
    district = forms.ModelChoiceField(
        label="Circunscripción",
        queryset=ElectoralDistrict.objects.filter(is_active=True).order_by("dignity__order", "name"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select form-select-solid"}),
    )
    parish = forms.ModelChoiceField(
        label="Parroquia",
        queryset=Parish.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select form-select-solid"}),
    )
    venue = forms.ModelChoiceField(
        label="Recinto electoral",
        queryset=ElectoralVenue.objects.filter(is_active=True).order_by("name"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select form-select-solid"}),
    )
    table = forms.ModelChoiceField(
        label="Mesa",
        queryset=ElectoralTable.objects.filter(is_active=True).order_by("number", "gender"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select form-select-solid"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["parish"].queryset = Parish.objects.filter(is_active=True).order_by(
            "canton__name", "name"
        )
