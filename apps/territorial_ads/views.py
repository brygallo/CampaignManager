"""Map view for physical advertisements.

Single-page Leaflet map showing one pin per ``PhysicalAdvertisement``: the
installed coordinates when present, otherwise the offered coordinates. The
same map also surfaces ``AdvertisingRefusal`` pins so canvassers can see
spots where owners have already declined.
"""
from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from apps.campaigns.active import scope_queryset_to_active_campaign
from apps.campaigns.querysets import visible_campaign_choices
from superadmin.shortcuts import get_urls_of_site
from superadmin.sites import site as superadmin_site

from core.map_mixins import (
    MapAjaxCreateMixin,
    MapAjaxUpdateMixin,
    MapInitialLocationMixin,
)

from .forms import AdvertisingRefusalForm
from .models import AdvertisingRefusal, PhysicalAdvertisement


class PhysicalAdMapInitialLocationMixin(MapInitialLocationMixin):
    """Prefill offered coordinates when the create form is opened from the map."""

    coordinate_initial_fields = ("offered_latitude", "offered_longitude")
    map_location_field = "offered_location"


class PhysicalAdMapAjaxCreateMixin(MapAjaxCreateMixin):
    map_form_template_name = "territorial_ads/_map_create_form.html"
    map_detail_url_name = "site:territorial_ads_physicaladvertisement_"


class PhysicalAdMapAjaxUpdateMixin(MapAjaxUpdateMixin):
    map_form_template_name = "territorial_ads/_map_create_form.html"


class RefusalMapAjaxUpdateMixin(MapAjaxUpdateMixin):
    map_form_template_name = "territorial_ads/_map_refusal_form.html"


STATE_COLORS = {
    0: "#f1416c",  # RECHAZADA
    1: "#3e97ff",  # OFRECIDA
    2: "#7239ea",  # APROBADA
    3: "#ffc700",  # PENDIENTE_INSTALACION
    4: "#50cd89",  # INSTALADA
    5: "#fd7e14",  # DAÑADA
    6: "#7e8299",  # RETIRADA
}

REFUSAL_COLOR = "#7e8299"
REFUSAL_ICON = "cross-square"

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
        context["page_title"] = "Mapa de publicidad territorial"
        context["breadcrumbs"] = [
            ("Inicio", "/"),
            ("Publicidad territorial", None),
            ("Mapa", None),
        ]
        context["campaigns"] = visible_campaign_choices(self.request.user)
        context["selected_campaign_id"] = (
            self.request.GET.get("campaign")
            or (
                str(self.request.active_campaign.pk)
                if getattr(self.request, "active_campaign", None)
                else ""
            )
        )
        context["states"] = PhysicalAdvertisement.workflow.choices
        return context


class PhysicalAdMapDataView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "territorial_ads.view_physicaladvertisement"
    # Same rationale as FieldSurveyMapDataView.MAX_POINTS — hard cap so the
    # Leaflet client doesn't choke on huge payloads. Frontend surfaces a
    # banner when truncation happens.
    MAX_POINTS = 5000

    def get(self, request, *args, **kwargs):
        queryset = (
            PhysicalAdvertisement.objects.select_related("campaign", "advertisement_type")
            .filter(
                Q(installed_latitude__isnull=False, installed_longitude__isnull=False)
                | Q(offered_latitude__isnull=False, offered_longitude__isnull=False)
            )
        )
        # Active-campaign fallback: explicit ``?campaign=`` in the URL wins
        # (deep links keep working), otherwise the navbar's active campaign
        # is applied so the map matches the rest of the UI.
        campaign_id = request.GET.get("campaign")
        if not campaign_id and getattr(request, "active_campaign", None):
            campaign_id = str(request.active_campaign.pk)
        if campaign_id:
            queryset = queryset.filter(campaign_id=campaign_id)
        state = request.GET.get("state")
        if state:
            queryset = queryset.filter(state=state)

        # Refusals share the same map but live in a different model; we
        # build their queryset early so the count() feeds the truncation
        # budget below. They are hidden when a state filter is set because
        # AdvertisingRefusal doesn't participate in the PhysicalAdvertisement
        # workflow.
        refusal_qs = None
        refusal_total = 0
        if not state:
            refusal_qs = AdvertisingRefusal.objects.select_related("campaign").filter(
                latitude__isnull=False, longitude__isnull=False, is_active=True
            )
            if campaign_id:
                refusal_qs = refusal_qs.filter(campaign_id=campaign_id)
            refusal_total = refusal_qs.count()

        ad_total = queryset.count()
        grand_total = ad_total + refusal_total
        truncated = grand_total > self.MAX_POINTS
        if truncated:
            ad_cap = int(self.MAX_POINTS * ad_total / grand_total)
            refusal_cap = self.MAX_POINTS - ad_cap
            queryset = queryset.order_by("-id")[:ad_cap]
            if refusal_qs is not None:
                refusal_qs = refusal_qs.order_by("-id")[:refusal_cap]

        # Reuse the superadmin URL-building helper so the perm checks match what
        # the list view applies (it returns ``update``/``delete`` only when the
        # user has the corresponding ``change_`` / ``delete_`` perm).
        ad_site = superadmin_site.get_modelsite(PhysicalAdvertisement)
        refusal_site = superadmin_site.get_modelsite(AdvertisingRefusal)

        ads = []
        for ad in queryset:
            if ad.installed_latitude is not None and ad.installed_longitude is not None:
                lat, lng, kind = ad.installed_latitude, ad.installed_longitude, "instalada"
            else:
                lat, lng, kind = ad.offered_latitude, ad.offered_longitude, "ofrecida"
            ad_urls = get_urls_of_site(ad_site, object=ad, user=request.user)
            item = {
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
                "marker_kind": "ad",
            }
            if "update" in ad_urls and not ad.is_state_read_only():
                item["update_url"] = ad_urls["update"]
            if "delete" in ad_urls:
                item["delete_url"] = ad_urls["delete"]
            ads.append(item)

        if refusal_qs is not None:
            for refusal in refusal_qs:
                refusal_urls = get_urls_of_site(refusal_site, object=refusal, user=request.user)
                item = {
                    "id": refusal.id,
                    "lat": float(refusal.latitude),
                    "lng": float(refusal.longitude),
                    "kind": "rechazo",
                    "label": refusal.owner_reference or f"Rechazo #{refusal.id}",
                    "state_code": None,
                    "state_label": "No quiere publicidad",
                    "color": REFUSAL_COLOR,
                    "type_icon": REFUSAL_ICON,
                    "type_label": "Rechazo",
                    "url": reverse("territorial_ads:refusal_popup", kwargs={"pk": refusal.id}),
                    "campaign": refusal.campaign.name if refusal.campaign_id else "",
                    "address": refusal.owner_reference or "",
                    "marker_kind": "refusal",
                }
                if "update" in refusal_urls:
                    item["update_url"] = refusal_urls["update"]
                if "delete" in refusal_urls:
                    item["delete_url"] = refusal_urls["delete"]
                ads.append(item)

        return JsonResponse(
            {
                "ads": ads,
                "truncated": truncated,
                "total": grand_total,
                "returned": len(ads),
                "limit": self.MAX_POINTS,
            }
        )


