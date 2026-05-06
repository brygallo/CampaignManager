"""Atajo: corre todos los comandos `seed_*` en el orden correcto.

Uso:
    python manage.py tenant_command seed_all --schema=<tenant>
    python manage.py tenant_command seed_all --schema=<tenant> --reset

Equivale a:
    seed_audit_rules
    seed_campaigns
    seed_field_survey_results
    seed_sectors
    seed_field_surveys
    seed_political_agenda
    seed_territorial_ads
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand


SEEDS = [
    ("seed_audit_rules",          True),   # acepta --reset
    ("seed_campaigns",            True),   # acepta --reset
    ("seed_field_survey_results", False),
    ("seed_sectors",              True),
    ("seed_field_surveys",        True),
    ("seed_political_agenda",     True),
    ("seed_territorial_ads",      True),
]


class Command(BaseCommand):
    help = "Corre todos los seeds del proyecto en orden."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true",
                            help="Borra y resiembra cada catálogo/dataset.")

    def handle(self, *args, **opts):
        reset = opts.get("reset", False)
        for cmd, supports_reset in SEEDS:
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n→ {cmd}"))
            kwargs = {}
            if reset and supports_reset:
                kwargs["reset"] = True
            call_command(cmd, **kwargs)
        self.stdout.write(self.style.SUCCESS("\n✔ Todos los seeds aplicados."))
