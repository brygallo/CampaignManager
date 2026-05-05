"""Tenant + Domain + Branding + Settings.

These models live in the SHARED_APPS (public schema). Every other app's data
is isolated inside its own PostgreSQL schema, but the registry of tenants
(who exists and what branding it uses) is global.
"""
from django.db import models
from django_tenants.models import DomainMixin, TenantMixin


def tenant_logo_upload_to(instance, filename):
    return f"tenant_branding/{instance.tenant.schema_name}/logo/{filename}"


def tenant_favicon_upload_to(instance, filename):
    return f"tenant_branding/{instance.tenant.schema_name}/favicon/{filename}"


class Tenant(TenantMixin):
    """A political party using the platform.

    `schema_name` (inherited from TenantMixin) is the PostgreSQL schema where
    all the party's operational data lives. `auto_create_schema=True` triggers
    schema creation + per-tenant migrations on save().
    """

    name = models.CharField("Nombre del partido", max_length=200)
    slug = models.SlugField(
        "Slug",
        max_length=80,
        unique=True,
        help_text="Identificador URL-friendly (también usado como schema).",
    )

    is_active = models.BooleanField("Activo", default=True)
    created_at = models.DateTimeField("Creado", auto_now_add=True)
    updated_at = models.DateTimeField("Actualizado", auto_now=True)

    auto_create_schema = True
    auto_drop_schema = False

    class Meta:
        verbose_name = "Partido (tenant)"
        verbose_name_plural = "Partidos (tenants)"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Domain(DomainMixin):
    """Maps a hostname (subdomain or custom domain) to a Tenant.

    `is_primary=True` marks the canonical domain used for password reset
    emails and outbound links.
    """

    class Meta:
        verbose_name = "Dominio"
        verbose_name_plural = "Dominios"

    def __str__(self):
        return self.domain


class TenantBranding(models.Model):
    """Visual identity per tenant. Read by the brand context processor."""

    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name="branding",
        verbose_name="Partido",
    )

    brand_name = models.CharField("Nombre comercial", max_length=120, blank=True)
    logo = models.ImageField(
        "Logo", upload_to=tenant_logo_upload_to, blank=True, null=True
    )
    favicon = models.ImageField(
        "Favicon", upload_to=tenant_favicon_upload_to, blank=True, null=True
    )

    theme_default = models.CharField(
        "Tema",
        max_length=10,
        choices=[("light", "Claro"), ("dark", "Oscuro"), ("system", "Sistema")],
        default="light",
    )

    updated_at = models.DateTimeField("Actualizado", auto_now=True)

    class Meta:
        verbose_name = "Branding"
        verbose_name_plural = "Branding"

    def __str__(self):
        return f"Branding de {self.tenant.name}"
