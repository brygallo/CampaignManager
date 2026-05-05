from django.contrib import admin

from .models import PoliticalAgendaEvent, PoliticalAgendaRequest


@admin.register(PoliticalAgendaRequest)
class PoliticalAgendaRequestAdmin(admin.ModelAdmin):
    list_display = ("title", "campaign", "requester_name", "event_type", "state", "priority", "proposed_start_at")
    list_filter = ("campaign", "event_type", "state", "priority")
    search_fields = ("title", "requester_name", "organization", "address")


@admin.register(PoliticalAgendaEvent)
class PoliticalAgendaEventAdmin(admin.ModelAdmin):
    list_display = ("title", "campaign", "event_type", "state", "start_at", "end_at", "responsible")
    list_filter = ("campaign", "event_type", "state", "start_at")
    search_fields = ("title", "organizer_name", "address", "objective")
