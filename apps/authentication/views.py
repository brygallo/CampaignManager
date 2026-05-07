"""Views: login, logout, current user profile, password management, user permissions matrix."""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import PasswordChangeView as AuthPasswordChangeView
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django.views.generic import UpdateView

from .forms import EmailOrUsernameAuthenticationForm, UserPermissionForm
from .permissions import build_user_permission_context, resolve_posted_permissions

User = get_user_model()


def _safe_redirect_target(request, candidate):
    """Return ``candidate`` only if it is an internal URL; otherwise ``"/"``."""
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return "/"


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
        return redirect(_safe_redirect_target(request, request.GET.get("next")))
    form = EmailOrUsernameAuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        auth_login(request, form.get_user())
        target = request.POST.get("next") or request.GET.get("next")
        return redirect(_safe_redirect_target(request, target))
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


class UserPermissionView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Edit a user's groups + direct permissions through the shared matrix.

    Renders inside ``base/base_form.html`` via a stub ``site`` context so the
    standard toolbar (breadcrumbs, save buttons, sticky bar) works without
    registering the view in superadmin.
    """

    model = User
    form_class = UserPermissionForm
    slug_field = "username"
    slug_url_kwarg = "username"
    template_name = "authentication/user/permission_form.html"

    def test_func(self):
        user = self.request.user
        if not (user.is_authenticated and user.is_active):
            return False
        if user.is_superuser:
            return True
        target = self.get_object()
        # Staff cannot edit a superuser's permissions.
        if target.is_superuser:
            return False
        return user.has_perm("auth.change_user")

    def get_success_url(self):
        return reverse_lazy(
            "authentication:user_permissions",
            kwargs={"username": self.object.username},
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        target_user = self.object
        target_user_urls = _site_urls_for(User, target_user, user=self.request.user)

        context.update(build_user_permission_context(target_user, enabled=True))
        context["target_user"] = target_user
        context["target_user_urls"] = target_user_urls

        # Stub `site` so base_form.html renders toolbar + breadcrumbs without
        # having this view registered in superadmin.
        page_title = f"Permisos de {target_user.get_full_name() or target_user.username}"
        context["page_title"] = page_title
        context["site"] = {
            "title": page_title,
            "model_name": "Permisos",
            "urls": {
                "list": target_user_urls.get("detail") or target_user_urls.get("list") or "/",
            },
        }
        return context

    def form_valid(self, form):
        if not self.test_func():
            raise PermissionDenied
        self.object = form.save()  # persists groups via the form
        self.object.user_permissions.set(resolve_posted_permissions(self.request.POST))
        messages.success(self.request, "Permisos actualizados correctamente.")
        return redirect(self.get_success_url())