class PhysicalAdMapPopupView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Render a rich HTML card for a single ad, used inside the map's modal."""

    permission_required = "territorial_ads.view_physicaladvertisement"

    def get(self, request, pk, *args, **kwargs):
        queryset = scope_queryset_to_active_campaign(
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
            request,
        )
        ad = get_object_or_404(
            queryset,
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


class AdvertisingRefusalCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """AJAX-only create endpoint for refusal pins, opened from the map."""

    permission_required = "territorial_ads.add_advertisingrefusal"
    template_name = "territorial_ads/_map_refusal_form.html"

    def _initial_from_query(self, request):
        initial = {}
        for source, target in (
            ("offered_latitude", "latitude"),
            ("offered_longitude", "longitude"),
            ("latitude", "latitude"),
            ("longitude", "longitude"),
        ):
            value = request.GET.get(source)
            if value and target not in initial:
                initial[target] = value
        return initial

    def _render_form(self, request, form):
        return render_to_string(
            self.template_name,
            {"form": form, "action_url": request.get_full_path()},
            request=request,
        )

    def _bind_form(self, request, *args, **kwargs):
        if args:
            data = args[0].copy()
            active = getattr(request, "active_campaign", None)
            if active is not None:
                data["campaign"] = str(active.pk)
            args = (data,) + args[1:]
        form = AdvertisingRefusalForm(*args, **kwargs)
        active = getattr(request, "active_campaign", None)
        if active is None:
            return form
        field = form.fields.get("campaign")
        if field is None:
            return form
        field.queryset = field.queryset.filter(pk=active.pk)
        if hasattr(field.widget, "queryset"):
            field.widget.queryset = field.queryset
        field.initial = active.pk
        field.widget = forms.HiddenInput()
        field.required = True
        return form

    def get(self, request, *args, **kwargs):
        initial = self._initial_from_query(request)
        active = getattr(request, "active_campaign", None)
        if active is not None:
            initial.setdefault("campaign", active.pk)
        form = self._bind_form(request, initial=initial)
        return JsonResponse({"html": self._render_form(request, form)})

    def post(self, request, *args, **kwargs):
        form = self._bind_form(request, request.POST)
        if not form.is_valid():
            return JsonResponse(
                {"ok": False, "html": self._render_form(request, form)},
                status=400,
            )
        refusal = form.save(commit=False)
        if getattr(request, "active_campaign", None) is not None:
            refusal.campaign = request.active_campaign
        if request.user.is_authenticated:
            refusal.reported_by = request.user
        refusal.save()
        return JsonResponse(
            {
                "ok": True,
                "id": refusal.pk,
                "label": refusal.owner_reference or f"Rechazo #{refusal.pk}",
                "url": reverse("territorial_ads:refusal_popup", kwargs={"pk": refusal.pk}),
            }
        )


class AdvertisingRefusalPopupView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """HTML card for a refusal pin, rendered inside the map modal."""

    permission_required = "territorial_ads.view_advertisingrefusal"

    def get(self, request, pk, *args, **kwargs):
        queryset = scope_queryset_to_active_campaign(
            AdvertisingRefusal.objects.select_related("campaign", "reported_by"),
            request,
        )
        refusal = get_object_or_404(
            queryset,
            pk=pk,
        )
        html = render_to_string(
            "territorial_ads/_map_refusal_popup.html",
            {"refusal": refusal, "state_color": REFUSAL_COLOR},
            request=request,
        )
        return JsonResponse(
            {
                "html": html,
                "title": refusal.owner_reference or f"Rechazo #{refusal.pk}",
                "url": "",
            }
        )
