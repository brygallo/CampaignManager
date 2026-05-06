"""Activa las reglas de `tracing.Rule` para los modelos del proyecto.

Sin reglas activas, el middleware/signals de `tracing` no registra ningún
`Trace` — la página `/sistema/auditoria/` queda vacía aunque haya cambios y
transiciones FSM en el sistema.

Este comando descubre todos los modelos relevantes (User custom + cualquier
modelo de las apps del proyecto que herede de `tracing.BaseModel`) y crea o
actualiza una `Rule` por cada uno con `check_create / check_edit /
check_delete = True` e `is_active = True`.

Uso:
    python manage.py tenant_command seed_audit_rules --schema=<tenant>
    python manage.py tenant_command seed_audit_rules --schema=<tenant> --reset
"""
from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction

from tracing.models import BaseModel as TracingBaseModel
from tracing.models import Rule


PROJECT_APP_PREFIX = "apps."


def discover_audited_models():
    """Modelos que valen la pena auditar.

    - Cualquier modelo concreto de `apps.*` que herede de `tracing.BaseModel`.
    - El custom User (no hereda de BaseModel pero sí queremos rastrear
      creaciones/edits/borrados de cuentas).
    """
    models_to_audit = []
    seen = set()

    for model in apps.get_models():
        app_label = model._meta.app_config.name
        if not app_label.startswith(PROJECT_APP_PREFIX):
            continue
        if not issubclass(model, TracingBaseModel):
            continue
        if model is TracingBaseModel:
            continue
        models_to_audit.append(model)
        seen.add(model)

    user_model = get_user_model()
    if user_model not in seen:
        models_to_audit.append(user_model)

    return models_to_audit


class Command(BaseCommand):
    help = "Crea o actualiza las reglas de auditoría (`tracing.Rule`) del tenant."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Borra TODAS las reglas existentes antes de sembrar.",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts.get("reset"):
            deleted, _ = Rule.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Eliminadas {deleted} reglas existentes."))

        created = updated = 0
        for model in discover_audited_models():
            ct = ContentType.objects.get_for_model(model)
            _, was_created = Rule.objects.update_or_create(
                content_type=ct,
                defaults={
                    "check_create": True,
                    "check_edit": True,
                    "check_delete": True,
                    "is_active": True,
                },
            )
            if was_created:
                created += 1
            else:
                updated += 1
            self.stdout.write(f"  · {ct.app_label}.{ct.model}")

        self.stdout.write(self.style.SUCCESS(
            f"\n✔ Reglas de auditoría aplicadas: {created} creadas, {updated} actualizadas."
        ))
