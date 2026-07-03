from django.core.management.base import BaseCommand
from django.utils import timezone
from django_tenants.utils import schema_context

from apps.tenancy.models import Tenant


class Command(BaseCommand):
    help = "Carga encuestas genéricas de ejemplo en los tenants."

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema",
            action="append",
            dest="schemas",
            help="Schema tenant a cargar. Se puede repetir. Por defecto carga todos los tenants activos.",
        )

    def handle(self, *args, **options):
        schemas = options["schemas"] or list(
            Tenant.objects.filter(is_active=True)
            .order_by("schema_name")
            .values_list("schema_name", flat=True)
        )
        for schema_name in schemas:
            with schema_context(schema_name):
                payload = self._seed_schema()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"{schema_name}: encuesta '{payload['survey']}' lista "
                        f"({payload['questions']} preguntas, {payload['responses']} respuestas)"
                    )
                )

    def _seed_schema(self):
        from apps.authentication.models import User
        from apps.surveys.models import (
            Survey,
            SurveyAnswer,
            SurveyOption,
            SurveyQuestion,
            SurveyResponse,
            SurveySection,
        )

        creator = User.objects.filter(is_superuser=True).first() or User.objects.first()
        survey, _ = Survey.objects.update_or_create(
            slug="diagnostico-general",
            defaults={
                "title": "Diagnóstico general institucional",
                "description": (
                    "Encuesta de ejemplo para levantar necesidades, nivel de satisfacción "
                    "y prioridades de atención. Puede usarse como base para cualquier área."
                ),
                "starts_at": timezone.now(),
                "ends_at": None,
                "requires_login": False,
                "allow_multiple_responses": True,
                "is_anonymous": False,
                "thank_you_message": "Gracias por completar el diagnóstico.",
                "created_by": creator,
                "is_active": True,
            },
        )
        # ``state`` is a protected FSM field: assigning it via ``defaults`` above
        # would raise, so publish the seeded survey with a direct queryset update.
        Survey.objects.filter(pk=survey.pk).update(state=Survey.workflow.PUBLISHED)

        general, _ = SurveySection.objects.update_or_create(
            survey=survey,
            title="Datos generales",
            defaults={"description": "Información básica de la persona encuestada.", "order": 1},
        )
        perception, _ = SurveySection.objects.update_or_create(
            survey=survey,
            title="Percepción y prioridades",
            defaults={"description": "Opinión sobre servicios y necesidades.", "order": 2},
        )

        question_specs = [
            {
                "text": "Nombre completo",
                "section": general,
                "question_type": SurveyQuestion.QuestionType.SHORT_TEXT,
                "is_required": True,
                "order": 1,
            },
            {
                "text": "Correo electrónico",
                "section": general,
                "question_type": SurveyQuestion.QuestionType.EMAIL,
                "is_required": False,
                "order": 2,
            },
            {
                "text": "Edad",
                "section": general,
                "question_type": SurveyQuestion.QuestionType.NUMBER,
                "is_required": False,
                "order": 3,
            },
            {
                "text": "¿Ha usado nuestros servicios en los últimos 3 meses?",
                "section": perception,
                "question_type": SurveyQuestion.QuestionType.YES_NO,
                "is_required": True,
                "order": 4,
            },
            {
                "text": "Servicio que más necesita",
                "section": perception,
                "question_type": SurveyQuestion.QuestionType.SINGLE_CHOICE,
                "is_required": True,
                "order": 5,
                "options": ["Atención ciudadana", "Obras públicas", "Salud", "Seguridad", "Educación"],
            },
            {
                "text": "Canales por los que desea recibir información",
                "section": perception,
                "question_type": SurveyQuestion.QuestionType.MULTIPLE_CHOICE,
                "is_required": False,
                "order": 6,
                "options": ["WhatsApp", "Correo", "Llamada", "Redes sociales", "Presencial"],
            },
            {
                "text": "Nivel de satisfacción general",
                "section": perception,
                "question_type": SurveyQuestion.QuestionType.SCALE_5,
                "is_required": True,
                "order": 7,
            },
            {
                "text": "Comentario o sugerencia",
                "section": perception,
                "question_type": SurveyQuestion.QuestionType.LONG_TEXT,
                "is_required": False,
                "order": 8,
            },
            {
                "text": "Ubicación referencial",
                "section": perception,
                "question_type": SurveyQuestion.QuestionType.LOCATION,
                "is_required": False,
                "order": 9,
                "help_text": "Formato: latitud, longitud. Ejemplo: -2.304600, -78.117500",
            },
        ]

        questions = {}
        for spec in question_specs:
            options = spec.pop("options", [])
            question, _ = SurveyQuestion.objects.update_or_create(
                survey=survey,
                text=spec["text"],
                defaults={**spec, "is_active": True},
            )
            questions[spec["text"]] = question
            for index, label in enumerate(options, start=1):
                SurveyOption.objects.update_or_create(
                    question=question,
                    label=label,
                    defaults={"value": label, "order": index, "is_active": True},
                )

        # Keep this command idempotent: refresh example responses.
        survey.responses.filter(respondent_name__startswith="Demo ").delete()
        demo_rows = [
            {
                "name": "Demo Ana",
                "email": "ana.demo@example.com",
                "age": "32",
                "used": "Sí",
                "service": "Atención ciudadana",
                "channels": ["WhatsApp", "Correo"],
                "satisfaction": "4",
                "comment": "La atención fue buena, pero el seguimiento puede mejorar.",
                "location": "-2.304600, -78.117500",
            },
            {
                "name": "Demo Luis",
                "email": "luis.demo@example.com",
                "age": "45",
                "used": "No",
                "service": "Obras públicas",
                "channels": ["WhatsApp", "Redes sociales"],
                "satisfaction": "3",
                "comment": "La prioridad debería ser el mantenimiento vial.",
                "location": "-2.298100, -78.120900",
            },
            {
                "name": "Demo Carla",
                "email": "carla.demo@example.com",
                "age": "28",
                "used": "Sí",
                "service": "Salud",
                "channels": ["Correo", "Presencial"],
                "satisfaction": "5",
                "comment": "Me gustaría recibir más información preventiva.",
                "location": "-2.310200, -78.109800",
            },
        ]
        for row in demo_rows:
            response = SurveyResponse.objects.create(
                survey=survey,
                respondent_name=row["name"],
                respondent_email=row["email"],
                user_agent="seed_surveys",
            )
            self._answer_text(SurveyAnswer, response, questions["Nombre completo"], row["name"])
            self._answer_text(SurveyAnswer, response, questions["Correo electrónico"], row["email"])
            self._answer_number(SurveyAnswer, response, questions["Edad"], row["age"])
            self._answer_text(
                SurveyAnswer,
                response,
                questions["¿Ha usado nuestros servicios en los últimos 3 meses?"],
                row["used"],
            )
            self._answer_options(
                SurveyAnswer,
                response,
                questions["Servicio que más necesita"],
                [row["service"]],
            )
            self._answer_options(
                SurveyAnswer,
                response,
                questions["Canales por los que desea recibir información"],
                row["channels"],
            )
            self._answer_text(
                SurveyAnswer, response, questions["Nivel de satisfacción general"], row["satisfaction"]
            )
            self._answer_text(SurveyAnswer, response, questions["Comentario o sugerencia"], row["comment"])
            self._answer_location(
                SurveyAnswer, response, questions["Ubicación referencial"], row["location"]
            )

        return {
            "survey": survey.title,
            "questions": survey.questions.count(),
            "responses": survey.responses.count(),
        }

    def _answer_text(self, SurveyAnswer, response, question, value):
        SurveyAnswer.objects.create(response=response, question=question, value_text=value)

    def _answer_number(self, SurveyAnswer, response, question, value):
        SurveyAnswer.objects.create(response=response, question=question, value_number=value)

    def _answer_options(self, SurveyAnswer, response, question, labels):
        answer = SurveyAnswer.objects.create(response=response, question=question)
        answer.selected_options.set(question.options.filter(label__in=labels))

    def _answer_location(self, SurveyAnswer, response, question, value):
        lat, lng = [part.strip() for part in value.split(",", 1)]
        SurveyAnswer.objects.create(
            response=response,
            question=question,
            value_text=value,
            latitude=lat,
            longitude=lng,
        )
