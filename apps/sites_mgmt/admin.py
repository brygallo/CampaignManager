from django.contrib import admin

from .models import Domain, Site, SiteMembership


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "currency", "timezone", "is_active")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ("site", "host", "is_primary")
    search_fields = ("host",)
    list_filter = ("is_primary",)


@admin.register(SiteMembership)
class SiteMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "site", "role")
    search_fields = ("user__username", "user__email", "site__name")
    list_filter = ("role",)
