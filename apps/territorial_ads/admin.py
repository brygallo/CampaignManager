from django.contrib import admin

from .models import (
    AdvertisingCostType,
    AdvertisingRefusal,
    InstallationPhoto,
    PhysicalAdvertisement,
    PhysicalAdvertisementItem,
)


class PhysicalAdvertisementItemInline(admin.TabularInline):
    model = PhysicalAdvertisementItem
    extra = 0


class InstallationPhotoInline(admin.TabularInline):
    model = InstallationPhoto
    extra = 0


@admin.register(PhysicalAdvertisement)
class PhysicalAdvertisementAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "campaign",
        "owner_name",
        "cost_type",
        "state",
    )
    list_filter = ("state", "items__advertisement_type", "cost_type")
    search_fields = ("code", "owner_name", "owner_phone", "address")
    inlines = (PhysicalAdvertisementItemInline, InstallationPhotoInline)


@admin.register(AdvertisingCostType)
class AdvertisingCostTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "order", "requires_amount", "is_active")
    list_filter = ("requires_amount", "is_active")
    search_fields = ("code", "name")


@admin.register(AdvertisingRefusal)
class AdvertisingRefusalAdmin(admin.ModelAdmin):
    list_display = ("id", "campaign", "owner_reference", "reported_by", "created_date")
    list_filter = ("campaign", "is_active")
    search_fields = ("owner_reference", "reason")
