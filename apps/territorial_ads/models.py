from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django_fsm import FSMIntegerField
from tracing.models import BaseModel

from apps.campaigns.models import Campaign
from apps.territorial_ads.transitions import PhysicalAdTransitions


class AdvertisingCostType(BaseModel):
    """Catálogo de cómo se obtiene el lugar (gratuita, pagada, donada, canje, etc.)."""

    PAID_CODE = "PAGADA"

    code = models.CharField("Código", max_length=40, unique=True)
    name = models.CharField("Nombre", max_length=120)
    order = models.PositiveSmallIntegerField("Orden", default=0)
    requires_amount = models.BooleanField(
        "Requiere monto",
        default=False,
        help_text="Si está activo, se exige capturar el monto acordado.",
    )

    class Meta:
        verbose_name = "Tipo de costo de publicidad"
        verbose_name_plural = "Tipos de costo de publicidad"
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class PhysicalAdvertisement(BaseModel, PhysicalAdTransitions):
    """Physical campaign advertising placement, initially focused on lonas."""

    workflow = PhysicalAdTransitions.workflow

    class AdvertisementType(models.TextChoices):
        LONA = "lona", "Lona"
        VALLA = "valla", "Valla"
        AFICHE = "afiche", "Afiche"
        OTRO = "otro", "Otro"

    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.PROTECT,
        related_name="physical_advertisements",
        verbose_name="Campaña",
    )
    advertisement_type = models.CharField(
        "Tipo de publicidad",
        max_length=24,
        choices=AdvertisementType.choices,
        default=AdvertisementType.LONA,
    )
    code = models.CharField("Código", max_length=32, unique=True, blank=True)
    quantity = models.PositiveSmallIntegerField("Cantidad", default=1)
    width_meters = models.DecimalField(
        "Ancho (m)", max_digits=6, decimal_places=2, null=True, blank=True
    )
    height_meters = models.DecimalField(
        "Alto (m)", max_digits=6, decimal_places=2, null=True, blank=True
    )

    owner_name = models.CharField("Propietario / contacto", max_length=180)
    owner_phone = models.CharField("Teléfono contacto", max_length=32)
    cost_type = models.ForeignKey(
        AdvertisingCostType,
        on_delete=models.PROTECT,
        related_name="physical_advertisements",
        verbose_name="Tipo de costo",
        null=True,
        blank=True,
    )
    cost_amount = models.DecimalField(
        "Monto acordado",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Sólo si el tipo de costo lo requiere.",
    )
    offered_notes = models.TextField("Condiciones ofrecidas", blank=True)

    address = models.CharField("Dirección", max_length=255)
    reference = models.CharField("Referencia", max_length=255, blank=True)
    offered_latitude = models.DecimalField(
        "Latitud referencial",
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    offered_longitude = models.DecimalField(
        "Longitud referencial",
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    offered_photo = models.ImageField(
        "Foto del lugar ofrecido",
        upload_to="territorial_ads/offered/",
        null=True,
        blank=True,
    )

    state = FSMIntegerField(
        "Estado",
        choices=workflow.choices,
        default=workflow.OFRECIDA,
        protected=True,
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="approved_physical_ads",
        verbose_name="Aprobado por",
        null=True,
        blank=True,
    )
    approved_at = models.DateTimeField("Fecha de aprobación", null=True, blank=True)
    installation_instructions = models.TextField(
        "Instrucciones para instalación",
        blank=True,
        help_text="Indica qué se requiere para instalar (escalera, andamio, permisos, etc.).",
    )
    assigned_installer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assigned_physical_ads",
        verbose_name="Instalador asignado",
        null=True,
        blank=True,
    )
    installer_team = models.CharField("Equipo instalador", max_length=180, blank=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assigned_physical_ad_jobs",
        verbose_name="Asignado por",
        null=True,
        blank=True,
    )
    assigned_at = models.DateTimeField("Fecha de asignación", null=True, blank=True)

    installation_photo = models.ImageField(
        "Foto de evidencia",
        upload_to="territorial_ads/installations/",
        null=True,
        blank=True,
    )
    installed_latitude = models.DecimalField(
        "Latitud GPS instalación",
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    installed_longitude = models.DecimalField(
        "Longitud GPS instalación",
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    installed_at = models.DateTimeField("Fecha/hora instalación", null=True, blank=True)
    installed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="installed_physical_ads",
        verbose_name="Usuario instalador",
        null=True,
        blank=True,
    )
    installation_notes = models.TextField("Notas de instalación", blank=True)

    damage_notes = models.TextField("Notas de daño", blank=True)
    damage_photo = models.ImageField(
        "Foto de daño",
        upload_to="territorial_ads/damages/",
        null=True,
        blank=True,
    )
    damage_reported_at = models.DateTimeField("Fecha reporte daño", null=True, blank=True)
    damage_reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="damage_reported_physical_ads",
        verbose_name="Daño reportado por",
        null=True,
        blank=True,
    )

    rejection_reason = models.TextField("Motivo de rechazo", blank=True)
    rejected_at = models.DateTimeField("Fecha de rechazo", null=True, blank=True)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="rejected_physical_ads",
        verbose_name="Rechazado por",
        null=True,
        blank=True,
    )

    retirement_notes = models.TextField("Notas de retiro", blank=True)
    retirement_photo = models.ImageField(
        "Foto de retiro",
        upload_to="territorial_ads/retirements/",
        null=True,
        blank=True,
    )
    retired_at = models.DateTimeField("Fecha retiro", null=True, blank=True)
    retired_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="retired_physical_ads",
        verbose_name="Retirado por",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Publicidad física"
        verbose_name_plural = "Publicidad física"
        ordering = ["-created_date"]
        permissions = (
            ("approve_physicaladvertisement", "Puede aprobar publicidad física"),
            ("reject_physicaladvertisement", "Puede rechazar publicidad física"),
            ("assign_physicaladvertisement", "Puede asignar instalación de publicidad física"),
            ("install_physicaladvertisement", "Puede registrar instalación de publicidad física"),
            ("report_damage_physicaladvertisement", "Puede reportar daño de publicidad física"),
            ("retire_physicaladvertisement", "Puede retirar publicidad física"),
        )

    def __str__(self):
        return self.code or self.address

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.code:
            self.code = f"PF-{self.pk:06d}"
            super().save(update_fields=["code"])
