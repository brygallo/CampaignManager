from django.conf import settings
from django.db import models
from tracing.models import BaseModel

from apps.locations.models import Canton, Parish, Province
from core.validators import LATITUDE_VALIDATORS, LONGITUDE_VALIDATORS


class ElectoralDignity(BaseModel):
    class Scope(models.TextChoices):
        PROVINCE = "province", "Provincia"
        CANTON = "canton", "Cantón"
        DISTRICT = "district", "Circunscripción"
        PARISH = "parish", "Parroquia"

    class ParishKindRule(models.TextChoices):
        ALL = "all", "Todas"
        URBAN = "urban", "Solo urbanas"
        RURAL = "rural", "Solo rurales"

    name = models.CharField("Dignidad", max_length=140, unique=True)
    scope = models.CharField("Ámbito", max_length=20, choices=Scope.choices)
    parish_kind_rule = models.CharField(
        "Tipo de parroquia",
        max_length=20,
        choices=ParishKindRule.choices,
        default=ParishKindRule.ALL,
    )
    seats = models.PositiveSmallIntegerField("Escaños", default=1)
    order = models.PositiveSmallIntegerField("Orden", default=0)

    class Meta:
        verbose_name = "Dignidad electoral"
        verbose_name_plural = "Dignidades electorales"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class ElectoralDistrict(BaseModel):
    class DistrictKind(models.TextChoices):
        PROVINCE = "province", "Provincia"
        CANTON = "canton", "Cantón"
        URBAN = "urban", "Urbana"
        RURAL = "rural", "Rural"
        PARISH = "parish", "Parroquial"

    dignity = models.ForeignKey(
        ElectoralDignity,
        on_delete=models.CASCADE,
        related_name="districts",
        verbose_name="Dignidad",
    )
    name = models.CharField("Circunscripción", max_length=180)
    kind = models.CharField("Tipo", max_length=20, choices=DistrictKind.choices)
    province = models.ForeignKey(
        Province,
        on_delete=models.PROTECT,
        related_name="vote_districts",
        verbose_name="Provincia",
        null=True,
        blank=True,
    )
    canton = models.ForeignKey(
        Canton,
        on_delete=models.PROTECT,
        related_name="vote_districts",
        verbose_name="Cantón",
        null=True,
        blank=True,
    )
    parishes = models.ManyToManyField(
        Parish,
        related_name="vote_districts",
        verbose_name="Parroquias",
        blank=True,
    )
    seats = models.PositiveSmallIntegerField("Escaños", default=1)
    order = models.PositiveSmallIntegerField("Orden", default=0)

    class Meta:
        verbose_name = "Circunscripción electoral"
        verbose_name_plural = "Circunscripciones electorales"
        ordering = ["dignity__order", "order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["dignity", "name"], name="votes_unique_electoral_district_name"
            )
        ]

    def __str__(self):
        return f"{self.dignity} / {self.name}"

    def contains_parish(self, parish):
        if self.dignity.scope == ElectoralDignity.Scope.PROVINCE:
            return self.province_id == parish.canton.province_id
        if self.dignity.scope == ElectoralDignity.Scope.CANTON:
            return self.canton_id == parish.canton_id
        return self.parishes.filter(pk=parish.pk).exists()


class ElectoralCandidateOption(BaseModel):
    district = models.ForeignKey(
        ElectoralDistrict,
        on_delete=models.CASCADE,
        related_name="candidate_options",
        verbose_name="Circunscripción",
    )
    list_code = models.CharField("Lista", max_length=32)
    candidate_name = models.CharField("Candidato", max_length=180)
    order = models.PositiveSmallIntegerField("Orden", default=0)

    class Meta:
        verbose_name = "Candidatura electoral"
        verbose_name_plural = "Candidaturas electorales"
        ordering = ["district__dignity__order", "district__order", "order", "list_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["district", "list_code", "candidate_name"],
                name="votes_unique_electoral_candidate_option",
            )
        ]

    def __str__(self):
        return f"{self.district} / {self.list_code} - {self.candidate_name}"


class ElectoralVenue(BaseModel):
    parish = models.ForeignKey(
        Parish, on_delete=models.PROTECT, related_name="vote_venues", verbose_name="Parroquia"
    )
    name = models.CharField("Recinto electoral", max_length=180)
    latitude = models.DecimalField(
        "Latitud",
        max_digits=9,
        decimal_places=6,
        validators=list(LATITUDE_VALIDATORS),
        null=True,
        blank=True,
    )
    longitude = models.DecimalField(
        "Longitud",
        max_digits=9,
        decimal_places=6,
        validators=list(LONGITUDE_VALIDATORS),
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Recinto electoral"
        verbose_name_plural = "Recintos electorales"
        ordering = ["parish__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["parish", "name"], name="votes_unique_electoral_venue_per_parish"
            )
        ]

    def __str__(self):
        return f"{self.name} - {self.parish.name}"


