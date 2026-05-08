"""Borra y vuelve a sembrar agenda política en todos los tenants.

Itera los tenants no-public y, para cada uno, ejecuta dentro de su schema:
    seed_political_agenda_catalog    (tipos de evento)
    seed_political_agenda --reset    (solicitudes y eventos)

Uso:
    python manage.py reseed_political_agenda_all
"""
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django_tenants.utils import get_tenant_model, schema_context

from tracing.middleware import TracingMiddleware


class Command(BaseCommand):
    help = "Borra y resiembra catálogos y agenda política en todos los tenants."

    def handle(self, *args, **opts):
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
                seed_user = (
                    user_model.objects.filter(is_superuser=True)
                    .order_by("id")
                    .first()
                )
                if seed_user is not None:
                    TracingMiddleware.thread_local.user = seed_user
                try:
                    call_command("seed_political_agenda_catalog")
                    call_command("seed_political_agenda", reset=True)
                finally:
                    if hasattr(TracingMiddleware.thread_local, "user"):
                        del TracingMiddleware.thread_local.user

        self.stdout.write(self.style.SUCCESS(
            f"\n✔ Reseed completado en {tenants.count()} tenant(s)."
        ))
