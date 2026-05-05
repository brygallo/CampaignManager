"""Generic views: home dashboard, Select2 AutoResponse, error pages."""
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render
from django.views.generic import TemplateView
from django_select2.views import AutoResponseView as BaseAutoResponseView


class AutoResponseView(BaseAutoResponseView):
    """Handle Select2 dependent-field requests and multi-value queries."""

    def get_queryset(self):
        for key, value in self.request.GET.items():
            if key == "field_id":
                continue
            key_tuple = key.split("-")
            if len(key_tuple) == 3:
                self.widget.dependent_fields.update({key: key_tuple[2]})

        kwargs = {
            model_field_name: self.request.GET.get(form_field_name)
            for form_field_name, model_field_name in self.widget.dependent_fields.items()
            if form_field_name in self.request.GET
            and self.request.GET.get(form_field_name, "") != ""
        }
        kwargs.update(
            {
                f"{model_field_name}__in": self.request.GET.getlist(
                    f"{form_field_name}[]", []
                )
                for form_field_name, model_field_name in self.widget.dependent_fields.items()
            }
        )
        return self.widget.filter_queryset(
            self.request,
            self.term,
            self.queryset,
            **{key: value for key, value in kwargs.items() if value},
        )


@login_required
def home(request):
    """Dashboard landing page: KPI cards + upcoming elections + recent campaigns + charts."""
    from django.db.models import Count
    from django.db.models.functions import TruncMonth

    from apps.campaigns.models import Campaign, Candidate, Election
    from apps.campaigns.workflows import CampaignWorkflow
    from apps.territorial_ads.models import PhysicalAdvertisement
    from apps.territorial_ads.workflows import PhysicalAdWorkflow

    today = date.today()
    horizon = today + timedelta(days=90)

    upcoming_elections_qs = Election.objects.filter(
        election_date__gte=today, election_date__lte=horizon
    ).order_by("election_date")

    stats = {
        "campaigns": Campaign.objects.count(),
        "candidates": Candidate.objects.count(),
        "ads": PhysicalAdvertisement.objects.count(),
        "elections_upcoming": upcoming_elections_qs.count(),
    }

    recent_campaigns = (
        Campaign.objects
        .select_related("candidate", "election", "movement")
        .order_by("-created_date")[:5]
    )

    # Trend: campaigns created per month, last 6 months (oldest -> newest).
    six_months_ago = (today.replace(day=1) - timedelta(days=180)).replace(day=1)
    monthly = (
        Campaign.objects
        .filter(created_date__gte=six_months_ago)
        .annotate(month=TruncMonth("created_date"))
        .values("month")
        .annotate(total=Count("id"))
        .order_by("month")
    )
    months_index = {row["month"].strftime("%Y-%m"): row["total"] for row in monthly}
    month_labels, month_values = [], []
    cursor = six_months_ago
    es_months = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    for _ in range(6):
        key = cursor.strftime("%Y-%m")
        month_labels.append(es_months[cursor.month - 1])
        month_values.append(months_index.get(key, 0))
        # advance one month
        next_year = cursor.year + (1 if cursor.month == 12 else 0)
        next_month = 1 if cursor.month == 12 else cursor.month + 1
        cursor = cursor.replace(year=next_year, month=next_month)

    # Distribution: physical ads by state (workflow choices order).
    ad_workflow = PhysicalAdWorkflow()
    ad_state_counts = dict(
        PhysicalAdvertisement.objects
        .values_list("state")
        .annotate(total=Count("id"))
        .values_list("state", "total")
    )
    ad_distribution = [
        {"label": label, "value": ad_state_counts.get(value, 0)}
        for value, label in ad_workflow.choices
    ]

    # Distribution: campaigns by visible state.
    campaign_workflow = CampaignWorkflow()
    campaign_state_counts = dict(
        Campaign.objects
        .values_list("state")
        .annotate(total=Count("id"))
        .values_list("state", "total")
    )
    campaign_distribution = [
        {"label": label, "value": campaign_state_counts.get(value, 0)}
        for value, label in campaign_workflow.choices
    ]

    context = {
        "stats": stats,
        "upcoming_elections": list(upcoming_elections_qs[:5]),
        "recent_campaigns": list(recent_campaigns),
        "today": today,
        "chart_data": {
            "trend": {"labels": month_labels, "values": month_values},
            "ads": ad_distribution,
            "campaigns": campaign_distribution,
        },
        "breadcrumbs": [("Inicio", None)],
    }
    return render(request, "home.html", context)


