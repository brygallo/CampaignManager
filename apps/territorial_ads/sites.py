"""Register territorial advertising models in superadmin."""
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse

from superadmin.decorators import register

from core.base import BaseSite, DetailMapsMixin, HideEmptyFieldsetsMixin
from core.form_mixins import SaveOptionsMixin
from core.list_mixins import WorkflowStateFilterMixin

from .forms import PhysicalAdvertisementForm
from .models import AdvertisingCostType, PhysicalAdvertisement


class MapInitialLocationMixin:
    """Prefill offered coordinates when the create form is opened from the map."""

    coordinate_initial_fields = ("offered_latitude", "offered_longitude")
    allowed_map_layers = {"carto", "osm", "satellite"}

    def get_initial(self):
        initial = super().get_initial()
        for field in self.coordinate_initial_fields:
            value = self.request.GET.get(field)
            if value:
                initial[field] = value
        return initial

    def get_form(self, *args, **kwargs):
        form = super().get_form(*args, **kwargs)
        field = form.fields.get("offered_location")
        if not field:
            return form

        zoom = self.request.GET.get("map_zoom")
        if zoom:
            try:
                parsed_zoom = int(float(zoom))
            except (TypeError, ValueError):
                parsed_zoom = None
            if parsed_zoom is not None:
                field.widget.attrs["data-default-zoom"] = max(1, min(parsed_zoom, 20))

        layer = self.request.GET.get("map_layer")
        if layer in self.allowed_map_layers:
            field.widget.attrs["data-default-basemap"] = layer

        return form


class MapAjaxCreateMixin:
    """Render and submit the create form inside the map modal."""

    def _is_map_ajax(self):
        return self.request.headers.get("X-Map-Create") == "1"

    def _render_map_form(self, form):
        return render_to_string(
            "territorial_ads/_map_create_form.html",
            {"form": form, "action_url": self.request.get_full_path()},
            request=self.request,
        )

    def get(self, request, *args, **kwargs):
        if self._is_map_ajax():
            form = self.get_form()
            return JsonResponse({"html": self._render_map_form(form)})
        return super().get(request, *args, **kwargs)

    def form_invalid(self, form):
        if self._is_map_ajax():
            return JsonResponse(
                {"ok": False, "html": self._render_map_form(form)},
                status=400,
            )
        return super().form_invalid(form)

    def form_valid(self, form):
        response = super().form_valid(form)
        if self._is_map_ajax():
            return JsonResponse(
                {
                    "ok": True,
                    "id": self.object.pk,
                    "label": self.object.code or str(self.object),
                    "url": reverse(
                        "site:territorial_ads_physicaladvertisement_",
                        kwargs={"pk": self.object.pk},
                    ),
                }
            )
        return response


@register("territorial_ads.AdvertisingCostType")
class AdvertisingCostTypeSite(BaseSite):
    list_fields = ("code", "name", "order", "requires_amount", "is_active:Activo")
    detail_fields = {
        "Tipo de costo": (
            ("code", "name"),
            ("order", "requires_amount"),
        ),
    }
    search_params = ("code__icontains", "name__icontains")
    filter_fields = ("requires_amount", "is_active:Activo")


@register("territorial_ads.PhysicalAdvertisement")
class PhysicalAdvertisementSite(BaseSite):
    form_class = PhysicalAdvertisementForm
    form_template_name = "territorial_ads/physicaladvertisement_form.html"
    list_template_name = "territorial_ads/superadmin_physicaladvertisement_list.html"
    list_mixins = (WorkflowStateFilterMixin,)
    create_mixins = (MapInitialLocationMixin, MapAjaxCreateMixin, SaveOptionsMixin)
    detail_mixins = (HideEmptyFieldsetsMixin, DetailMapsMixin)

    always_visible_fieldsets = (
        "Publicidad",
        "Contacto que ofreció el lugar",
        "Ubicación ofrecida",
        "Seguimiento",
    )
    list_fields = (
        "code",
        "campaign",
        "owner_name",
        "cost_type:Costo",
        "get_state_display:Estado",
        "assigned_installer",
        "installer_team",
    )
    detail_fields = {
        "Publicidad": (
            ("campaign", "advertisement_type"),
            ("quantity",),
        ),
        "Contacto que ofreció el lugar": (
            ("owner_name", "owner_phone"),
            ("cost_type", "cost_amount"),
            ("offered_notes",),
        ),
        "Ubicación ofrecida": (
            ("address",),
            ("reference",),
            ("offered_latitude", "offered_longitude"),
            ("offered_photo",),
        ),
        "Seguimiento": (
            ("code", "get_state_display:Estado"),
        ),
        "Rechazo": (
            ("rejected_at", "rejected_by"),
            ("rejection_reason",),
        ),
        "Aprobación": (
            ("approved_by", "approved_at"),
            ("width_meters", "height_meters"),
            ("installation_instructions",),
        ),
        "Asignación de instalación": (
            ("assigned_installer", "installer_team"),
            ("assigned_by", "assigned_at"),
        ),
        "Instalación": (
            ("installation_photo",),
            ("installed_latitude", "installed_longitude"),
            ("installed_at", "installed_by"),
            ("installation_notes",),
        ),
        "Daño reportado": (
            ("damage_reported_at", "damage_reported_by"),
            ("damage_notes",),
            ("damage_photo",),
        ),
        "Retiro": (
            ("retired_at", "retired_by"),
        ),
    }
    search_params = (
        "code__icontains",
        "owner_name__icontains",
        "owner_phone__icontains",
        "address__icontains",
    )
    filter_fields = (
        "state",
        "campaign",
        "advertisement_type",
        "cost_type",
        "assigned_installer",
        "is_active",
    )
    detail_maps = (
        {
            "title": "Ubicaciones",
            "points": [
                {
                    "label": "Ofrecida",
                    "lat": "offered_latitude",
                    "lng": "offered_longitude",
                    "color": "#3388ff",
                },
                {
                    "label": "Instalada",
                    "lat": "installed_latitude",
                    "lng": "installed_longitude",
                    "color": "#198754",
                },
            ],
        },
    )
