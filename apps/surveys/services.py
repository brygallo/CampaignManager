from __future__ import annotations

import json
from collections import defaultdict

from django.db import transaction
from django.db.models import Avg, Count, Max, Min, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.utils.formats import number_format
from django.utils.functional import cached_property
from django.utils.text import slugify

from .models import (
    Survey,
    SurveyAnswer,
    SurveyOption,
    SurveyQuestion,
    SurveyResponse,
    SurveySection,
)
from .reports import filtered_survey_responses

CHOICE_QUESTION_TYPES = frozenset(
    {
        SurveyQuestion.QuestionType.SINGLE_CHOICE,
        SurveyQuestion.QuestionType.MULTIPLE_CHOICE,
        SurveyQuestion.QuestionType.YES_NO,
        SurveyQuestion.QuestionType.SCALE_5,
        SurveyQuestion.QuestionType.SCALE_10,
    }
)


def format_decimal_stat(value):
    if value is None:
        return None
    return number_format(value, decimal_pos=2)


class SurveyBuilderResponseService:
    """Rules for editing a survey builder after responses have been collected."""

    STRUCTURE_LOCK_MESSAGE = "Vacía las respuestas antes de modificar la estructura."

    def __init__(self, survey):
        self.survey = survey

    @property
    def is_structure_locked(self):
        return self.survey.has_responses

    def assert_structure_can_change(self):
        if self.is_structure_locked:
            raise ValueError(self.STRUCTURE_LOCK_MESSAGE)

    def clear_responses(self, *, confirmed):
        if not confirmed:
            raise ValueError("Confirma el borrado de respuestas para continuar.")
        with transaction.atomic():
            response_count = self.survey.responses.count()
            self.survey.responses.all().delete()
        return response_count


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


@transaction.atomic
def clone_survey(source, *, user=None):
    """Deep-copy a survey into a fresh DRAFT: sections, questions, options and
    visibility rules. Visibility FKs (``visibility_question`` /
    ``visibility_option``) point at other objects within the same survey, so
    they are remapped to the cloned counterparts in a second pass. Responses
    are never copied."""
    clone = Survey.objects.create(
        title=f"Copia de {source.title}",
        slug=unique_survey_slug(f"Copia de {source.title}"),
        description=source.description,
        is_anonymous=source.is_anonymous,
        requires_login=source.requires_login,
        allow_multiple_responses=source.allow_multiple_responses,
        all_users_can_respond=source.all_users_can_respond,
        thank_you_message=source.thank_you_message,
        starts_at=source.starts_at,
        ends_at=source.ends_at,
        created_by=user if user and user.is_authenticated else None,
    )
    clone.assigned_users.set(source.assigned_users.all())

    section_map = {}
    for section in source.sections.filter(is_active=True).order_by("order", "title"):
        section_map[section.pk] = SurveySection.objects.create(
            survey=clone,
            title=section.title,
            description=section.description,
            order=section.order,
        )

    question_map = {}
    option_map = {}
    source_questions = list(
        source.questions.filter(is_active=True).order_by("section__order", "order", "id")
    )
    for question in source_questions:
        new_question = SurveyQuestion.objects.create(
            survey=clone,
            section=section_map.get(question.section_id),
            text=question.text,
            help_text=question.help_text,
            question_type=question.question_type,
            is_required=question.is_required,
            order=question.order,
            visibility_operator=question.visibility_operator,
            visibility_value=question.visibility_value,
            allow_other=question.allow_other,
            min_selections=question.min_selections,
            max_selections=question.max_selections,
            min_value=question.min_value,
            max_value=question.max_value,
        )
        question_map[question.pk] = new_question
        for option in question.options.filter(is_active=True).order_by("order", "label"):
            option_map[option.pk] = SurveyOption.objects.create(
                question=new_question,
                label=option.label,
                value=option.value,
                order=option.order,
            )

    # Second pass: remap visibility references onto the cloned objects. A rule
    # pointing at a question/option that was not cloned (inactive) degrades to
    # no dependency rather than a dangling reference.
    for question in source_questions:
        if not (question.visibility_question_id or question.visibility_option_id):
            continue
        new_question = question_map[question.pk]
        new_question.visibility_question = question_map.get(question.visibility_question_id)
        new_question.visibility_option = option_map.get(question.visibility_option_id)
        new_question.save(update_fields=["visibility_question", "visibility_option"])

    return clone


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


TEXT_QUESTION_TYPES = frozenset(
    {
        SurveyQuestion.QuestionType.SHORT_TEXT,
        SurveyQuestion.QuestionType.LONG_TEXT,
        SurveyQuestion.QuestionType.EMAIL,
        SurveyQuestion.QuestionType.PHONE,
    }
)


