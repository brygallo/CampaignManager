from django.conf import settings
from django.db import models
from django_fsm import FSMIntegerField
from tracing.models import BaseModel

from apps.campaigns.models import Campaign
from apps.field_surveys.models import AdvertisingType
from apps.territorial_ads.transitions import (
    PhysicalAdTransitions,
    PhysicalAdUnitTransitions,
)
from core.fields import CompressedImageField
from core.validators import LATITUDE_VALIDATORS, LONGITUDE_VALIDATORS


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


class AdvertisingTypeSize(BaseModel):
    """Catálogo de tamaños por tipo de publicidad.

    E.g. Sticker: pequeño / mediano / grande; Lona: pared / cuadro. Al
    aprobar una publicidad se elige el tamaño de cada unidad desde aquí.
    """

    advertisement_type = models.ForeignKey(
        AdvertisingType,
        on_delete=models.CASCADE,
        related_name="sizes",
        verbose_name="Tipo de publicidad",
    )
    name = models.CharField("Nombre", max_length=120)
    order = models.PositiveSmallIntegerField("Orden", default=0)

    class Meta:
        verbose_name = "Tamaño de publicidad"
        verbose_name_plural = "Tamaños de publicidad"
        ordering = ["advertisement_type__order", "advertisement_type__name", "order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["advertisement_type", "name"],
                name="unique_size_name_per_type",
            )
        ]

    def __str__(self):
        return f"{self.advertisement_type.name} — {self.name}"


