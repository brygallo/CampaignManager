from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from tracing.models import BaseModel

from apps.campaigns.models import Campaign
from apps.locations.models import Parish, Sector
from core.fields import CompressedImageField


class SurveyResultOption(BaseModel):
    code = models.CharField("Código", max_length=40, unique=True)
    name = models.CharField("Nombre", max_length=120)
    order = models.PositiveSmallIntegerField("Orden", default=0)

    class Meta:
        verbose_name = "Resultado de levantamiento"
        verbose_name_plural = "Resultados de levantamiento"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class FieldSurvey(BaseModel):
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.PROTECT,
        related_name="field_surveys",
        verbose_name="Campaña",
    )
    code = models.CharField("Código", max_length=32, unique=True, blank=True)
    brigadier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="field_surveys",
        verbose_name="Brigadista",
    )
    latitude = models.DecimalField(
        "Latitud GPS",
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        "Longitud GPS",
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    gps_accuracy = models.DecimalField(
        "Precisión GPS (m)", max_digits=8, decimal_places=2, null=True, blank=True
    )
    location_was_manually_adjusted = models.BooleanField(
        "Ubicación ajustada manualmente", default=False
    )
    address = models.CharField("Dirección", max_length=255, blank=True)
    reference = models.CharField("Referencia", max_length=255, blank=True)
    parish = models.ForeignKey(
        Parish,
        on_delete=models.PROTECT,
        related_name="field_surveys",
        verbose_name="Parroquia",
        null=True,
        blank=True,
    )
    neighborhood = models.ForeignKey(
        Sector,
        on_delete=models.PROTECT,
        related_name="field_surveys",
        verbose_name="Barrio / sector",
        null=True,
        blank=True,
    )
    person_name = models.CharField("Nombre de persona", max_length=180, blank=True)
    person_phone = models.CharField("Teléfono", max_length=32, blank=True)
    voters_count = models.PositiveIntegerField("Cantidad de votantes", default=0)
    notes = models.TextField("Notas", blank=True)
    results = models.ManyToManyField(
        SurveyResultOption,
        related_name="field_surveys",
        verbose_name="Resultados",
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_field_surveys",
        verbose_name="Creado por",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Levantamiento de campo"
        verbose_name_plural = "Levantamientos de campo"
        ordering = ["-created_date"]
        permissions = (
            ("view_all_fieldsurvey", "Puede ver todos los levantamientos de campo"),
        )

    def __str__(self):
        return self.code or f"{self.campaign} - {self.brigadier} - {self.created_date:%d/%m/%Y %H:%M}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.code:
            self.code = f"LC-{self.pk:06d}"
            super().save(update_fields=["code"])

    @property
    def primary_result_code(self):
        priority = ["APOYA", "INDECISO", "NO_APOYA", "ATENDIO", "NO_ATENDIO"]
        selected = set(self.results.values_list("code", flat=True))
        return next((code for code in priority if code in selected), "")

    @property
    def results_display(self):
        return ", ".join(self.results.order_by("order", "name").values_list("name", flat=True)) or "-"


class AdvertisingType(BaseModel):
    code = models.CharField("Código", max_length=40, unique=True)
    name = models.CharField("Nombre", max_length=120)
    icon = models.CharField(
        "Icono",
        max_length=60,
        default="element-12",
        help_text="Nombre del icono KeenIcons usado en mapas y vistas.",
    )
    order = models.PositiveSmallIntegerField("Orden", default=0)

    class Meta:
        verbose_name = "Tipo de publicidad"
        verbose_name_plural = "Tipos de publicidad"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class Competitor(BaseModel):
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.PROTECT,
        related_name="competitors",
        verbose_name="Campaña",
    )
    list_number = models.CharField("Lista", max_length=16)
    political_organization = models.CharField("Organización política", max_length=180)
    candidate_name = models.CharField("Candidato", max_length=180, blank=True)
    color = models.CharField("Color", max_length=7, blank=True, help_text="Hex #RRGGBB")
    notes = models.TextField("Notas", blank=True)

    class Meta:
        verbose_name = "Competidor"
        verbose_name_plural = "Competidores"
        ordering = ["campaign", "list_number", "political_organization"]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "list_number", "political_organization"],
                name="field_surveys_unique_competitor_by_campaign",
            )
        ]

    def __str__(self):
        candidate = f" - {self.candidate_name}" if self.candidate_name else ""
        return f"Lista {self.list_number} {self.political_organization}{candidate}"


class CompetitorAdvertisingDetection(BaseModel):
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.PROTECT,
        related_name="competitor_advertising_detections",
        verbose_name="Campaña",
    )
    competitor = models.ForeignKey(
        Competitor,
        on_delete=models.PROTECT,
        related_name="advertising_detections",
        verbose_name="Competidor",
    )
    brigadier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="competitor_advertising_detections",
        verbose_name="Brigadista",
    )
    field_survey = models.ForeignKey(
        FieldSurvey,
        on_delete=models.SET_NULL,
        related_name="competitor_advertising_detections",
        verbose_name="Levantamiento",
        null=True,
        blank=True,
    )
    advertising_type = models.ForeignKey(
        AdvertisingType,
        on_delete=models.PROTECT,
        related_name="competitor_advertising_detections",
        verbose_name="Tipo de publicidad",
    )
    latitude = models.DecimalField(
        "Latitud GPS",
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        "Longitud GPS",
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    gps_accuracy = models.DecimalField(
        "Precisión GPS (m)", max_digits=8, decimal_places=2, null=True, blank=True
    )
    location_was_manually_adjusted = models.BooleanField(
        "Ubicación ajustada manualmente", default=False
    )
    address = models.CharField("Dirección", max_length=255, blank=True)
    reference = models.CharField("Referencia", max_length=255, blank=True)
    photo = CompressedImageField(
        "Foto", upload_to="field_surveys/competitor_advertising/", null=True, blank=True
    )
    observation = models.TextField("Observación", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_competitor_advertising_detections",
        verbose_name="Creado por",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Publicidad de competencia detectada"
        verbose_name_plural = "Publicidad de competencia detectada"
        ordering = ["-created_date"]

    def __str__(self):
        return f"{self.competitor} - {self.advertising_type}"

    def clean(self):
        errors = {}
        if self.competitor_id and self.campaign_id and self.competitor.campaign_id != self.campaign_id:
            errors["competitor"] = "El competidor debe pertenecer a la campaña seleccionada."
        if self.latitude in (None, ""):
            errors["latitude"] = "La latitud GPS es obligatoria."
        if self.longitude in (None, ""):
            errors["longitude"] = "La longitud GPS es obligatoria."
        if errors:
            raise ValidationError(errors)
