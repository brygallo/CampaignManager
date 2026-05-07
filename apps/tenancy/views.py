"""Tenant-facing settings views."""
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.views.generic import UpdateView
from django_tenants.utils import get_public_schema_name, schema_context

from .forms import TenantMapSettingsForm
from .models import TenantSettings


class TenantAdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Restrict tenant-config views to staff/superusers."""

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (user.is_superuser or user.is_staff)


class TenantMapSettingsView(TenantAdminRequiredMixin, UpdateView):
    """Edit the tenant's default map center / zoom.

    ``TenantSettings`` lives in the public schema, so we resolve and persist
    the row inside a ``schema_context(public)`` block while still rendering
    the page in the current tenant context.
    """

    template_name = "tenancy/tenant_map_settings.html"
    form_class = TenantMapSettingsForm
    success_url = reverse_lazy("tenancy:map_settings")

    def get_object(self, queryset=None):
        tenant = self.request.tenant
        with schema_context(get_public_schema_name()):
            obj, _ = TenantSettings.objects.get_or_create(tenant=tenant)
        return obj

    def form_valid(self, form):
        with schema_context(get_public_schema_name()):
            self.object = form.save()
        messages.success(self.request, "Configuración del mapa actualizada.")
        return super().form_valid(form)
