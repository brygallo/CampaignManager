"""Views: login, logout, current user profile, password management, permission matrix."""
from django.apps import apps
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.models import Permission
from django.contrib.auth.views import PasswordChangeView as AuthPasswordChangeView
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django.views.generic import UpdateView

from .forms import EmailOrUsernameAuthenticationForm, UserPermissionForm

User = get_user_model()


def _site_urls_for(model, instance, user=None):
    """Resolve list/detail/update/delete URLs of a model registered in superadmin."""
    try:
        from superadmin import site as superadmin_site
        from superadmin.shortcuts import get_urls_of_site
    except ImportError:
        return {}
    if not superadmin_site.is_registered(model):
        return {}
    model_site = superadmin_site.get_modelsite(model)
    return get_urls_of_site(model_site, object=instance, user=user)


@csrf_protect
@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect(request.GET.get("next") or "/")
    form = EmailOrUsernameAuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        auth_login(request, form.get_user())
        return redirect(request.POST.get("next") or request.GET.get("next") or "/")
    return render(request, "registration/login.html", {"form": form, "next": request.GET.get("next", "")})


@require_http_methods(["POST"])
def logout_view(request):
    auth_logout(request)
    return redirect(reverse_lazy("authentication:login"))


@login_required
def profile_view(request):
    return render(request, "authentication/profile.html", {"profile": request.user.profile})


# ---------------------------------------------------------------------------
# Password change (authenticated)
# ---------------------------------------------------------------------------

class PasswordChangeView(LoginRequiredMixin, AuthPasswordChangeView):
    """Pattern P3: password change for the current user inside the app shell."""

    template_name = "authentication/password_change_form.html"
    success_url = reverse_lazy("authentication:password_change_done")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "La contraseña se actualizó correctamente.")
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Cambiar contraseña"
        context["breadcrumbs"] = [
            ("Inicio", "/"),
            ("Mi perfil", reverse_lazy("authentication:profile")),
            ("Cambiar contraseña", None),
        ]
        return context


@login_required
def password_change_done(request):
    return render(
        request,
        "authentication/password_change_done.html",
        {
            "page_title": "Contraseña actualizada",
            "breadcrumbs": [
                ("Inicio", "/"),
                ("Mi perfil", reverse_lazy("authentication:profile")),
                ("Contraseña actualizada", None),
            ],
        },
    )


# ---------------------------------------------------------------------------
# User permissions matrix (Pattern P5)
# ---------------------------------------------------------------------------

# Standard CRUD action codes that get a dedicated column in the matrix.
STANDARD_PERM_ACTIONS = ("view", "add", "change", "delete")
STANDARD_PERM_LABELS = {
    "view": "Ver",
    "add": "Crear",
    "change": "Editar",
    "delete": "Eliminar",
}


def _build_permission_matrix(direct_perm_ids, group_perm_map=None):
    """Group every Permission by app/model for rendering the matrix.

    ``direct_perm_ids``: iterable of Permission ids assigned directly to
    the holder (a User's ``user_permissions`` or a Group's ``permissions``).
    ``group_perm_map``: optional ``{permission_id: [group_name, ...]}`` to
    show inheritance markers; pass ``None`` when the holder is a Group.

    Returns a list of dicts ``{app_label, app_name, models}`` where each
    model contains ``{model_name, model_label, standard, custom}``.
    """
    direct_perm_ids = set(direct_perm_ids)
    group_perm_map = group_perm_map or {}

    permissions = (
        Permission.objects
        .select_related("content_type")
        .order_by("content_type__app_label", "content_type__model", "codename")
    )

    apps_map = {}
    for perm in permissions:
        ct = perm.content_type
        app_label = ct.app_label
        model_name = ct.model

        try:
            app_config = apps.get_app_config(app_label)
            app_name = str(app_config.verbose_name).capitalize()
        except LookupError:
            app_name = app_label

        model_class = ct.model_class()
        if model_class is not None:
            model_label = str(model_class._meta.verbose_name_plural).capitalize()
        else:
            model_label = model_name

        # Detect action prefix (view_user / add_user / custom_codename)
        codename = perm.codename
        action = codename.split("_", 1)[0] if "_" in codename else codename
        is_standard = action in STANDARD_PERM_ACTIONS and codename == f"{action}_{model_name}"

        entry = {
            "id": perm.id,
            "codename": codename,
            "name": perm.name,
            "content_type_id": ct.id,
            "has_direct": perm.id in direct_perm_ids,
            "via_groups": group_perm_map.get(perm.id, []),
            "action": action,
        }

        app_dict = apps_map.setdefault(
            app_label,
            {"app_label": app_label, "app_name": app_name, "models": {}},
        )
        model_dict = app_dict["models"].setdefault(
            model_name,
            {
                "model_name": model_name,
                "model_label": model_label,
                "standard": {a: None for a in STANDARD_PERM_ACTIONS},
                "custom": [],
            },
        )
        if is_standard:
            model_dict["standard"][action] = entry
        else:
            model_dict["custom"].append(entry)

    # Convert to ordered lists.
    apps_list = []
    for app_label in sorted(apps_map):
        a = apps_map[app_label]
        models_list = sorted(a["models"].values(), key=lambda m: m["model_label"])
        apps_list.append(
            {
                "app_label": a["app_label"],
                "app_name": a["app_name"],
                "models": models_list,
            }
        )
    return apps_list


