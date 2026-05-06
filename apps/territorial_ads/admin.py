from django.contrib import admin

from .models import AdvertisingCostType, PhysicalAdvertisement


@admin.register(PhysicalAdvertisement)
class PhysicalAdvertisementAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "campaign",
        "owner_name",
        "cost_type",
        "state",
    )
    list_filter = ("state", "advertisement_type", "cost_type")
    search_fields = ("code", "owner_name", "owner_phone", "address")


@admin.register(AdvertisingCostType)
class AdvertisingCostTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "order", "requires_amount", "is_active")
    list_filter = ("requires_amount", "is_active")
    search_fields = ("code", "name")