class SurveyResultsSummary:
    """Single filter-aware computation of a survey's results.

    Instantiated once per request by the results dashboard view and the
    ``results_data`` / ``results_map_data`` endpoints so the filtered response
    query and every per-question aggregate run once and are reused across the
    stat tiles, charts, completion table, trend and map instead of being
    recomputed per consumer. Every heavy attribute is a ``cached_property`` so
    consumers can read only what they need.
    """

    def __init__(self, survey, params=None):
        self.survey = survey
        self.params = params or {}

    @cached_property
    def questions(self):
        """Active questions ordered as rendered, with section and options loaded."""
        return list(
            self.survey.questions.filter(is_active=True)
            .select_related("section")
            .prefetch_related("options")
            .order_by("section__order", "order", "id")
        )

    @cached_property
    def responses(self):
        """Filtered response queryset (used for pagination and export)."""
        return filtered_survey_responses(self.survey, self.params)

    @cached_property
    def response_ids(self):
        return list(self.responses.values_list("pk", flat=True))

    @cached_property
    def total_responses(self):
        return len(self.response_ids)

    @cached_property
    def _base_responses(self):
        return SurveyResponse.objects.filter(pk__in=self.response_ids)

    @cached_property
    def has_location_questions(self):
        return any(
            question.question_type == SurveyQuestion.QuestionType.LOCATION
            for question in self.questions
        )

    @cached_property
    def stat_tiles(self):
        """Headline counters shown as tiles and refreshed by the live feed."""
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        last_7_days = now - timezone.timedelta(days=7)
        latest = self._base_responses.order_by("-submitted_at").first()
        return {
            "total_responses": self.total_responses,
            "responses_today": self._base_responses.filter(
                submitted_at__gte=today_start
            ).count(),
            "responses_last_7_days": self._base_responses.filter(
                submitted_at__gte=last_7_days
            ).count(),
            "latest_response": latest.submitted_at.strftime("%d/%m/%Y %H:%M")
            if latest
            else "",
        }

    @cached_property
    def choice_summaries(self):
        """Per-question choice aggregates (chart categories/series and rows).

        All option/text aggregates are batched into a constant number of
        queries instead of one query per question.
        """
        # ``uses_options`` also covers RANKING (it needs a real SurveyOption
        # set to sync/order), but ranking isn't part of CHOICE_QUESTION_TYPES
        # and has its own aggregation (see ``ranking_summaries``), so it's
        # deliberately excluded here.
        option_choice_types = {
            SurveyQuestion.QuestionType.SINGLE_CHOICE,
            SurveyQuestion.QuestionType.MULTIPLE_CHOICE,
        }
        option_question_ids = [q.pk for q in self.questions if q.question_type in option_choice_types]
        text_choice_ids = [
            q.pk
            for q in self.questions
            if q.question_type in CHOICE_QUESTION_TYPES and q.question_type not in option_choice_types
        ]
        other_question_ids = [
            q.pk for q in self.questions if q.question_type in option_choice_types and q.allow_other
        ]

        option_rows = defaultdict(list)
        if option_question_ids:
            answer_filter = Q(answers__response_id__in=self.response_ids)
            for row in (
                SurveyOption.objects.filter(
                    question_id__in=option_question_ids, is_active=True
                )
                .annotate(count=Count("answers", filter=answer_filter))
                .values("question_id", "label", "count")
                .order_by("question_id", "order", "label")
            ):
                option_rows[row["question_id"]].append(
                    {"label": row["label"], "count": row["count"]}
                )

        text_rows = defaultdict(list)
        if text_choice_ids:
            for row in (
                SurveyAnswer.objects.filter(
                    question_id__in=text_choice_ids, response_id__in=self.response_ids
                )
                .values("question_id", "value_text")
                .annotate(count=Count("id"))
                .order_by("question_id", "value_text")
            ):
                text_rows[row["question_id"]].append(
                    {
                        "label": row["value_text"] or "Sin respuesta",
                        "count": row["count"],
                    }
                )

        # "Otro" free-text picks don't have a SurveyOption row, so they're
        # aggregated separately (any non-empty value_text on an
        # allow_other choice question is an "Otro" pick — see
        # ``SurveyRespondView._save_answers``) and folded in as their own
        # category below.
        other_counts = {}
        if other_question_ids:
            other_counts = {
                row["question_id"]: row["count"]
                for row in (
                    SurveyAnswer.objects.filter(
                        question_id__in=other_question_ids, response_id__in=self.response_ids
                    )
                    .exclude(value_text="")
                    .values("question_id")
                    .annotate(count=Count("id"))
                )
            }

        summaries = []
        for question in self.questions:
            if question.question_type not in CHOICE_QUESTION_TYPES:
                continue
            rows = (
                option_rows.get(question.pk, [])
                if question.question_type in option_choice_types
                else text_rows.get(question.pk, [])
            )
            other_count = other_counts.get(question.pk)
            if other_count:
                rows = rows + [{"label": "Otro", "count": other_count}]
            denominator = self.total_responses or sum(row["count"] for row in rows)
            for row in rows:
                row["percent"] = (
                    round((row["count"] / denominator) * 100) if denominator else 0
                )
            chart_type = (
                "donut"
                if question.question_type == SurveyQuestion.QuestionType.YES_NO
                else "bar"
            )
            summaries.append(
                {
                    "question_id": question.pk,
                    "question": question.text,
                    "chart_type": chart_type,
                    "rows": rows,
                    "categories": [row["label"] for row in rows],
                    "series": [row["count"] for row in rows],
                    "answered": sum(row["count"] for row in rows),
                }
            )
        return summaries

    @cached_property
    def nps_summaries(self):
        """Per-NPS-question 0-10 distribution plus the computed NPS score.

        Score = %promoters (9-10) − %detractors (0-6), rounded to a whole
        percentage point, following the standard NPS formula.
        """
        nps_questions = [
            q for q in self.questions if q.question_type == SurveyQuestion.QuestionType.NPS
        ]
        if not nps_questions:
            return []
        question_ids = [q.pk for q in nps_questions]
        values_by_question = defaultdict(list)
        for row in SurveyAnswer.objects.filter(
            question_id__in=question_ids,
            response_id__in=self.response_ids,
            value_number__isnull=False,
        ).values("question_id", "value_number"):
            values_by_question[row["question_id"]].append(int(row["value_number"]))

        summaries = []
        for question in nps_questions:
            values = [v for v in values_by_question.get(question.pk, []) if 0 <= v <= 10]
            counts = [0] * 11
            for value in values:
                counts[value] += 1
            total = len(values)
            promoters = sum(counts[9:11])
            detractors = sum(counts[0:7])
            score = round(((promoters - detractors) / total) * 100) if total else None
            summaries.append(
                {
                    "question_id": question.pk,
                    "question": question.text,
                    "chart_type": "bar",
                    "categories": [str(i) for i in range(11)],
                    "series": counts,
                    "answered": total,
                    "nps_score": score,
                    "subtitle": f"NPS: {score}" if score is not None else "NPS: Sin datos",
                }
            )
        return summaries

    @cached_property
    def ranking_summaries(self):
        """Per-RANKING-question average position per option (lower = better)."""
        ranking_questions = [
            q for q in self.questions if q.question_type == SurveyQuestion.QuestionType.RANKING
        ]
        if not ranking_questions:
            return []
        question_ids = [q.pk for q in ranking_questions]
        rows = list(
            SurveyAnswer.objects.filter(question_id__in=question_ids, response_id__in=self.response_ids)
            .exclude(value_text="")
            .values("question_id", "value_text")
        )
        positions_by_question = defaultdict(lambda: defaultdict(list))
        answered_by_question = defaultdict(int)
        for row in rows:
            try:
                ordered_values = json.loads(row["value_text"])
            except (TypeError, ValueError):
                continue
            if not isinstance(ordered_values, list):
                continue
            answered_by_question[row["question_id"]] += 1
            for position, value in enumerate(ordered_values, start=1):
                positions_by_question[row["question_id"]][value].append(position)

        summaries = []
        for question in ranking_questions:
            option_labels = {
                option.value: option.label for option in question.options.filter(is_active=True)
            }
            positions = positions_by_question.get(question.pk, {})
            option_rows = []
            for value, label in option_labels.items():
                option_positions = positions.get(value, [])
                avg_position = (
                    round(sum(option_positions) / len(option_positions), 2)
                    if option_positions
                    else None
                )
                option_rows.append(
                    {"label": label, "avg_position": avg_position, "responses": len(option_positions)}
                )
            option_rows.sort(key=lambda row: (row["avg_position"] is None, row["avg_position"]))
            summaries.append(
                {
                    "question_id": question.pk,
                    "question": question.text,
                    "chart_type": "bar",
                    "rows": option_rows,
                    "categories": [row["label"] for row in option_rows],
                    "series": [row["avg_position"] or 0 for row in option_rows],
                    "answered": answered_by_question.get(question.pk, 0),
                    "subtitle": "Posición promedio (menor = mejor)",
                }
            )
        return summaries

    @cached_property
    def trend(self):
        """30-day daily submission counts (categories + series)."""
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        trend_start = today_start - timezone.timedelta(days=29)
        trend_map = {
            row["day"]: row["count"]
            for row in (
                self._base_responses.filter(submitted_at__gte=trend_start)
                .annotate(day=TruncDate("submitted_at"))
                .values("day")
                .annotate(count=Count("id"))
            )
        }
        categories = []
        series = []
        for offset in range(30):
            day = (trend_start + timezone.timedelta(days=offset)).date()
            categories.append(day.strftime("%d/%m"))
            series.append(trend_map.get(day, 0))
        return {"categories": categories, "series": series}

    @cached_property
    def question_summaries(self):
        """Completion table: answered/missing counts plus number stats and text samples."""
        question_ids = [question.pk for question in self.questions]
        answers = SurveyAnswer.objects.filter(
            question_id__in=question_ids, response_id__in=self.response_ids
        )

        # An answer row is created for every visible question during submit, so
        # "answered" must count only rows that hold actual content. The combined
        # AND condition matches fully-empty answers; ``distinct`` collapses the
        # M2M fan-out from the ``selected_options`` join.
        empty_answer = (
            Q(value_text="")
            & Q(value_number__isnull=True)
            & Q(value_date__isnull=True)
            & Q(value_time__isnull=True)
            & (Q(value_file="") | Q(value_file__isnull=True))
            & Q(latitude__isnull=True)
            & Q(longitude__isnull=True)
            & Q(selected_options__isnull=True)
        )
        answered_map = {
            row["question_id"]: row["count"]
            for row in answers.exclude(empty_answer)
            .values("question_id")
            .annotate(count=Count("id", distinct=True))
        }

        number_map = {
            row["question_id"]: row
            for row in answers.filter(
                question__question_type=SurveyQuestion.QuestionType.NUMBER
            )
            .values("question_id")
            .annotate(
                avg=Avg("value_number"),
                min=Min("value_number"),
                max=Max("value_number"),
            )
        }

        text_question_ids = [
            question.pk
            for question in self.questions
            if question.question_type in TEXT_QUESTION_TYPES
        ]
        samples_map = defaultdict(list)
        if text_question_ids:
            for row in (
                answers.filter(question_id__in=text_question_ids)
                .exclude(value_text="")
                .order_by("question_id", "-response__submitted_at")
                .values("question_id", "value_text")
            ):
                bucket = samples_map[row["question_id"]]
                if len(bucket) < 3:
                    bucket.append(row["value_text"])

        total_responses = self.total_responses
        summaries = []
        for question in self.questions:
            answered = answered_map.get(question.pk, 0)
            summary = {
                "question": question,
                "answered": answered,
                "missing": max(total_responses - answered, 0),
                "completion_percent": round((answered / total_responses) * 100)
                if total_responses
                else 0,
            }
            if question.question_type == SurveyQuestion.QuestionType.NUMBER:
                stats = number_map.get(question.pk)
                summary["number_stats"] = (
                    {"avg": stats["avg"], "min": stats["min"], "max": stats["max"]}
                    if stats
                    else {"avg": None, "min": None, "max": None}
                )
            elif question.question_type in TEXT_QUESTION_TYPES:
                summary["samples"] = samples_map.get(question.pk, [])
            summaries.append(summary)
        return summaries

    @cached_property
    def location_points(self):
        """Lat/lng rows for LOCATION answers, consumed by the map endpoint."""
        location_question_ids = [
            question.pk
            for question in self.questions
            if question.question_type == SurveyQuestion.QuestionType.LOCATION
        ]
        if not location_question_ids or not self.response_ids:
            return []
        rows = (
            SurveyAnswer.objects.filter(
                question_id__in=location_question_ids,
                response_id__in=self.response_ids,
                latitude__isnull=False,
                longitude__isnull=False,
            )
            .values("latitude", "longitude", "question__text")
            .order_by("-response__submitted_at")
        )
        return [
            {
                "lat": float(row["latitude"]),
                "lng": float(row["longitude"]),
                "question": row["question__text"],
            }
            for row in rows
        ]

    def payload(self):
        """JSON-serializable payload for the dashboard initial render and live feed."""
        return {
            "survey_id": self.survey.pk,
            "question_count": len(self.questions),
            "choice_summaries": self.choice_summaries + self.nps_summaries + self.ranking_summaries,
            "trend": self.trend,
            **self.stat_tiles,
        }
