"""Map view for physical advertisements.

Single-page Leaflet map showing one pin per ``PhysicalAdvertisement``: the
installed coordinates when present, otherwise the offered coordinates. The
same map also surfaces ``AdvertisingRefusal`` pins so canvassers can see
spots where owners have already declined.
"""
from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db import transaction
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

from .forms import (
    AdvertisingRefusalForm,
    BulkAssignInstallationForm,
    DirectInstallForm,
)
from .models import (
    AdvertisingRefusal,
    PhysicalAdvertisement,
    PhysicalAdvertisementUnit,
)


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
    5: "#7e8299",  # RETIRADA (auto: every unit retired)
}

# Unit (publicidad física) workflow colors: RETIRADA, PENDIENTE, INSTALADA, DANADA.
UNIT_STATE_COLORS = {
    0: "#7e8299",
    1: "#ffc700",
    2: "#50cd89",
    3: "#fd7e14",
}

REFUSAL_COLOR = "#7e8299"
REFUSAL_ICON = "cross-square"

# Every request (solicitud) pin shows the same generic icon; the advertising
# type icon belongs to each installed publicidad (unit) instead. Shape
# (diamond) + color (state) carry the meaning for requests.
REQUEST_ICON = "clipboard-list"

# Forward-path stepper for the REQUEST. RECHAZADA (0) and RETIRADA (6) are
# rendered separately as terminal alerts; damage now lives on each unit.
STEPPER_STEPS = (
    {"value": 1, "label": "Ofrecida", "icon": "send"},
    {"value": 2, "label": "Aprobada", "icon": "verify"},
    {"value": 3, "label": "Pendiente", "icon": "time"},
    {"value": 4, "label": "Instalada", "icon": "check-circle"},
)

def physicalad_detail_url(pk):
    return reverse("site:territorial_ads_physicaladvertisement_", kwargs={"pk": pk})


