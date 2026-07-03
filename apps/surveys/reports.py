from django.db.models import Q

from apps.reporting.exporters import ReportColumn, TabularReport


def filtered_survey_responses(survey, params=None):
    params = params or {}
    responses = survey.responses.select_related("respondent").prefetch_related(
        "answers__question", "answers__selected_options"
    )
    date_from = params.get("date_from")
    date_to = params.get("date_to")
    search = (params.get("q") or "").strip()
    if date_from:
        responses = responses.filter(submitted_at__date__gte=date_from)
    if date_to:
        responses = responses.filter(submitted_at__date__lte=date_to)
    if search:
        responses = responses.filter(
            Q(respondent__username__icontains=search)
            | Q(respondent__email__icontains=search)
            | Q(respondent__first_name__icontains=search)
            | Q(respondent__last_name__icontains=search)
            | Q(answers__value_text__icontains=search)
            | Q(answers__selected_options__label__icontains=search)
        )
    return responses.distinct().order_by("-submitted_at")


def survey_responses_report(survey, questions=None, responses=None):
    questions = questions or list(
        survey.questions.filter(is_active=True).order_by("section__order", "order", "id")
    )

    def respondent(response):
        if survey.is_anonymous:
            return "Anónima"
        return response.respondent or response.respondent_name or "Pública"

    def answer_for(question):
        def _value(response):
            answers = getattr(response, "_survey_answer_map", None)
            if answers is None:
                answers = {answer.question_id: answer.display_value for answer in response.answers.all()}
            return answers.get(question.pk, "")

        return _value

    columns = [
        ReportColumn("ID", "pk", width=10),
        ReportColumn("Fecha", "submitted_at", width=20),
        ReportColumn("Usuario", respondent, width=24),
    ]
    columns.extend(ReportColumn(question.text, answer_for(question), width=28) for question in questions)
    rows = list(filtered_survey_responses(survey) if responses is None else responses)
    for response in rows:
        response._survey_answer_map = {
            answer.question_id: answer.display_value for answer in response.answers.all()
        }
    return TabularReport(
        title=f"Resultados: {survey.title}",
        filename=f"encuesta-{survey.pk}",
        sheet_name="Respuestas",
        columns=tuple(columns),
        rows=rows,
    )
