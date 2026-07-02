from __future__ import annotations

from django.db import transaction
from django.db.models import Count
from django.utils.text import slugify

from .models import Survey, SurveyAnswer, SurveyOption, SurveyQuestion, SurveySection


SURVEY_TEMPLATE_LIBRARY = [
    {
        "key": "diagnostico-territorial",
        "title": "Diagnóstico territorial",
        "description": "Levantamiento rápido de necesidades y prioridades ciudadanas por territorio.",
        "sections": [
            {
                "title": "Datos de contacto",
                "questions": [
                    {"text": "Nombre completo", "question_type": SurveyQuestion.QuestionType.SHORT_TEXT, "is_required": True},
                    {"text": "Teléfono", "question_type": SurveyQuestion.QuestionType.PHONE, "is_required": False},
                    {"text": "Barrio o sector", "question_type": SurveyQuestion.QuestionType.SHORT_TEXT, "is_required": True},
                ],
            },
            {
                "title": "Prioridades",
                "questions": [
                    {
                        "text": "Principal necesidad del sector",
                        "question_type": SurveyQuestion.QuestionType.SINGLE_CHOICE,
                        "is_required": True,
                        "options": ["Agua potable", "Vialidad", "Seguridad", "Salud", "Educación", "Empleo"],
                    },
                    {"text": "Nivel de urgencia", "question_type": SurveyQuestion.QuestionType.SCALE_5, "is_required": True},
                    {"text": "Comentario adicional", "question_type": SurveyQuestion.QuestionType.LONG_TEXT},
                    {"text": "Ubicación referencial", "question_type": SurveyQuestion.QuestionType.LOCATION},
                ],
            },
        ],
    },
    {
        "key": "satisfaccion-servicios",
        "title": "Satisfacción de servicios",
        "description": "Medición de experiencia ciudadana después de recibir atención o usar un servicio.",
        "sections": [
            {
                "title": "Experiencia",
                "questions": [
                    {"text": "Servicio evaluado", "question_type": SurveyQuestion.QuestionType.SHORT_TEXT, "is_required": True},
                    {"text": "Fecha de atención", "question_type": SurveyQuestion.QuestionType.DATE},
                    {"text": "Calificación general", "question_type": SurveyQuestion.QuestionType.SCALE_10, "is_required": True},
                    {
                        "text": "¿Recomendaría este servicio?",
                        "question_type": SurveyQuestion.QuestionType.YES_NO,
                        "is_required": True,
                    },
                    {"text": "¿Qué deberíamos mejorar?", "question_type": SurveyQuestion.QuestionType.LONG_TEXT},
                ],
            },
        ],
    },
    {
        "key": "intencion-voto",
        "title": "Intención de voto",
        "description": "Formulario base para medir preferencia, indecisión y motivadores electorales.",
        "sections": [
            {
                "title": "Preferencia",
                "questions": [
                    {
                        "text": "Si las elecciones fueran hoy, ¿por quién votaría?",
                        "question_type": SurveyQuestion.QuestionType.SINGLE_CHOICE,
                        "is_required": True,
                        "options": ["Nuestro candidato", "Otro candidato", "Indeciso", "Prefiere no responder"],
                    },
                    {
                        "text": "Temas que más influyen en su voto",
                        "question_type": SurveyQuestion.QuestionType.MULTIPLE_CHOICE,
                        "options": ["Seguridad", "Empleo", "Obras", "Salud", "Educación", "Transparencia"],
                    },
                    {"text": "Probabilidad de votar", "question_type": SurveyQuestion.QuestionType.SCALE_5, "is_required": True},
                    {"text": "Observación del encuestador", "question_type": SurveyQuestion.QuestionType.LONG_TEXT},
                ],
            },
        ],
    },
]


def get_template(key):
    return next((template for template in SURVEY_TEMPLATE_LIBRARY if template["key"] == key), None)


def unique_survey_slug(title):
    base = slugify(title) or "encuesta"
    slug = base
    counter = 2
    while Survey.objects.filter(slug=slug).exists():
        slug = f"{base}-{counter}"
        counter += 1
    return slug


@transaction.atomic
def create_survey_from_template(template_key, *, user=None):
    template = get_template(template_key)
    if template is None:
        raise ValueError("Plantilla no encontrada.")
    survey = Survey.objects.create(
        title=template["title"],
        slug=unique_survey_slug(template["title"]),
        description=template.get("description", ""),
        status=Survey.Status.DRAFT,
        created_by=user if user and user.is_authenticated else None,
    )
    for section_index, section_spec in enumerate(template["sections"], start=1):
        section = SurveySection.objects.create(
            survey=survey,
            title=section_spec["title"],
            description=section_spec.get("description", ""),
            order=section_index,
        )
        for question_index, question_spec in enumerate(section_spec["questions"], start=1):
            options = question_spec.get("options", [])
            question = SurveyQuestion.objects.create(
                survey=survey,
                section=section,
                text=question_spec["text"],
                help_text=question_spec.get("help_text", ""),
                question_type=question_spec.get(
                    "question_type", SurveyQuestion.QuestionType.SHORT_TEXT
                ),
                is_required=question_spec.get("is_required", False),
                order=question_index,
            )
            for option_index, label in enumerate(options, start=1):
                SurveyOption.objects.create(
                    question=question,
                    label=label,
                    value=label,
                    order=option_index,
                )
    return survey