def refusal_detail_url(pk):
    return reverse("site:territorial_ads_advertisingrefusal_", kwargs={"pk": pk})


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
        # Requests and physical units are separate map concepts. A request
        # keeps its offered-location pin throughout its lifecycle, while each
        # installed unit gets its own evidence-location pin.
        queryset = (
            PhysicalAdvertisement.objects.select_related("campaign")
            .prefetch_related("items__advertisement_type", "items__units")
            # Same soft-delete contract as the refusal queryset below:
            # deactivated records must not surface on the map.
            .filter(is_active=True)
            .filter(
                offered_latitude__isnull=False, offered_longitude__isnull=False
            )
        )
        unit_qs = (
            PhysicalAdvertisementUnit.objects.select_related(
                "item__advertisement__campaign",
                "item__advertisement_type",
                "size",
            )
            .filter(
                item__advertisement__is_active=True,
                latitude__isnull=False,
                longitude__isnull=False,
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
            unit_qs = unit_qs.filter(item__advertisement__campaign_id=campaign_id)
        marker_kind = request.GET.get("kind", "")
        state = request.GET.get("state")
        if state and marker_kind != "refusal":
            queryset = queryset.filter(state=state)
            unit_qs = unit_qs.filter(item__advertisement__state=state)

        if marker_kind == "request":
            unit_qs = unit_qs.none()
        elif marker_kind == "publicity":
            queryset = queryset.none()
        elif marker_kind == "refusal":
            queryset = queryset.none()
            unit_qs = unit_qs.none()

        # Refusals share the same map but live in a different model; we
        # build their queryset early so the count() feeds the truncation
        # budget below. They are hidden when a state filter is set because
        # AdvertisingRefusal doesn't participate in the PhysicalAdvertisement
        # workflow.
        refusal_qs = None
        refusal_total = 0
        include_refusals = marker_kind == "refusal" or (
            marker_kind == "" and not state
        )
        if include_refusals and request.user.has_perm(
            "territorial_ads.view_advertisingrefusal"
        ):
            refusal_qs = AdvertisingRefusal.objects.select_related("campaign").filter(
                latitude__isnull=False, longitude__isnull=False, is_active=True
            )
            if campaign_id:
                refusal_qs = refusal_qs.filter(campaign_id=campaign_id)
            refusal_total = refusal_qs.count()

        ad_total = queryset.count()
        unit_total = unit_qs.count()
        grand_total = ad_total + unit_total + refusal_total
        truncated = grand_total > self.MAX_POINTS
        if truncated:
            ad_cap = int(self.MAX_POINTS * ad_total / grand_total)
            unit_cap = int(self.MAX_POINTS * unit_total / grand_total)
            refusal_cap = self.MAX_POINTS - ad_cap - unit_cap
            queryset = queryset.order_by("-id")[:ad_cap]
            unit_qs = unit_qs.order_by("-id")[:unit_cap]
            if refusal_qs is not None:
                refusal_qs = refusal_qs.order_by("-id")[:refusal_cap]

        # Reuse the superadmin URL-building helper so the perm checks match what
        # the list view applies (it returns ``update``/``delete`` only when the
        # user has the corresponding ``change_`` / ``delete_`` perm).
        ad_site = superadmin_site.get_modelsite(PhysicalAdvertisement)
        refusal_site = superadmin_site.get_modelsite(AdvertisingRefusal)

        ads = []
        for ad in queryset:
            ad_urls = get_urls_of_site(ad_site, object=ad, user=request.user)
            item = {
                "id": ad.id,
                "marker_key": f"request:{ad.id}",
                "lat": float(ad.offered_latitude),
                "lng": float(ad.offered_longitude),
                "kind": "solicitud",
                "label": ad.code or str(ad),
                "state_code": ad.state,
                "state_label": ad.get_state_display(),
                "color": STATE_COLORS.get(ad.state, "#3388ff"),
                "type_icon": REQUEST_ICON,
                "type_label": ad.items_summary,
                "url": physicalad_detail_url(ad.id),
                "campaign": ad.campaign.name if ad.campaign_id else "",
                "address": ad.address or "",
                "marker_kind": "ad",
            }
            # Read-only workflow states reject the update view (409), so the
            # map must not offer the edit action for them.
            if "update" in ad_urls and not ad.is_state_read_only():
                item["update_url"] = ad_urls["update"]
            if "delete" in ad_urls:
                item["delete_url"] = ad_urls["delete"]
            ads.append(item)

        for unit in unit_qs:
            ad = unit.item.advertisement
            ads.append(
                {
                    "id": unit.id,
                    "marker_key": f"unit:{unit.id}",
                    "lat": float(unit.latitude),
                    "lng": float(unit.longitude),
                    "kind": "publicidad",
                    "label": f"{unit.code or ad.code} · {unit.display_label}",
                    "state_code": unit.state,
                    "state_label": unit.get_state_display(),
                    "color": UNIT_STATE_COLORS.get(unit.state, "#50cd89"),
                    "type_icon": unit.item.advertisement_type.icon,
                    "type_label": unit.display_label,
                    # Unit pins open the request detail (it lists every unit
                    # with its evidence and per-unit actions).
                    "url": physicalad_detail_url(ad.id),
                    "campaign": ad.campaign.name if ad.campaign_id else "",
                    "address": ad.address or "",
                    "marker_kind": "unit",
                }
            )

        if refusal_qs is not None:
            for refusal in refusal_qs:
                refusal_urls = get_urls_of_site(refusal_site, object=refusal, user=request.user)
                item = {
                    "id": refusal.id,
                    "marker_key": f"refusal:{refusal.id}",
                    "lat": float(refusal.latitude),
                    "lng": float(refusal.longitude),
                    "kind": "rechazo",
                    "label": refusal.owner_reference or f"Rechazo #{refusal.id}",
                    "state_code": None,
                    "state_label": "No quiere publicidad",
                    "color": REFUSAL_COLOR,
                    "type_icon": REFUSAL_ICON,
                    "type_label": "Rechazo",
                    # Full detail page so the click opens the same modal as
                    # requests/units (the map JS uses openDetailModal).
                    "url": refusal_detail_url(refusal.id),
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
                "cost_type",
                "approved_by",
                "assigned_installer",
                "assigned_by",
                "installed_by",
                "rejected_by",
                "damage_reported_by",
                "retired_by",
            ).prefetch_related(
                "items__advertisement_type",
                "items__units__size",
                "items__units__installed_by",
                "installation_photos",
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
        installed = ad.installed_location
        if installed is not None:
            pin_kind = "instalada"
            pin_lat, pin_lng = installed
        elif ad.offered_latitude is not None and ad.offered_longitude is not None:
            pin_kind = "ofrecida"
            pin_lat, pin_lng = ad.offered_latitude, ad.offered_longitude
        else:
            pin_kind, pin_lat, pin_lng = None, None, None
        units = ad.units
        html = render_to_string(
            "territorial_ads/_map_popup.html",
            {
                "ad": ad,
                "units": units,
                "state_color": STATE_COLORS.get(ad.state, "#3388ff"),
                "stepper_steps": steps,
                "is_rejected": ad.state == 0,
                "is_retired": ad.state == 5,
                "type_icon": REQUEST_ICON,
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


class PhysicalAdBulkAssignView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Assign one installer to several APROBADA ads in a single step.

    AJAX endpoint behind the "Asignación masiva" button on the list view:
    GET returns the form HTML for the modal, POST runs the
    ``assign_installation`` transition for every selected ad atomically.
    """

    permission_required = "territorial_ads.assign_physicaladvertisement"
    raise_exception = True
    template_name = "territorial_ads/_bulk_assign_form.html"

    def _queryset(self, request):
        queryset = (
            PhysicalAdvertisement.objects.filter(
                is_active=True,
                state=PhysicalAdvertisement.workflow.APROBADA,
            )
            .select_related("campaign")
            .prefetch_related("items__advertisement_type")
            .order_by("-id")
        )
        active = getattr(request, "active_campaign", None)
        if active is not None:
            queryset = queryset.filter(campaign=active)
        return queryset

    def _render_form(self, request, form):
        return render_to_string(
            self.template_name,
            {"form": form, "action_url": reverse("territorial_ads:bulk_assign")},
            request=request,
        )

    def get(self, request, *args, **kwargs):
        queryset = self._queryset(request)
        form = BulkAssignInstallationForm(queryset=queryset)
        return JsonResponse(
            {"html": self._render_form(request, form), "count": queryset.count()}
        )

    def post(self, request, *args, **kwargs):
        form = BulkAssignInstallationForm(
            request.POST, queryset=self._queryset(request)
        )
        if not form.is_valid():
            return JsonResponse(
                {"ok": False, "html": self._render_form(request, form)},
                status=400,
            )
        installer = form.cleaned_data.get("assigned_installer")
        team = form.cleaned_data.get("installer_team") or ""
        ads = list(form.cleaned_data["advertisements"])
        with transaction.atomic():
            for ad in ads:
                ad.assign_installation(
                    user=request.user,
                    assigned_installer=installer.pk if installer else None,
                    installer_team=team,
                )
                ad.save()
        return JsonResponse({"ok": True, "count": len(ads)})


class DirectInstallCreateView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """One-step registration of an already-installed advertisement.

    Creates a fast-tracked request (keeping contact data and the audit
    trail) and its installed unit with photo + GPS + notes. Opened from the
    map's choice modal.
    """

    permission_required = (
        "territorial_ads.add_physicaladvertisement",
        "territorial_ads.install_physicaladvertisement",
    )
    raise_exception = True
    template_name = "territorial_ads/_map_direct_form.html"

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

    def _build_form(self, request, *args, **kwargs):
        form = DirectInstallForm(*args, **kwargs)
        active = getattr(request, "active_campaign", None)
        field = form.fields["campaign"]
        if active is not None:
            field.queryset = field.queryset.filter(pk=active.pk)
            field.initial = active.pk
            field.widget = forms.HiddenInput()
        return form

    def get(self, request, *args, **kwargs):
        initial = self._initial_from_query(request)
        active = getattr(request, "active_campaign", None)
        if active is not None:
            initial.setdefault("campaign", active.pk)
        form = self._build_form(request, initial=initial)
        return JsonResponse({"html": self._render_form(request, form)})

    def post(self, request, *args, **kwargs):
        data = request.POST.copy()
        active = getattr(request, "active_campaign", None)
        if active is not None:
            data["campaign"] = str(active.pk)
        form = self._build_form(request, data, request.FILES)
        if not form.is_valid():
            return JsonResponse(
                {"ok": False, "html": self._render_form(request, form)},
                status=400,
            )
        cleaned = form.cleaned_data
        with transaction.atomic():
            ad = PhysicalAdvertisement.objects.create(
                campaign=cleaned["campaign"],
                address=cleaned["address"],
                reference=cleaned.get("reference") or "",
                owner_name=cleaned["owner_name"],
                owner_phone=cleaned["owner_phone"],
                offered_latitude=cleaned["latitude"],
                offered_longitude=cleaned["longitude"],
            )
            item = ad.items.create(
                advertisement_type=cleaned["advertisement_type"], quantity=1
            )
            size = cleaned.get("size")
            approve_kwargs = {}
            if size is not None:
                approve_kwargs[f"item_size_{item.pk}_1"] = size.pk
            # Fast-track the request through the normal transitions so the
            # audit trail (who/when) stays consistent with the manual flow.
            ad.approve(user=request.user, **approve_kwargs)
            ad.save()
            ad.assign_installation(
                user=request.user, assigned_installer=request.user.pk
            )
            ad.save()
            unit = item.units.first()
            unit.mark_installed(
                user=request.user,
                photo=cleaned["photo"],
                latitude=cleaned["latitude"],
                longitude=cleaned["longitude"],
                notes=cleaned.get("notes") or "",
            )
            unit.save()
        return JsonResponse(
            {
                "ok": True,
                "id": ad.pk,
                "label": ad.code or str(ad),
                "url": physicalad_detail_url(ad.pk),
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
                # Full detail page, so the map modal can offer "open record"
                # for refusals just like it does for advertisements.
                "url": refusal_detail_url(refusal.pk),
            }
        )