class PhysicalAdvertisement(BaseModel, PhysicalAdTransitions):
    """Physical campaign advertising placement, initially focused on lonas."""

    workflow = PhysicalAdTransitions.workflow

    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.PROTECT,
        related_name="physical_advertisements",
        verbose_name="Campaña",
    )
    code = models.CharField("Código", max_length=32, unique=True, blank=True)
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
        validators=list(LATITUDE_VALIDATORS),
    )
    offered_longitude = models.DecimalField(
        "Longitud referencial",
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=list(LONGITUDE_VALIDATORS),
    )
    offered_photo = CompressedImageField(
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
    assigned_installer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assigned_physical_ads",
        verbose_name="Instalador asignado",
        null=True,
        blank=True,
    )
    installer_team = models.CharField("Instalador externo", max_length=180, blank=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assigned_physical_ad_jobs",
        verbose_name="Asignado por",
        null=True,
        blank=True,
    )
    assigned_at = models.DateTimeField("Fecha de asignación", null=True, blank=True)

    installed_latitude = models.DecimalField(
        "Latitud GPS instalación",
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=list(LATITUDE_VALIDATORS),
    )
    installed_longitude = models.DecimalField(
        "Longitud GPS instalación",
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=list(LONGITUDE_VALIDATORS),
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
    damage_photo = CompressedImageField(
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
        verbose_name = "Solicitud de publicidad"
        verbose_name_plural = "Solicitudes de publicidad"
        ordering = ["-created_date"]
        permissions = (
            ("approve_physicaladvertisement", "Puede aprobar publicidad"),
            ("reject_physicaladvertisement", "Puede rechazar publicidad"),
            ("assign_physicaladvertisement", "Puede asignar instalación de publicidad"),
            ("install_physicaladvertisement", "Puede registrar instalación de publicidad"),
            ("report_damage_physicaladvertisement", "Puede reportar daño de publicidad"),
            ("retire_physicaladvertisement", "Puede retirar publicidad"),
        )

    def __str__(self):
        return self.code or self.address

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.code:
            # ``SOL-`` = solicitud; each physical unit carries its own ``PUB-`` code.
            self.code = f"SOL-{self.pk:06d}"
            super().save(update_fields=["code"])

    @property
    def primary_item(self):
        """First item by catalog order; drives the map pin icon."""
        return self.items.select_related("advertisement_type").first()

    @property
    def primary_type_icon(self):
        item = self.primary_item
        return item.advertisement_type.icon if item else "element-12"

    @property
    def items_summary(self):
        """Human-readable list like ``2× Valla · 3× Lona`` for lists and pins."""
        return " · ".join(
            f"{item.quantity}× {item.advertisement_type.name}"
            for item in self.items.select_related("advertisement_type")
        )

    @property
    def total_units(self):
        """Total physical units across all items (one installation photo each)."""
        return sum(item.quantity for item in self.items.all())

    @property
    def installation_photos_summary(self):
        count = self.installation_photos.count()
        return f"{count} foto(s)" if count else ""

    @property
    def units(self):
        """All physical units spawned by this request, across its items.

        Iterates ``items`` so a ``prefetch_related("items__units")`` on the
        request queryset is honored (map/popup render many requests).
        """
        return [
            unit for item in self.items.all() for unit in item.units.all()
        ]

    @property
    def items_sizes_summary(self):
        """Approved unit sizes, e.g. ``Lona: Pared, Cuadro · Sticker: Mediano``."""
        per_type = {}
        for unit in self.units:
            if unit.size_id:
                per_type.setdefault(unit.item.advertisement_type.name, []).append(
                    unit.size.name
                )
        return " · ".join(
            f"{type_name}: {', '.join(sizes)}" for type_name, sizes in per_type.items()
        )

    @property
    def units_state_summary(self):
        """State counts like ``2 instaladas · 1 dañada`` for lists/popups."""
        counts = {}
        for unit in self.units:
            label = unit.get_state_display().lower()
            counts[label] = counts.get(label, 0) + 1
        return " · ".join(f"{count} {label}" for label, count in counts.items())

    @property
    def installed_location(self):
        """(lat, lng) shown on the map once installed.

        Prefers the legacy ad-level GPS pair, then falls back to the first
        unit that carries evidence coordinates.
        """
        if self.installed_latitude is not None and self.installed_longitude is not None:
            return self.installed_latitude, self.installed_longitude
        for unit in self.units:
            if unit.latitude is not None and unit.longitude is not None:
                return unit.latitude, unit.longitude
        return None

    def sync_state_with_units(self, user=None, pending_unit=None, pending_state=None):
        """Aggregate unit states into the request workflow.

        Called from unit transitions BEFORE the unit row is saved, so the
        in-flight unit's target state is passed explicitly and overrides
        whatever the DB still holds for it.

        The request state is DERIVED from its units (never set by hand):
        - every active unit retired → request RETIRADA;
        - else no unit PENDIENTE and at least one INSTALADA/DAÑADA → INSTALADA;
        - else some unit back to PENDIENTE → PENDIENTE_INSTALACION.
        A DESCARTADA (won't install) unit counts as resolved (neither pending
        nor active), so it never blocks completion nor forces retirement.
        """
        unit_workflow = PhysicalAdvertisementUnit.workflow
        states = []
        for unit in PhysicalAdvertisementUnit.objects.filter(item__advertisement=self):
            if pending_unit is not None and unit.pk == pending_unit.pk:
                states.append(pending_state)
            else:
                states.append(unit.state)
        if not states:
            return
        changed = False
        any_pending = any(s == unit_workflow.PENDIENTE for s in states)
        any_installed = any(
            s in (unit_workflow.INSTALADA, unit_workflow.DANADA) for s in states
        )
        # Units that were discarded never counted as physical advertising.
        active = [s for s in states if s != unit_workflow.DESCARTADA]
        all_retired = bool(active) and all(
            s == unit_workflow.RETIRADA for s in active
        )
        if all_retired and self.state == self.workflow.INSTALADA:
            self.retire_request(user=user)
            changed = True
        elif not any_pending and any_installed and (
            self.state == self.workflow.PENDIENTE_INSTALACION
        ):
            self.mark_installed(user=user)
            changed = True
        elif any_pending and self.state == self.workflow.INSTALADA:
            self.revert_to_pending(user=user)
            changed = True
        if changed:
            self.save()

    @property
    def items_instructions_summary(self):
        """Per-type installation instructions for detail pages."""
        return "\n".join(
            f"{item.quantity}× {item.advertisement_type.name}: {item.installation_instructions}"
            for item in self.items.select_related("advertisement_type")
            if item.installation_instructions
        )


class PhysicalAdvertisementItem(BaseModel):
    """One advertising type (with quantity) inside a physical advertisement.

    A single offered spot can host several preloaded advertising types at
    once (e.g. 2 vallas + 3 lonas); each line keeps its own quantity and,
    once approved, its own installation instructions.
    """

    advertisement = models.ForeignKey(
        PhysicalAdvertisement,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Publicidad",
    )
    advertisement_type = models.ForeignKey(
        AdvertisingType,
        on_delete=models.PROTECT,
        related_name="physical_ad_items",
        verbose_name="Tipo de publicidad",
    )
    quantity = models.PositiveSmallIntegerField("Cantidad", default=1)
    installation_instructions = models.TextField(
        "Indicaciones para instalación",
        blank=True,
        help_text="Indica qué se requiere para instalar este tipo (escalera, andamio, permisos, etc.).",
    )

    class Meta:
        verbose_name = "Tipo de publicidad del lugar"
        verbose_name_plural = "Tipos de publicidad del lugar"
        ordering = ["advertisement_type__order", "advertisement_type__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["advertisement", "advertisement_type"],
                name="unique_type_per_advertisement",
            )
        ]

    def __str__(self):
        return f"{self.quantity}× {self.advertisement_type.name}"


class PhysicalAdvertisementUnit(BaseModel, PhysicalAdUnitTransitions):
    """One physical advertisement (valla / lona / sticker) born from a request.

    The request (``PhysicalAdvertisement``) handles the place: offer,
    approval, installer assignment. Once approved, every unit materializes
    as a row here and lives its own lifecycle: installation evidence
    (photo + GPS + notes), damage reports and retirement are per unit.
    """

    workflow = PhysicalAdUnitTransitions.workflow

    code = models.CharField("Código", max_length=32, blank=True)
    item = models.ForeignKey(
        PhysicalAdvertisementItem,
        on_delete=models.CASCADE,
        related_name="units",
        verbose_name="Ítem solicitado",
    )
    unit_number = models.PositiveSmallIntegerField("Unidad", default=1)
    size = models.ForeignKey(
        AdvertisingTypeSize,
        on_delete=models.PROTECT,
        related_name="units",
        verbose_name="Tamaño",
        null=True,
        blank=True,
    )
    state = FSMIntegerField(
        "Estado",
        choices=workflow.choices,
        default=workflow.PENDIENTE,
        protected=True,
    )

    photo = CompressedImageField(
        "Foto de evidencia",
        upload_to="territorial_ads/installations/",
        null=True,
        blank=True,
    )
    latitude = models.DecimalField(
        "Latitud GPS",
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=list(LATITUDE_VALIDATORS),
    )
    longitude = models.DecimalField(
        "Longitud GPS",
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=list(LONGITUDE_VALIDATORS),
    )
    notes = models.TextField("Notas de instalación", blank=True)
    installed_at = models.DateTimeField("Fecha/hora instalación", null=True, blank=True)
    installed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="installed_ad_units",
        verbose_name="Instalado por",
        null=True,
        blank=True,
    )

    damage_notes = models.TextField("Notas de daño", blank=True)
    damage_photo = CompressedImageField(
        "Foto de daño",
        upload_to="territorial_ads/damages/",
        null=True,
        blank=True,
    )
    damage_reported_at = models.DateTimeField("Fecha reporte daño", null=True, blank=True)
    damage_reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="damage_reported_ad_units",
        verbose_name="Daño reportado por",
        null=True,
        blank=True,
    )

    retired_at = models.DateTimeField("Fecha retiro", null=True, blank=True)
    retired_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="retired_ad_units",
        verbose_name="Retirado por",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Publicidad"
        verbose_name_plural = "Publicidades"
        ordering = ["item__advertisement_type__order", "item_id", "unit_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["item", "unit_number"],
                name="unique_unit_number_per_item",
            )
        ]

    def __str__(self):
        return self.code or self.display_label

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.code:
            # ``PUB-`` = publicidad física (one installable advertisement).
            self.code = f"PUB-{self.pk:06d}"
            super().save(update_fields=["code"])

    @property
    def advertisement(self):
        return self.item.advertisement

    @property
    def request_code(self):
        return self.item.advertisement.code

    @property
    def request_campaign(self):
        return self.item.advertisement.campaign

    @property
    def display_label(self):
        """Human label like ``Lona (Pared) #2`` for cards and lists."""
        label = self.item.advertisement_type.name
        if self.size_id:
            label += f" ({self.size.name})"
        if self.item.quantity > 1:
            label += f" #{self.unit_number}"
        return label