# Visual metadata applied to each menu group/leaf in the SuperAdmin landing.
# Keys match the lowercased item.name from menu.yaml. When a key is missing,
# defaults defined in module_list.html are used.
SUPERADMIN_MODULE_META = {
    # Group-level metadata (sections from menu.yaml)
    "campañas": {"icon": "flag", "color": "primary", "description": "Campañas, candidatos, elecciones y movimientos políticos."},
    "control territorial": {"icon": "geolocation", "color": "success", "description": "Publicidad y operaciones en territorio."},
    "sistema": {"icon": "setting-2", "color": "info", "description": "Cuentas, roles, permisos y auditoría del sistema."},
    # Leaf-level metadata
    "campañas electorales": {"icon": "flag", "color": "primary", "description": "Gestiona campañas activas y archivadas."},
    "candidatos": {"icon": "user-tick", "color": "success", "description": "Personas que postulan a cargos."},
    "elecciones": {"icon": "element-equal", "color": "info", "description": "Periodos y procesos electorales."},
    "movimientos políticos": {"icon": "abstract-26", "color": "warning", "description": "Organizaciones políticas registradas."},
    "cargos": {"icon": "medal-star", "color": "danger", "description": "Posiciones disputadas en cada elección."},
    "publicidad física": {"icon": "billboard", "color": "success", "description": "Vallas, lonas y soportes publicitarios en campo."},
    "usuarios": {"icon": "profile-circle", "color": "primary", "description": "Cuentas, datos y estado de los usuarios."},
    "grupos": {"icon": "people", "color": "success", "description": "Roles agrupando permisos por función."},
    "permisos": {"icon": "shield-tick", "color": "info", "description": "Permisos disponibles en el sistema."},
    "auditoría": {"icon": "time", "color": "warning", "description": "Trazabilidad de acciones realizadas."},
    "reglas de auditoría": {"icon": "rule", "color": "danger", "description": "Configura qué eventos se registran."},
}


class SuperAdminLandingView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """Pattern P1: card grid of registered SuperAdmin modules.

    Reads the global ``menu_tree`` (provided by superadmin's context processor)
    and enriches each entry with visual metadata from ``SUPERADMIN_MODULE_META``.
    Only ``is_staff`` users may see this landing.
    """

    template_name = "superadmin/module_list.html"

    def test_func(self):
        return self.request.user.is_staff

    def _decorate(self, items):
        decorated = []
        for item in items or []:
            meta = SUPERADMIN_MODULE_META.get((item.get("name") or "").lower(), {})
            decorated.append(
                {
                    "name": item.get("name"),
                    "url": item.get("url"),
                    "is_group": item.get("is_group"),
                    "submenus": self._decorate(item.get("submenus")),
                    "icon": meta.get("icon", item.get("icon") or "element-11"),
                    "color": meta.get("color", "primary"),
                    "description": meta.get("description", ""),
                }
            )
        return decorated

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        menu_tree = self.request.session.get("__noop__") or kwargs.get("menu_tree")
        # menu_tree comes from the superadmin context processor; re-decorate it.
        from superadmin.context_processors import menu as menu_cp

        raw = menu_cp(self.request).get("menu_tree", [])
        context["sections"] = self._decorate(raw)
        context["page_title"] = "Panel de administración"
        context["breadcrumbs"] = [("Inicio", "/"), ("Panel de administración", None)]
        return context


def error_403(request, exception=None):
    return render(request, "errors/403.html", status=403)


def error_404(request, exception=None):
    return render(request, "errors/404.html", status=404)


def error_500(request):
    return render(request, "errors/500.html", status=500)
