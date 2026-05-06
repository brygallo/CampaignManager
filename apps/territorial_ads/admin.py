from django.contrib import admin

from .models import PhysicalAdvertisement


@admin.register(PhysicalAdvertisement)
class PhysicalAdvertisementAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "campaign",
        "owner_name",
        "state",
    )
    list_filter = ("state", "advertisement_type")
    search_fields = ("code", "owner_name", "owner_phone", "address")