class InstallationPhoto(BaseModel):
    """Legacy installation evidence photo (pre per-unit redesign).

    New evidence lives on ``PhysicalAdvertisementUnit.photo``; this model
    only keeps historical galleries readable.
    """

    advertisement = models.ForeignKey(
        PhysicalAdvertisement,
        on_delete=models.CASCADE,
        related_name="installation_photos",
        verbose_name="Publicidad",
    )
    photo = CompressedImageField(
        "Foto de evidencia",
        upload_to="territorial_ads/installations/",
    )

    class Meta:
        verbose_name = "Foto de instalación"
        verbose_name_plural = "Fotos de instalación"
        ordering = ["id"]

    def __str__(self):
        return f"Foto #{self.pk}" if self.pk else "Foto"


class AdvertisingRefusal(BaseModel):
    """A reported spot where the owner did NOT want to host advertising.

    Visible on the territorial-ads map so canvassers don't re-approach the
    same place. Stays out of the PhysicalAdvertisement workflow on purpose:
    it's a lightweight refusal log, not a piece of inventory.
    """

    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.PROTECT,
        related_name="advertising_refusals",
        verbose_name="Campaña",
    )
    reason = models.TextField(
        "Motivo",
        help_text="Razón por la cual el propietario no acepta publicidad.",
    )
    owner_reference = models.CharField(
        "Referencia del propietario",
        max_length=180,
        blank=True,
        help_text="Opcional: nombre o referencia para identificar de quién es la casa.",
    )
    latitude = models.DecimalField(
        "Latitud",
        max_digits=9,
        decimal_places=6,
        validators=list(LATITUDE_VALIDATORS),
    )
    longitude = models.DecimalField(
        "Longitud",
        max_digits=9,
        decimal_places=6,
        validators=list(LONGITUDE_VALIDATORS),
    )
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reported_advertising_refusals",
        verbose_name="Reportado por",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Rechazo de publicidad"
        verbose_name_plural = "Rechazos de publicidad"
        ordering = ["-created_date"]

    def __str__(self):
        return f"Rechazo #{self.pk}" if self.pk else "Rechazo"
