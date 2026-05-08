"""Catálogos base para agenda política.

Pre-carga los tipos de evento (reunión, visita, recorrido, mitin, ...).

Uso:
    python manage.py tenant_command seed_political_agenda_catalog --schema=<tenant>
"""
from django.core.management.base import BaseCommand

from apps.political_agenda.models import AgendaEventType


EVENT_TYPES = [
    # (code, name, order, color, icon)
    ("REUNION", "Reunión", 10, "#3e97ff", "people"),
    ("VISITA", "Visita", 20, "#50cd89", "geolocation"),
    ("RECORRIDO", "Recorrido", 30, "#7239ea", "route"),
    ("MITIN", "Mitin", 40, "#f1416c", "flag"),
    ("ENTREVISTA", "Entrevista", 50, "#ffc700", "microphone-2"),
    ("RUEDA_PRENSA", "Rueda de prensa", 60, "#fd7e14", "picture"),
    ("OTRO", "Otro", 99, "#7e8299", "dots-circle"),
]


class Command(BaseCommand):
    help = "Crea los catálogos base de agenda política."

    def handle(self, *args, **options):
        for code, name, order, color, icon in EVENT_TYPES:
            obj, created = AgendaEventType.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "order": order,
                    "color": color,
                    "icon": icon,
                    "is_active": True,
                },
            )
            self.stdout.write(
                f"AgendaEventType: {'Creado' if created else 'Actualizado'} {obj.code}"
            )
