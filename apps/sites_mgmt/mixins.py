"""Mixins reutilizables para modelos y vistas relacionados con Site."""
from django.db import models


class SiteScopedModel(models.Model):
    """Mixin abstracto: añade FK a Site para multi-sitio suave."""

    site = models.ForeignKey(
        "sites_mgmt.Site",
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="Sitio",
    )

    class Meta:
        abstract = True


class SiteScopedListMixin:
    """Filtra automáticamente el queryset por `request.active_site`."""

    def get_queryset(self):
        qs = super().get_queryset()
        site = getattr(self.request, "active_site", None)
        if site and any(f.name == "site" for f in qs.model._meta.fields):
            qs = qs.filter(site=site)
        return qs


class SiteScopedFormMixin:
    """Pre-llena `site` en formularios cuando existe un Site activo."""

    def get_initial(self):
        initial = super().get_initial()
        site = getattr(self.request, "active_site", None)
        if site and "site" not in initial:
            initial["site"] = site.pk
        return initial
