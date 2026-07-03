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
    seed_votes
"""
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand

from tracing.middleware import TracingMiddleware


SEEDS = [
    ("seed_audit_rules",             True),   # acepta --reset
    ("seed_ecuador",                 False),  # provincias / cantones / parroquias
    ("seed_campaigns",               True),   # acepta --reset
    ("seed_field_survey_results",    False),
    ("seed_territorial_ads_catalog", False),
    ("seed_sectors",                 True),
    ("seed_field_surveys",           True),
    ("seed_political_agenda",        True),
    ("seed_territorial_ads",         True),
    ("seed_votes",                   True),
]


class Command(BaseCommand):
    help = "Corre todos los seeds del proyecto en orden."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true",
                            help="Borra y resiembra cada catálogo/dataset.")

    def handle(self, *args, **opts):
        reset = opts.get("reset", False)

        # tracing.signals demands a user on every audited save; outside an HTTP
        # request, the thread-local is empty. Stamp it with the first
        # superuser so seed runs after audit rules are active don't choke.
        user_model = get_user_model()
        seed_user = user_model.objects.filter(is_superuser=True).order_by("id").first()
        if seed_user is not None:
            TracingMiddleware.thread_local.user = seed_user

        try:
            for cmd, supports_reset in SEEDS:
                self.stdout.write(self.style.MIGRATE_HEADING(f"\n→ {cmd}"))
                kwargs = {}
                if reset and supports_reset:
                    kwargs["reset"] = True
                call_command(cmd, **kwargs)
        finally:
            if hasattr(TracingMiddleware.thread_local, "user"):
                del TracingMiddleware.thread_local.user

        self.stdout.write(self.style.SUCCESS("\n✔ Todos los seeds aplicados."))
