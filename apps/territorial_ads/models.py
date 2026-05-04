from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django_fsm import FSMIntegerField
from tracing.models import BaseModel

from apps.campaigns.models import Campaign
from apps.territorial_ads.transitions import PhysicalAdTransitions


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
        null=True,
        blank=True,
    )
    advertisement_type = models.CharField(
        "Tipo de publicidad",
        max_length=24,
        choices=AdvertisementType.choices,
        default=AdvertisementType.LONA,
    )
    code = models.CharField("Código", max_length=32, unique=True, blank=True)
    title = models.CharField("Identificación", max_length=180)
    quantity = models.PositiveSmallIntegerField("Cantidad", default=1)
    width_meters = models.DecimalField(
        "Ancho (m)", max_digits=6, decimal_places=2, null=True, blank=True
    )
    height_meters = models.DecimalField(
        "Alto (m)", max_digits=6, decimal_places=2, null=True, blank=True
    )

    owner_name = models.CharField("Dueño / contacto", max_length=180)
    owner_phone = models.CharField("Teléfono contacto", max_length=32)
    offered_notes = models.TextField("Condiciones ofrecidas", blank=True)

    province = models.CharField("Provincia", max_length=80, blank=True)
    canton = models.CharField("Cantón", max_length=80, blank=True)
    parish = models.CharField("Parroquia", max_length=80, blank=True)
    sector = models.CharField("Sector / barrio", max_length=120, blank=True)
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
            ("assign_physicaladvertisement", "Puede asignar instalación de publicidad física"),
            ("install_physicaladvertisement", "Puede registrar instalación de publicidad física"),
            ("report_damage_physicaladvertisement", "Puede reportar daño de publicidad física"),
            ("retire_physicaladvertisement", "Puede retirar publicidad física"),
        )

    def __str__(self):
        return self.code or self.title

    def save(self, *args, **kwargs):
        now = timezone.now()
        if self.approved_by_id and not self.approved_at:
            self.approved_at = now
        if (self.assigned_installer_id or self.installer_team) and not self.assigned_at:
            self.assigned_at = now
        if self.installed_by_id and not self.installed_at:
            self.installed_at = now
        if self.damage_reported_by_id and not self.damage_reported_at:
            self.damage_reported_at = now
        if self.retired_by_id and not self.retired_at:
            self.retired_at = now
        super().save(*args, **kwargs)
        if not self.code:
            self.code = f"PF-{self.pk:06d}"
            super().save(update_fields=["code"])

    @property
    def transition_requirements(self):
        if self.state == self.workflow.APROBADA:
            assigned = bool(self.assigned_installer_id or self.installer_team)
            return self._build_transition_requirements(
                "Asignar instalación",
                [
                    self._build_transition_requirement_item(
                        "Responsable de instalación",
                        self.assigned_installer or self.installer_team,
                        assigned,
                    )
                ],
                ready_text="Puedes asignar la instalación desde el menú de acciones.",
            )
        if self.state == self.workflow.PENDIENTE_INSTALACION:
            return self._build_transition_requirements(
                "Marcar instalada",
                [
                    self._build_transition_requirement_item("Foto de evidencia", self.installation_photo, False),
                    self._build_transition_requirement_item("Latitud GPS", self.installed_latitude, False),
                    self._build_transition_requirement_item("Longitud GPS", self.installed_longitude, False),
                ],
                help_text="Estos datos se capturan obligatoriamente al ejecutar la transición de instalación.",
            )
        return None

    @staticmethod
    def _build_transition_requirement_item(label, value=None, is_met=False, icon=None):
        return {
            "label": label,
            "value": value,
            "is_met": bool(is_met),
            "icon": icon or "fas fa-check-circle",
        }

    @classmethod
    def _build_transition_requirements(
        cls,
        transition_verb,
        items,
        target_label=None,
        help_text=None,
        ready_text=None,
    ):
        pending_count = sum(1 for item in items if not item.get("is_met"))
        return {
            "target_label": target_label,
            "transition_verb": transition_verb,
            "items": items,
            "pending_count": pending_count,
            "help_text": help_text
            or (
                "Completa los requisitos marcados en rojo para habilitar la "
                f"transición {transition_verb} desde el menú de acciones."
            ),
            "ready_text": ready_text
            or f"Puedes ejecutar la transición {transition_verb} desde el menú de acciones.",
        }
