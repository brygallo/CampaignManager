"""Siembra sectores/barrios para parroquias del cantón Morona (Macas).

Las provincias, cantones y parroquias se crean vía la migración
`0002_seed_ecuador.py`. Este comando complementa con los sectores/barrios
que el GAD Morona usa operativamente.

Uso:
    python manage.py tenant_command seed_sectors --schema=<tenant>
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.locations.models import Parish, Sector


# (parish_code, [sector_name, ...])
SECTORS = [
    # Macas (cabecera urbana)
    ("140150", [
        "Centro / La Catedral",
        "La Loma",
        "Yantzaza",
        "La Florida",
        "El Tesoro",
        "La Unión",
        "Amazonas",
        "Eloy Alfaro",
        "27 de Febrero",
        "Sangay",
        "Buenos Aires",
        "Las Orquídeas",
        "La Barranca",
        "Río Upano",
    ]),
    # General Proaño
    ("140151", [
        "Centro Parroquial",
        "San Luis",
        "Don Bosco",
        "El Edén",
    ]),
    # San Isidro
    ("140152", [
        "Centro San Isidro",
        "La Florida",
        "Santa Rosa",
    ]),
    # Sevilla Don Bosco
    ("140153", [
        "Sevilla Centro",
        "Yukutais",
        "Kuamar",
        "Tunants",
        "Yawi",
    ]),
    # Sinaí
    ("140154", [
        "Sinaí Centro",
        "Buena Esperanza",
    ]),
    # Cuchaentza
    ("140155", [
        "Cuchaentza Centro",
        "Tsuntsuim",
    ]),
    # Río Blanco
    ("140156", [
        "Río Blanco Centro",
        "San Pedro",
    ]),
    # 9 de Octubre
    ("140159", [
        "9 de Octubre Centro",
        "La Dolorosa",
    ]),
    # Sucúa (cabecera del cantón Sucúa)
    ("140650", [
        "Centro Sucúa",
        "Asunción",
        "Huambinimi",
    ]),
    # Gualaquiza
    ("140250", [
        "Centro Gualaquiza",
        "El Ideal",
    ]),
]


class Command(BaseCommand):
    help = "Siembra sectores/barrios (cantón Morona y aledaños)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Borra todos los sectores antes de sembrar.",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts.get("reset"):
            Sector.objects.all().delete()
            self.stdout.write(self.style.WARNING("Sectores borrados."))

        created = 0
        skipped = 0
        for parish_code, names in SECTORS:
            try:
                parish = Parish.objects.get(code=parish_code)
            except Parish.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f"Parroquia {parish_code} no existe — saltando sus sectores."
                ))
                continue
            for name in names:
                _, was_created = Sector.objects.get_or_create(
                    parish=parish, name=name
                )
                if was_created:
                    created += 1
                else:
                    skipped += 1

        total = Sector.objects.count()
        self.stdout.write(self.style.SUCCESS(
            f"Sectores: {created} nuevos, {skipped} existentes (total {total})."
        ))