def get_survey_publication_issues(survey):
    issues = []
    questions = list(
        survey.questions.filter(is_active=True)
        .select_related("section", "visibility_question", "visibility_option")
        .prefetch_related("options")
        .order_by("section__order", "order", "id")
    )
    if not questions:
        issues.append("Agrega al menos una pregunta activa.")
    if survey.starts_at and survey.ends_at and survey.starts_at >= survey.ends_at:
        issues.append("La fecha de inicio debe ser anterior a la fecha de cierre.")
    active_question_ids = {question.pk for question in questions}
    for question in questions:
        label = f'"{question.text}"'
        if question.uses_options and question.options.filter(is_active=True).count() < 2:
            issues.append(f"La pregunta {label} necesita al menos 2 opciones activas.")
        if question.visibility_question_id:
            if question.visibility_question_id not in active_question_ids:
                issues.append(f"La pregunta {label} depende de una pregunta inactiva o inexistente.")
            if (
                question.visibility_option_id
                and not question.visibility_option.is_active
            ):
                issues.append(f"La pregunta {label} usa una opción condicional inactiva.")
            if (
                question.visibility_option_id
                and question.visibility_option.question_id != question.visibility_question_id
            ):
                issues.append(f"La pregunta {label} usa una opción de otra pregunta.")
            if (
                not question.visibility_option_id
                and not question.visibility_value
                and question.visibility_operator != SurveyQuestion.VisibilityOperator.ALWAYS
            ):
                issues.append(f"La pregunta {label} necesita valor esperado para su condición.")
    return issues


@transaction.atomic
def update_survey_question_positions(survey, placements):
    question_ids = [str(placement["question_id"]) for placement in placements]
    section_ids = {
        str(placement["section_id"])
        for placement in placements
        if placement.get("section_id")
    }
    questions = {
        str(question.pk): question
        for question in survey.questions.filter(pk__in=question_ids)
    }
    sections = {
        str(section.pk): section
        for section in survey.sections.filter(pk__in=section_ids)
    }
    if len(sections) != len(section_ids):
        raise ValueError("Sección destino no válida.")

    updated = 0
    for placement in placements:
        question = questions.get(str(placement["question_id"]))
        if question is None:
            continue
        section_id = str(placement.get("section_id") or "")
        section = sections.get(section_id) if section_id else None
        changed = []
        if question.order != placement["order"]:
            question.order = placement["order"]
            changed.append("order")
        target_section_id = section.pk if section else None
        if question.section_id != target_section_id:
            question.section = section
            changed.append("section")
        if changed:
            question.save(update_fields=changed)
            updated += 1
    return updated


def build_survey_results_payload(survey):
    questions = list(survey.questions.filter(is_active=True).prefetch_related("options"))
    responses = survey.responses.prefetch_related("answers__question", "answers__selected_options")
    choice_summaries = []
    for question in questions:
        if question.question_type not in {
            SurveyQuestion.QuestionType.SINGLE_CHOICE,
            SurveyQuestion.QuestionType.MULTIPLE_CHOICE,
            SurveyQuestion.QuestionType.YES_NO,
            SurveyQuestion.QuestionType.SCALE_5,
            SurveyQuestion.QuestionType.SCALE_10,
        }:
            continue
        if question.uses_options:
            rows = list(
                question.options.filter(is_active=True)
                .annotate(count=Count("answers"))
                .values("label", "count")
                .order_by("order", "label")
            )
        else:
            rows = list(
                SurveyAnswer.objects.filter(question=question)
                .values("value_text")
                .annotate(count=Count("id"))
                .order_by("value_text")
            )
            rows = [
                {"label": row["value_text"] or "Sin respuesta", "count": row["count"]}
                for row in rows
            ]
        choice_summaries.append(
            {
                "question_id": question.pk,
                "question": question.text,
                "rows": rows,
            }
        )
    latest = []
    for survey_response in responses[:10]:
        latest.append(
            {
                "id": survey_response.pk,
                "submitted_at": survey_response.submitted_at.strftime("%d/%m/%Y %H:%M"),
                "respondent": "Anónima"
                if survey.is_anonymous
                else str(survey_response.respondent or "Pública"),
                "answers": [
                    {"question": answer.question.text, "value": answer.display_value}
                    for answer in survey_response.answers.all()
                ],
            }
        )
    return {
        "survey_id": survey.pk,
        "total_responses": responses.count(),
        "question_count": len(questions),
        "choice_summaries": choice_summaries,
        "latest": latest,
    }


def broadcast_survey_results_update(survey):
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
    except ImportError:
        return

    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        f"survey_results_{survey.pk}",
        {
            "type": "survey_results_updated",
            "payload": build_survey_results_payload(survey),
        },
    )
