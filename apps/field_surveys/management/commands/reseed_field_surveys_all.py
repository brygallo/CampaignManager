"""Borra y vuelve a sembrar levantamientos en todos los tenants.

Itera los tenants no-public y, para cada uno, ejecuta dentro de su schema:
    seed_field_survey_results        (catálogos: apoyo, publicidad, ad types)
    seed_field_surveys --reset       (competidores, visitas, detecciones)

Uso:
    python manage.py reseed_field_surveys_all
    python manage.py reseed_field_surveys_all --surveys 50
"""
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django_tenants.utils import get_tenant_model, schema_context

from tracing.middleware import TracingMiddleware


class Command(BaseCommand):
    help = "Borra y resiembra catálogos y levantamientos en todos los tenants."

    def add_arguments(self, parser):
        parser.add_argument(
            "--surveys",
            type=int,
            default=30,
            help="Cantidad de levantamientos a generar por tenant (default: 30).",
        )

    def handle(self, *args, **opts):
        surveys_count = opts["surveys"]
        tenant_model = get_tenant_model()
        tenants = tenant_model.objects.exclude(schema_name="public")

        if not tenants.exists():
            self.stdout.write(self.style.WARNING("No hay tenants registrados."))
            return

        user_model = get_user_model()

        for tenant in tenants:
            self.stdout.write(self.style.MIGRATE_HEADING(
                f"\n=== Tenant: {tenant.schema_name} ==="
            ))
            with schema_context(tenant.schema_name):
                # tracing.signals exige un usuario en cada save auditado; fuera de
                # un request HTTP, el thread-local está vacío.
                seed_user = (
                    user_model.objects.filter(is_superuser=True)
                    .order_by("id")
                    .first()
                )
                if seed_user is not None:
                    TracingMiddleware.thread_local.user = seed_user
                try:
                    call_command("seed_field_survey_results")
                    call_command("seed_field_surveys", reset=True, surveys=surveys_count)
                finally:
                    if hasattr(TracingMiddleware.thread_local, "user"):
                        del TracingMiddleware.thread_local.user

        self.stdout.write(self.style.SUCCESS(
            f"\n✔ Reseed completado en {tenants.count()} tenant(s)."
        ))
