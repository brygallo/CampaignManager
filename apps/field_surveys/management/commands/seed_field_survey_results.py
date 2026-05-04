from django.core.management.base import BaseCommand

from apps.field_surveys.models import SurveyResultOption


class Command(BaseCommand):
    help = "Crea las opciones base del checklist de levantamiento de campo."

    def handle(self, *args, **options):
        for order, (code, name) in enumerate(SurveyResultOption.Codes.choices, start=10):
            option, created = SurveyResultOption.objects.update_or_create(
                code=code,
                defaults={"name": name, "order": order, "is_active": True},
            )
            self.stdout.write(f"{'Creado' if created else 'Actualizado'}: {option.code}")
