from django.contrib import admin

from .models import (
    AdvertisingType,
    Competitor,
    CompetitorAdvertisingDetection,
    FieldSurvey,
    SurveyAdvertisingResponse,
    SurveySupportLevel,
)


@admin.register(SurveySupportLevel)
class SurveySupportLevelAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "color", "order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(SurveyAdvertisingResponse)
class SurveyAdvertisingResponseAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "color", "order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(AdvertisingType)
class AdvertisingTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "icon", "order", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


class CompetitorAdvertisingDetectionInline(admin.TabularInline):
    model = CompetitorAdvertisingDetection
    extra = 0
    fields = ("competitor", "advertising_type", "latitude", "longitude", "photo")


@admin.register(FieldSurvey)
class FieldSurveyAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "campaign",
        "brigadier",
        "support_level",
        "advertising_response",
        "voters_count",
        "created_date",
    )
    list_filter = ("campaign", "brigadier", "support_level", "advertising_response", "created_date")
    search_fields = ("code", "person_name", "person_phone")
    inlines = (CompetitorAdvertisingDetectionInline,)


@admin.register(Competitor)
class CompetitorAdmin(admin.ModelAdmin):
    list_display = ("campaign", "list_number", "political_organization", "candidate_name", "is_active")
    list_filter = ("campaign", "is_active")
    search_fields = ("list_number", "political_organization", "candidate_name")


@admin.register(CompetitorAdvertisingDetection)
class CompetitorAdvertisingDetectionAdmin(admin.ModelAdmin):
    list_display = ("campaign", "competitor", "brigadier", "advertising_type", "created_date")
    list_filter = ("campaign", "competitor", "advertising_type", "created_date")
    search_fields = ("competitor__political_organization", "competitor__candidate_name", "observation")
