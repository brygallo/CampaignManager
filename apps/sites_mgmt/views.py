"""Vista para cambiar de Site activo en sesión."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_http_methods

from core.tenancy import set_active_site

from .models import Site


@login_required
@require_http_methods(["POST"])
def switch_site(request, site_id: int):
    """Cambia el Site activo en sesión, validando membresía."""
    site = get_object_or_404(Site, pk=site_id)
    if not request.user.memberships.filter(site=site).exists() and not request.user.is_superuser:
        return HttpResponseForbidden("No eres miembro de este sitio.")
    set_active_site(request, site.pk)
    messages.success(request, f"Cambiaste al sitio: {site.name}")
    return redirect(request.META.get("HTTP_REFERER") or "/")
