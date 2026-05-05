"""Django admin for the tenancy app.

Note: this admin is exposed only on the public schema. The tenant URL conf
should NOT mount /admin/ for the django-tenants Tenant/Domain models, since
those tables don't exist inside tenant schemas.
"""
from django.contrib import admin

from .models import Domain, Tenant, TenantBranding


class DomainInline(admin.TabularInline):
    model = Domain
    extra = 1


class TenantBrandingInline(admin.StackedInline):
    model = TenantBranding
    can_delete = False


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "schema_name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug", "schema_name")
    inlines = [DomainInline, TenantBrandingInline]
    readonly_fields = ("created_at", "updated_at")
