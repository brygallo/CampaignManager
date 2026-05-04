"""Generic views: home dashboard, Select2 AutoResponse, error pages."""
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
    """Dashboard landing page with summary cards for the active Site."""
    context = {
        "breadcrumbs": [("Inicio", None)],
    }
    return render(request, "home.html", context)


# Visual metadata applied to each menu group/leaf in the SuperAdmin landing.
# Keys match the lowercased item.name from menu.yaml. When a key is missing,
# defaults defined in module_list.html are used.
SUPERADMIN_MODULE_META = {
    # Group-level metadata (sections from menu.yaml)
    "campañas": {"icon": "flag", "color": "primary", "description": "Campañas, candidatos, elecciones y movimientos políticos."},
    "sistema": {"icon": "setting-2", "color": "info", "description": "Cuentas, roles, permisos y auditoría del sistema."},
    # Leaf-level metadata
    "campañas electorales": {"icon": "flag", "color": "primary", "description": "Gestiona campañas activas y archivadas."},
    "candidatos": {"icon": "user-tick", "color": "success", "description": "Personas que postulan a cargos."},
    "elecciones": {"icon": "element-equal", "color": "info", "description": "Periodos y procesos electorales."},
    "movimientos políticos": {"icon": "abstract-26", "color": "warning", "description": "Organizaciones políticas registradas."},
    "cargos": {"icon": "medal-star", "color": "danger", "description": "Posiciones disputadas en cada elección."},
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
