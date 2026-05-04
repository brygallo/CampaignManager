from django.contrib import admin

from .models import PhysicalAdvertisement


@admin.register(PhysicalAdvertisement)
class PhysicalAdvertisementAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "title",
        "campaign",
        "owner_name",
        "canton",
        "sector",
        "state",
    )
    list_filter = ("state", "advertisement_type", "province", "canton")
    search_fields = ("code", "title", "owner_name", "owner_phone", "address")