class ElectoralTable(BaseModel):
    class Gender(models.TextChoices):
        FEMALE = "F", "Femenino"
        MALE = "M", "Masculino"
        MIXED = "X", "Mixta"

    venue = models.ForeignKey(
        ElectoralVenue, on_delete=models.PROTECT, related_name="tables", verbose_name="Recinto"
    )
    number = models.CharField("Mesa", max_length=24)
    gender = models.CharField("Género", max_length=1, choices=Gender.choices, default=Gender.MIXED)

    class Meta:
        verbose_name = "Mesa electoral"
        verbose_name_plural = "Mesas electorales"
        ordering = ["venue__parish__name", "venue__name", "number"]
        constraints = [
            models.UniqueConstraint(
                fields=["venue", "number", "gender"], name="votes_unique_electoral_table"
            )
        ]

    def __str__(self):
        return f"Mesa {self.number} {self.get_gender_display()} - {self.venue.name}"


class ElectoralTableAssignment(BaseModel):
    table = models.ForeignKey(
        ElectoralTable,
        on_delete=models.CASCADE,
        related_name="assignments",
        verbose_name="Mesa",
    )
    watcher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="vote_table_assignments",
        verbose_name="Veedor",
    )
    notes = models.CharField("Observaciones", max_length=240, blank=True)

    class Meta:
        verbose_name = "Asignación de mesa"
        verbose_name_plural = "Asignaciones de mesas"
        ordering = ["table__venue__parish__name", "table__venue__name", "table__number"]
        constraints = [
            models.UniqueConstraint(
                fields=["table", "watcher"], name="votes_unique_table_watcher_assignment"
            )
        ]

    def __str__(self):
        return f"{self.watcher} - {self.table}"


class ElectoralResultReport(BaseModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Borrador"
        SUBMITTED = "submitted", "Ingresada"
        OBSERVED = "observed", "Observada"
        VALIDATED = "validated", "Validada"
        REJECTED = "rejected", "Rechazada"

    parish = models.ForeignKey(
        Parish, on_delete=models.PROTECT, related_name="vote_result_reports", verbose_name="Parroquia"
    )
    venue = models.ForeignKey(
        ElectoralVenue,
        on_delete=models.PROTECT,
        related_name="result_reports",
        verbose_name="Recinto electoral",
    )
    table = models.ForeignKey(
        ElectoralTable,
        on_delete=models.PROTECT,
        related_name="result_reports",
        verbose_name="Mesa",
    )
    dignity = models.ForeignKey(
        ElectoralDignity,
        on_delete=models.PROTECT,
        related_name="result_reports",
        verbose_name="Dignidad",
    )
    district = models.ForeignKey(
        ElectoralDistrict,
        on_delete=models.PROTECT,
        related_name="result_reports",
        verbose_name="Circunscripción",
    )
    watcher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="vote_result_reports",
        verbose_name="Veedor",
        null=True,
        blank=True,
    )
    status = models.CharField(
        "Estado", max_length=20, choices=Status.choices, default=Status.SUBMITTED
    )
    voters_count = models.PositiveIntegerField("Sufragantes", null=True, blank=True)
    validation_notes = models.TextField("Observaciones de validación", blank=True)

    class Meta:
        verbose_name = "Acta de resultado electoral"
        verbose_name_plural = "Actas de resultados electorales"
        ordering = ["-created_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["table", "dignity", "district"],
                name="votes_unique_electoral_result_report",
            )
        ]

    def __str__(self):
        return f"{self.dignity} - {self.table}"

    @property
    def total_votes(self):
        return sum(line.votes for line in self.lines.all())


class ElectoralResultLine(BaseModel):
    class LineType(models.TextChoices):
        CANDIDATE = "candidate", "Candidato"
        BLANK = "blank", "Blancos"
        NULL = "null", "Nulos"

    report = models.ForeignKey(
        ElectoralResultReport,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="Acta",
    )
    line_type = models.CharField(
        "Tipo", max_length=20, choices=LineType.choices, default=LineType.CANDIDATE
    )
    list_code = models.CharField("Lista", max_length=32)
    candidate_name = models.CharField("Candidato", max_length=180, blank=True)
    candidate_option = models.ForeignKey(
        ElectoralCandidateOption,
        on_delete=models.PROTECT,
        related_name="result_lines",
        verbose_name="Candidatura",
        null=True,
        blank=True,
    )
    votes = models.PositiveIntegerField("Votos", default=0)
    order = models.PositiveSmallIntegerField("Orden", default=0)

    class Meta:
        verbose_name = "Línea de resultado electoral"
        verbose_name_plural = "Líneas de resultados electorales"
        ordering = ["report", "order", "list_code"]

    def __str__(self):
        return f"{self.list_code} {self.candidate_name}: {self.votes}"
