"""Map view for physical advertisements.

Single-page Leaflet map showing one pin per ``PhysicalAdvertisement``: the
installed coordinates when present, otherwise the offered coordinates.
"""
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from apps.campaigns.models import Campaign

from .models import PhysicalAdvertisement


STATE_COLORS = {
    0: "#f1416c",  # RECHAZADA
    1: "#3e97ff",  # OFRECIDA
    2: "#7239ea",  # APROBADA
    3: "#ffc700",  # PENDIENTE_INSTALACION
    4: "#50cd89",  # INSTALADA
    5: "#fd7e14",  # DAÑADA
    6: "#7e8299",  # RETIRADA
}

# Forward-path stepper. RECHAZADA (0) is rendered separately as a terminal state
# alert so it does not pollute the linear progress display.
STEPPER_STEPS = (
    {"value": 1, "label": "Ofrecida", "icon": "send"},
    {"value": 2, "label": "Aprobada", "icon": "verify"},
    {"value": 3, "label": "Pendiente", "icon": "time"},
    {"value": 4, "label": "Instalada", "icon": "check-circle"},
    {"value": 5, "label": "Dañada", "icon": "information-5"},
    {"value": 6, "label": "Retirada", "icon": "cross-square"},
)

def physicalad_detail_url(pk):
    return reverse("site:territorial_ads_physicaladvertisement_", kwargs={"pk": pk})


class PhysicalAdMapView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = "territorial_ads/map.html"
    permission_required = "territorial_ads.view_physicaladvertisement"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["campaigns"] = Campaign.objects.filter(is_active=True).order_by("name")
        context["states"] = PhysicalAdvertisement.workflow.choices
        return context


class PhysicalAdMapDataView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "territorial_ads.view_physicaladvertisement"

    def get(self, request, *args, **kwargs):
        queryset = (
            PhysicalAdvertisement.objects.select_related("campaign", "advertisement_type")
            .filter(
                Q(installed_latitude__isnull=False, installed_longitude__isnull=False)
                | Q(offered_latitude__isnull=False, offered_longitude__isnull=False)
            )
        )
        campaign_id = request.GET.get("campaign")
        if campaign_id:
            queryset = queryset.filter(campaign_id=campaign_id)
        state = request.GET.get("state")
        if state:
            queryset = queryset.filter(state=state)

        ads = []
        for ad in queryset:
            if ad.installed_latitude is not None and ad.installed_longitude is not None:
                lat, lng, kind = ad.installed_latitude, ad.installed_longitude, "instalada"
            else:
                lat, lng, kind = ad.offered_latitude, ad.offered_longitude, "ofrecida"
            ads.append(
                {
                    "id": ad.id,
                    "lat": float(lat),
                    "lng": float(lng),
                    "kind": kind,
                    "label": ad.code or str(ad),
                    "state_code": ad.state,
                    "state_label": ad.get_state_display(),
                    "color": STATE_COLORS.get(ad.state, "#3388ff"),
                    "type_icon": ad.advertisement_type.icon if ad.advertisement_type_id else "element-12",
                    "type_label": ad.advertisement_type.name if ad.advertisement_type_id else "",
                    "url": physicalad_detail_url(ad.id),
                    "campaign": ad.campaign.name if ad.campaign_id else "",
                    "address": ad.address or "",
                }
            )
        return JsonResponse({"ads": ads})


class PhysicalAdMapPopupView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Render a rich HTML card for a single ad, used inside the map's modal."""

    permission_required = "territorial_ads.view_physicaladvertisement"

    def get(self, request, pk, *args, **kwargs):
        ad = get_object_or_404(
            PhysicalAdvertisement.objects.select_related(
                "campaign",
                "advertisement_type",
                "cost_type",
                "approved_by",
                "assigned_installer",
                "assigned_by",
                "installed_by",
                "rejected_by",
                "damage_reported_by",
                "retired_by",
            ),
            pk=pk,
        )
        steps = [
            {
                **step,
                "is_done": step["value"] < ad.state,
                "is_current": step["value"] == ad.state,
            }
            for step in STEPPER_STEPS
        ]
        if ad.installed_latitude is not None and ad.installed_longitude is not None:
            pin_kind = "instalada"
            pin_lat, pin_lng = ad.installed_latitude, ad.installed_longitude
        elif ad.offered_latitude is not None and ad.offered_longitude is not None:
            pin_kind = "ofrecida"
            pin_lat, pin_lng = ad.offered_latitude, ad.offered_longitude
        else:
            pin_kind, pin_lat, pin_lng = None, None, None
        html = render_to_string(
            "territorial_ads/_map_popup.html",
            {
                "ad": ad,
                "state_color": STATE_COLORS.get(ad.state, "#3388ff"),
                "stepper_steps": steps,
                "is_rejected": ad.state == 0,
                "type_icon": ad.advertisement_type.icon if ad.advertisement_type_id else "element-12",
                "pin_kind": pin_kind,
                "pin_lat": pin_lat,
                "pin_lng": pin_lng,
            },
            request=request,
        )
        return JsonResponse(
            {
                "html": html,
                "title": ad.code or str(ad),
                "url": physicalad_detail_url(ad.id),
            }
        )