class UserPermissionView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Pattern P5: edit groups + direct permissions of a user via a matrix."""

    model = User
    form_class = UserPermissionForm
    slug_field = "username"
    slug_url_kwarg = "username"
    template_name = "authentication/user/permission_form.html"

    def test_func(self):
        return self.request.user.is_staff

    def get_success_url(self):
        return reverse_lazy(
            "authentication:user_permissions",
            kwargs={"username": self.object.username},
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        target_user = self.object or self.get_object()
        direct_ids = target_user.user_permissions.values_list("id", flat=True)
        group_perm_map = {}
        for group in target_user.groups.prefetch_related("permissions"):
            for perm in group.permissions.all():
                group_perm_map.setdefault(perm.id, []).append(group.name)
        context["target_user"] = target_user
        context["target_user_urls"] = _site_urls_for(User, target_user, user=self.request.user)
        context["permission_groups"] = _build_permission_matrix(direct_ids, group_perm_map)
        context["standard_actions"] = STANDARD_PERM_ACTIONS
        context["standard_labels"] = STANDARD_PERM_LABELS
        context["page_title"] = f"Permisos de {target_user.get_full_name() or target_user.username}"
        site_urls = context["target_user_urls"]
        context["breadcrumbs"] = [
            ("Inicio", "/"),
            ("Panel administrativo", reverse_lazy("superadmin_home")),
            ("Usuarios", site_urls.get("list")),
            (target_user.get_full_name() or target_user.username, site_urls.get("detail")),
            ("Permisos", None),
        ]
        return context

    def form_valid(self, form):
        if not self.request.user.is_staff:
            raise PermissionDenied
        self.object = form.save()  # persists groups via the form
        # Update direct permissions from POST (perm_<codename>=<content_type_id>)
        prefix = "perm_"
        target_codenames = [
            key[len(prefix):]
            for key in self.request.POST
            if key.startswith(prefix)
        ]
        new_perms = list(Permission.objects.filter(codename__in=target_codenames))
        # Validate: keep only perms whose codename matches what was posted (avoid
        # collisions across content types, since codename alone is not unique).
        posted_pairs = {
            (key[len(prefix):], self.request.POST[key])
            for key in self.request.POST
            if key.startswith(prefix)
        }
        new_perms = [
            p for p in new_perms
            if (p.codename, str(p.content_type_id)) in posted_pairs
        ]
        self.object.user_permissions.set(new_perms)
        messages.success(self.request, "Permisos actualizados correctamente.")
        return redirect(self.get_success_url())


def _resolve_posted_permissions(post_data):
    """Translate ``perm_<codename>=<content_type_id>`` POST keys to Permission qs."""
    prefix = "perm_"
    posted_pairs = {
        (key[len(prefix):], post_data[key])
        for key in post_data
        if key.startswith(prefix)
    }
    if not posted_pairs:
        return []
    codenames = [c for c, _ct in posted_pairs]
    candidates = Permission.objects.filter(codename__in=codenames).select_related("content_type")
    return [p for p in candidates if (p.codename, str(p.content_type_id)) in posted_pairs]


class GroupPermissionView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Pattern P5: edit the permissions assigned to a Group."""

    model = Group
    fields = ()  # POST handled manually (perm_<codename> keys)
    template_name = "authentication/group/permission_form.html"

    def test_func(self):
        return self.request.user.is_staff

    def get_success_url(self):
        return reverse_lazy(
            "authentication:group_permissions",
            kwargs={"pk": self.object.pk},
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        group = self.object or self.get_object()
        direct_ids = group.permissions.values_list("id", flat=True)
        context["target_group"] = group
        context["target_group_urls"] = _site_urls_for(Group, group, user=self.request.user)
        context["permission_groups"] = _build_permission_matrix(direct_ids, group_perm_map=None)
        context["standard_actions"] = STANDARD_PERM_ACTIONS
        context["standard_labels"] = STANDARD_PERM_LABELS
        context["page_title"] = f"Permisos del grupo {group.name}"
        site_urls = context["target_group_urls"]
        context["breadcrumbs"] = [
            ("Inicio", "/"),
            ("Panel administrativo", reverse_lazy("superadmin_home")),
            ("Grupos", site_urls.get("list")),
            (group.name, site_urls.get("detail")),
            ("Permisos", None),
        ]
        return context

    def form_valid(self, form):
        if not self.request.user.is_staff:
            raise PermissionDenied
        self.object.permissions.set(_resolve_posted_permissions(self.request.POST))
        messages.success(self.request, "Permisos del grupo actualizados correctamente.")
        return redirect(self.get_success_url())
