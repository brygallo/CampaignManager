"""Multi-sitio suave: Site + Domain + SiteMembership.

`Site` es el eje del sistema. Cada modelo de dominio (campaña, creativo,
presupuesto, etc.) se relaciona con un Site mediante el mixin
`SiteScopedModel`.
"""
from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from tracing.models import BaseModel


class Site(BaseModel):
    """Sitio / marca / cliente / unidad organizativa."""

    name = models.CharField("Nombre", max_length=128)
    slug = models.SlugField("Slug", max_length=64, unique=True)
    brand_color = models.CharField(
        "Color de marca",
        max_length=7,
        blank=True,
        validators=[
            RegexValidator(
                regex=r"^#[0-9A-Fa-f]{6}$",
                message="Color hexadecimal inválido (formato #RRGGBB).",
            )
        ],
    )
    logo = models.ImageField("Logo", upload_to="sites/logos/", blank=True, null=True)
    timezone = models.CharField("Zona horaria", max_length=64, default="America/Guayaquil")
    currency = models.CharField("Moneda", max_length=3, default="USD")
    description = models.TextField("Descripción", blank=True)

    class Meta:
        verbose_name = "Sitio"
        verbose_name_plural = "Sitios"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Domain(BaseModel):
    """Dominio asociado a un sitio."""

    site = models.ForeignKey(
        Site,
        on_delete=models.CASCADE,
        related_name="domains",
        verbose_name="Sitio",
    )
    host = models.CharField("Host", max_length=255, unique=True)
    is_primary = models.BooleanField("Primario", default=False)

    class Meta:
        verbose_name = "Dominio"
        verbose_name_plural = "Dominios"
        ordering = ["site", "-is_primary", "host"]

    def __str__(self):
        return self.host


class SiteMembership(BaseModel):
    """Relación usuario-sitio con rol."""

    class Role(models.TextChoices):
        OWNER = "owner", "Propietario"
        ADMIN = "admin", "Administrador"
        MANAGER = "manager", "Gerente de campaña"
        EDITOR = "editor", "Editor"
        VIEWER = "viewer", "Solo lectura"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name="Usuario",
    )
    site = models.ForeignKey(
        Site,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name="Sitio",
    )
    role = models.CharField(
        "Rol",
        max_length=16,
        choices=Role.choices,
        default=Role.VIEWER,
    )

    class Meta:
        verbose_name = "Membresía"
        verbose_name_plural = "Membresías"
        unique_together = ("user", "site")
        ordering = ["site", "user"]

    def __str__(self):
        return f"{self.user} @ {self.site} ({self.get_role_display()})"
