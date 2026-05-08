"""Backfill ``event_type_fk`` on Request and Event from the legacy CharField.

Creates the canonical ``AgendaEventType`` rows (idempotent) and assigns each
existing record's FK based on its old ``event_type`` code value.
"""
from django.db import migrations


CATALOG = [
    # (code, name, order, color, icon)
    ("REUNION", "Reunión", 10, "#3e97ff", "people"),
    ("VISITA", "Visita", 20, "#50cd89", "geolocation"),
    ("RECORRIDO", "Recorrido", 30, "#7239ea", "route"),
    ("MITIN", "Mitin", 40, "#f1416c", "flag"),
    ("ENTREVISTA", "Entrevista", 50, "#ffc700", "microphone-2"),
    ("RUEDA_PRENSA", "Rueda de prensa", 60, "#fd7e14", "picture"),
    ("OTRO", "Otro", 99, "#7e8299", "dots-circle"),
]


def forwards(apps, schema_editor):
    AgendaEventType = apps.get_model("political_agenda", "AgendaEventType")
    PoliticalAgendaRequest = apps.get_model("political_agenda", "PoliticalAgendaRequest")
    PoliticalAgendaEvent = apps.get_model("political_agenda", "PoliticalAgendaEvent")

    by_code = {}
    for code, name, order, color, icon in CATALOG:
        obj, _ = AgendaEventType.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "order": order,
                "color": color,
                "icon": icon,
                "is_active": True,
            },
        )
        by_code[code] = obj

    fallback = by_code["OTRO"]

    for model in (PoliticalAgendaRequest, PoliticalAgendaEvent):
        for row in model.objects.all():
            legacy = (row.event_type or "").strip()
            row.event_type_fk = by_code.get(legacy, fallback)
            row.save(update_fields=["event_type_fk"])


def backwards(apps, schema_editor):
    PoliticalAgendaRequest = apps.get_model("political_agenda", "PoliticalAgendaRequest")
    PoliticalAgendaEvent = apps.get_model("political_agenda", "PoliticalAgendaEvent")
    for model in (PoliticalAgendaRequest, PoliticalAgendaEvent):
        for row in model.objects.all():
            if row.event_type_fk_id:
                row.event_type = row.event_type_fk.code
                row.save(update_fields=["event_type"])


class Migration(migrations.Migration):

    dependencies = [
        ("political_agenda", "0002_agendaeventtype_gps"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
