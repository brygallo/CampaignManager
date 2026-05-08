from django.contrib import admin

from .models import AgendaEventType, PoliticalAgendaEvent, PoliticalAgendaRequest


@admin.register(AgendaEventType)
class AgendaEventTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "order", "color", "icon", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")
    ordering = ("order", "name")


@admin.register(PoliticalAgendaRequest)
class PoliticalAgendaRequestAdmin(admin.ModelAdmin):
    list_display = ("title", "campaign", "requester_name", "event_type", "state", "priority", "proposed_start_at")
    list_filter = ("campaign", "event_type", "state", "priority")
    search_fields = ("title", "requester_name", "organization", "address")
    autocomplete_fields = ("event_type",)


@admin.register(PoliticalAgendaEvent)
class PoliticalAgendaEventAdmin(admin.ModelAdmin):
    list_display = ("title", "campaign", "event_type", "state", "start_at", "end_at", "responsible")
    list_filter = ("campaign", "event_type", "state", "start_at")
    search_fields = ("title", "organizer_name", "address", "objective")
    autocomplete_fields = ("event_type", "source_request")
