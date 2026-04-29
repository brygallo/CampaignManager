"""Vistas: login, logout, perfil del usuario actual."""
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User as DjangoUserAlias  # noqa: F401  (avoid name conflict)
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from .forms import EmailOrUsernameAuthenticationForm


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
