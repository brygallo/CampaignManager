import csv
import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Count, Max, Q, Sum
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import ListView, TemplateView, View

from apps.insoles.views import InstanceBaseFormView

from .forms import (
    DynamicSurveyResponseForm,
    SurveyQuestionBuilderForm,
    SurveySectionBuilderForm,
)
from .models import (
    Survey,
    SurveyAnswer,
    SurveyOption,
    SurveyQuestion,
    SurveyResponse,
    SurveySection,
)
from .services import update_survey_question_positions

def user_can_apply_survey(user, survey):
    if not survey.requires_login:
        return True
    if not user.is_authenticated:
        return False
    if user.has_perm("surveys.apply_all_surveys"):
        return True
    if survey.all_users_can_respond:
        return True
    return survey.assigned_users.filter(pk=user.pk).exists()


class SurveyApplyListView(LoginRequiredMixin, ListView):
    template_name = "surveys/apply_list.html"
    context_object_name = "surveys"

    def get_queryset(self):
        from django.utils import timezone

        now = timezone.now()
        queryset = (
            Survey.objects.filter(status=Survey.Status.PUBLISHED, is_active=True)
            .filter(Q(starts_at__isnull=True) | Q(starts_at__lte=now))
            .filter(Q(ends_at__isnull=True) | Q(ends_at__gte=now))
        )
        if not self.request.user.has_perm("surveys.apply_all_surveys"):
            queryset = queryset.filter(
                Q(requires_login=False)
                | Q(all_users_can_respond=True)
                | Q(assigned_users=self.request.user)
            )
        return queryset.distinct().order_by("title")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["page_title"] = "Aplicar encuestas"
        context["breadcrumbs"] = [
            ("Inicio", "/"),
            ("Encuestas", None),
            ("Aplicar", None),
        ]
        return context


class SurveyAccessMixin:
    def get_survey(self):
        lookup = {"pk": self.kwargs["pk"]} if "pk" in self.kwargs else {"slug": self.kwargs["slug"]}
        return get_object_or_404(Survey, **lookup)


class SurveyBuilderView(LoginRequiredMixin, PermissionRequiredMixin, SurveyAccessMixin, TemplateView):
    template_name = "surveys/builder.html"
    permission_required = "surveys.change_survey"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        survey = self.get_survey()
        context.update(
            {
                "survey": survey,
                "sections": survey.sections.filter(is_active=True).prefetch_related(
                    "questions__options"
                ),
                "questions": survey.questions.filter(is_active=True).prefetch_related("options"),
                "form": kwargs.get("form") or SurveyQuestionBuilderForm(),
                "question_modal_url": reverse(
                    "surveys:builder_question_modal", kwargs={"pk": survey.pk}
                ),
                "section_modal_url": reverse(
                    "surveys:builder_section_modal", kwargs={"pk": survey.pk}
                ),
                "reorder_url": reverse("surveys:builder_reorder", kwargs={"pk": survey.pk}),
                "page_title": f"Constructor: {survey.title}",
                "breadcrumbs": [
                    ("Inicio", "/"),
                    ("Encuestas", reverse("site:surveys_survey_listar")),
                    (survey.title, survey.get_absolute_url()),
                    ("Constructor", None),
                ],
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        self.survey = self.get_survey()
        action = request.POST.get("action")
        if action == "delete_question":
            return self._delete_question(request)
        if action == "duplicate_question":
            return self._duplicate_question(request)
        if action == "publish_survey":
            return self._change_status(Survey.Status.PUBLISHED, "Encuesta publicada.")
        if action == "close_survey":
            return self._change_status(Survey.Status.CLOSED, "Encuesta cerrada.")
        form = SurveyQuestionBuilderForm(request.POST, survey=self.survey)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))
        question = form.save(commit=False)
        question.survey = self.survey
        question.order = (self.survey.questions.aggregate(max_order=Max("order"))["max_order"] or 0) + 1
        question.save()
        self._sync_options(question, form.cleaned_data.get("option_lines", ""))
        messages.success(request, "Pregunta agregada.")
        return HttpResponseRedirect(reverse("surveys:builder", kwargs={"pk": self.survey.pk}))

    def _delete_question(self, request):
        question = get_object_or_404(
            SurveyQuestion,
            pk=request.POST.get("question_id"),
            survey=self.survey,
        )
        question.is_active = False
        question.save(update_fields=["is_active"])
        messages.success(request, "Pregunta retirada del formulario.")
        return HttpResponseRedirect(reverse("surveys:builder", kwargs={"pk": self.survey.pk}))

    def _duplicate_question(self, request):
        source = get_object_or_404(
            SurveyQuestion.objects.prefetch_related("options"),
            pk=request.POST.get("question_id"),
            survey=self.survey,
        )
        copy = SurveyQuestion.objects.create(
            survey=self.survey,
            section=source.section,
            text=f"Copia de {source.text}",
            help_text=source.help_text,
            question_type=source.question_type,
            is_required=source.is_required,
            order=(self.survey.questions.aggregate(max_order=Max("order"))["max_order"] or 0) + 1,
            visibility_question=source.visibility_question,
            visibility_operator=source.visibility_operator,
            visibility_option=source.visibility_option,
            visibility_value=source.visibility_value,
        )
        for option in source.options.filter(is_active=True):
            SurveyOption.objects.create(
                question=copy,
                label=option.label,
                value=option.value,
                order=option.order,
            )
        messages.success(request, "Pregunta duplicada.")
        return HttpResponseRedirect(reverse("surveys:builder", kwargs={"pk": self.survey.pk}))

    def _sync_options(self, question, option_lines):
        if not question.uses_options:
            return
        labels = self._option_labels(option_lines)
        for index, label in enumerate(labels, start=1):
            SurveyOption.objects.create(
                question=question,
                label=label,
                value=label,
                order=index,
            )

    def _option_labels(self, option_lines):
        if isinstance(option_lines, str):
            values = option_lines.splitlines()
        else:
            values = option_lines or []
        return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))

    def _change_status(self, status, message):
        self.survey.status = status
        self.survey.save(update_fields=["status"])
        messages.success(self.request, message)
        return HttpResponseRedirect(reverse("surveys:builder", kwargs={"pk": self.survey.pk}))


class SurveyBuilderQuestionInsoleView(LoginRequiredMixin, InstanceBaseFormView):
    model = Survey
    form_class = SurveyQuestionBuilderForm
    create_url_name = "surveys:builder_question_modal"
    title = "Agregar pregunta"
    confirm_button = "Agregar pregunta"
    max_width = "760px"

    def has_permission(self):
        return self.request.user.has_perm("surveys.change_survey")

    def get_form_kwargs(self):
        kwargs = {}
        if self.request.POST or self.request.FILES:
            kwargs.update({"data": self.request.POST, "files": self.request.FILES})
        kwargs["survey"] = self.get_object()
        return kwargs

    def form_valid(self, form):
        self.survey = self.get_object()
        question = form.save(commit=False)
        question.survey = self.survey
        question.order = (self.survey.questions.aggregate(max_order=Max("order"))["max_order"] or 0) + 1
        question.save()
        self._sync_options(question, form.cleaned_data.get("option_lines", ""))
        return self.success("Pregunta agregada.")

    def _sync_options(self, question, option_lines):
        if not question.uses_options:
            return
        labels = self._option_labels(option_lines)
        for index, label in enumerate(labels, start=1):
            SurveyOption.objects.create(question=question, label=label, value=label, order=index)

    def _option_labels(self, option_lines):
        if isinstance(option_lines, str):
            values = option_lines.splitlines()
        else:
            values = option_lines or []
        return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


class SurveyBuilderQuestionEditInsoleView(SurveyBuilderQuestionInsoleView):
    model = SurveyQuestion
    create_url_name = "surveys:builder_question_edit_modal"
    title = "Editar pregunta"
    confirm_button = "Guardar cambios"

    def get_object(self):
        return get_object_or_404(
            SurveyQuestion,
            pk=self.kwargs["question_pk"],
            survey_id=self.kwargs["pk"],
        )

    def get_create_url(self):
        return reverse(
            self.create_url_name,
            kwargs={"pk": self.kwargs["pk"], "question_pk": self.kwargs["question_pk"]},
        )

    def get_form_kwargs(self):
        kwargs = {"instance": self.get_object()}
        if self.request.POST or self.request.FILES:
            kwargs.update({"data": self.request.POST, "files": self.request.FILES})
        kwargs["survey"] = self.get_object().survey
        return kwargs

    def form_valid(self, form):
        question = form.save()
        question.options.update(is_active=False)
        self._sync_options(question, form.cleaned_data.get("option_lines", ""))
        return self.success("Pregunta actualizada.")


class SurveyBuilderSectionInsoleView(LoginRequiredMixin, InstanceBaseFormView):
    model = Survey
    form_class = SurveySectionBuilderForm
    create_url_name = "surveys:builder_section_modal"
    title = "Agregar sección"
    confirm_button = "Agregar sección"
    max_width = "640px"

    def has_permission(self):
        return self.request.user.has_perm("surveys.change_survey")

    def get_form_kwargs(self):
        kwargs = {}
        if self.request.POST or self.request.FILES:
            kwargs.update({"data": self.request.POST, "files": self.request.FILES})
        return kwargs

    def form_valid(self, form):
        survey = self.get_object()
        section = form.save(commit=False)
        section.survey = survey
        section.order = (survey.sections.aggregate(max_order=Max("order"))["max_order"] or 0) + 1
        section.save()
        return self.success("Sección agregada.")


class SurveyBuilderSectionEditInsoleView(SurveyBuilderSectionInsoleView):
    model = SurveySection
    create_url_name = "surveys:builder_section_edit_modal"
    title = "Editar sección"
    confirm_button = "Guardar cambios"

    def get_object(self):
        return get_object_or_404(
            SurveySection,
            pk=self.kwargs["section_pk"],
            survey_id=self.kwargs["pk"],
        )

    def get_create_url(self):
        return reverse(
            self.create_url_name,
            kwargs={"pk": self.kwargs["pk"], "section_pk": self.kwargs["section_pk"]},
        )

    def get_form_kwargs(self):
        kwargs = {"instance": self.get_object()}
        if self.request.POST or self.request.FILES:
            kwargs.update({"data": self.request.POST, "files": self.request.FILES})
        return kwargs

    def form_valid(self, form):
        form.save()
        return self.success("Sección actualizada.")


class SurveyBuilderReorderView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = "surveys.change_survey"
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        survey = get_object_or_404(Survey, pk=kwargs["pk"])
        item_type = request.POST.get("type")
        ordered_ids = [value for value in request.POST.getlist("ids[]") if value]
        if item_type == "sections":
            queryset = survey.sections.filter(pk__in=ordered_ids)
        elif item_type == "questions":
            queryset = survey.questions.filter(pk__in=ordered_ids)
        elif item_type == "questions_bulk":
            return self._update_question_positions(request, survey)
        else:
            return JsonResponse({"error": "Tipo de ordenamiento no válido."}, status=400)
        objects = {str(obj.pk): obj for obj in queryset}
        section_id = request.POST.get("section_id")
        section = None
        if item_type == "questions" and section_id:
            section = get_object_or_404(SurveySection, pk=section_id, survey=survey)
        for index, object_id in enumerate(ordered_ids, start=1):
            obj = objects.get(str(object_id))
            if not obj:
                continue
            changed = []
            if obj.order != index:
                obj.order = index
                changed.append("order")
            if item_type == "questions" and section_id is not None and obj.section_id != (section.pk if section else None):
                obj.section = section
                changed.append("section")
            if changed:
                obj.save(update_fields=changed)
        return JsonResponse({"message": "Orden actualizado."})

    def _update_question_positions(self, request, survey):
        placements = []
        for raw_placement in request.POST.getlist("placements[]"):
            try:
                placement = json.loads(raw_placement)
            except (TypeError, ValueError):
                return JsonResponse({"error": "Orden de preguntas no válido."}, status=400)
            question_id = str(placement.get("question_id") or "")
            section_id = str(placement.get("section_id") or "")
            order = placement.get("order")
            if not question_id:
                continue
            try:
                order = int(order)
            except (TypeError, ValueError):
                return JsonResponse({"error": "Orden de preguntas no válido."}, status=400)
            placements.append(
                {
                    "question_id": question_id,
                    "section_id": section_id,
                    "order": order,
                }
            )

        try:
            update_survey_question_positions(survey, placements)
        except ValueError:
            return JsonResponse({"error": "Sección destino no válida."}, status=400)
        return JsonResponse({"message": "Orden actualizado."})


class SurveyRespondView(SurveyAccessMixin, TemplateView):
    template_name = "surveys/respond.html"

    def dispatch(self, request, *args, **kwargs):
        self.survey = self.get_survey()
        if self.survey.requires_login and not request.user.is_authenticated:
            from django.contrib.auth.views import redirect_to_login

            return redirect_to_login(request.get_full_path())
        if not user_can_apply_survey(request.user, self.survey):
            messages.error(request, "No tienes asignada esta encuesta.")
            return HttpResponseRedirect(reverse("surveys:apply_list"))
        return super().dispatch(request, *args, **kwargs)

    def get_form(self):
        return DynamicSurveyResponseForm(
            self.request.POST or None,
            self.request.FILES or None,
            survey=self.survey,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["survey"] = self.survey
        form = kwargs.get("form") or self.get_form()
        context["form"] = form
        context["question_groups"] = form.grouped_bound_fields()
        context["page_title"] = self.survey.title
        return context

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if not self.survey.is_open:
            messages.error(request, "Esta encuesta no está disponible.")
            return self.render_to_response(self.get_context_data(form=form))
        if self._has_existing_response(request):
            messages.error(request, "Ya registraste una respuesta para esta encuesta.")
            return self.render_to_response(self.get_context_data(form=form))
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))
        response = SurveyResponse.objects.create(
            survey=self.survey,
            respondent=None if self.survey.is_anonymous else request.user if request.user.is_authenticated else None,
            ip_address=self._client_ip(),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        self._save_answers(response, form)
        return HttpResponseRedirect(reverse("surveys:thanks", kwargs={"slug": self.survey.slug}))

    def _has_existing_response(self, request):
        if self.survey.allow_multiple_responses or not request.user.is_authenticated:
            return False
        return SurveyResponse.objects.filter(survey=self.survey, respondent=request.user).exists()

    def _client_ip(self):
        forwarded = self.request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return self.request.META.get("REMOTE_ADDR")

    def _save_answers(self, response, form):
        for question in form.questions:
            if not form.is_question_visible(question, form.cleaned_data):
                continue
            value = form.cleaned_data.get(form.field_name(question))
            answer = SurveyAnswer(response=response, question=question)
            qtype = question.question_type
            selected_option_ids = []
            if qtype == SurveyQuestion.QuestionType.NUMBER:
                answer.value_number = value
            elif qtype == SurveyQuestion.QuestionType.DATE:
                answer.value_date = value
            elif qtype == SurveyQuestion.QuestionType.TIME:
                answer.value_time = value
            elif qtype in {SurveyQuestion.QuestionType.FILE, SurveyQuestion.QuestionType.IMAGE}:
                answer.value_file = value
            elif qtype == SurveyQuestion.QuestionType.SINGLE_CHOICE:
                selected_option_ids = [value] if value else []
            elif qtype == SurveyQuestion.QuestionType.MULTIPLE_CHOICE:
                selected_option_ids = value or []
            elif qtype == SurveyQuestion.QuestionType.LOCATION:
                lat = form.cleaned_data.get(form.lat_field_name(question))
                lng = form.cleaned_data.get(form.lng_field_name(question))
                if lat is not None and lng is not None:
                    answer.latitude = lat
                    answer.longitude = lng
                    answer.value_text = f"{lat}, {lng}"
            else:
                answer.value_text = value or ""
            answer.save()
            if selected_option_ids:
                answer.selected_options.set(selected_option_ids)


class SurveyThanksView(SurveyAccessMixin, TemplateView):
    template_name = "surveys/thanks.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["survey"] = self.get_survey()
        context["page_title"] = "Respuesta registrada"
        return context


class SurveyResultsView(LoginRequiredMixin, PermissionRequiredMixin, SurveyAccessMixin, TemplateView):
    template_name = "surveys/results.html"
    permission_required = "surveys.view_survey_results"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        survey = self.get_survey()
        questions = list(survey.questions.filter(is_active=True).prefetch_related("options"))
        responses = survey.responses.prefetch_related("answers__question", "answers__selected_options")
        context.update(
            {
                "survey": survey,
                "questions": questions,
                "responses": responses[:100],
                "total_responses": responses.count(),
                "page_title": f"Resultados: {survey.title}",
                "choice_summaries": self._choice_summaries(questions),
            }
        )
        return context

    def _choice_summaries(self, questions):
        summaries = []
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
                rows = (
                    question.options.annotate(count=Count("answers"))
                    .values("label", "count")
                    .order_by("order", "label")
                )
            else:
                rows = (
                    SurveyAnswer.objects.filter(question=question)
                    .values("value_text")
                    .annotate(count=Count("id"))
                    .order_by("value_text")
                )
                rows = [{"label": row["value_text"] or "Sin respuesta", "count": row["count"]} for row in rows]
            summaries.append({"question": question, "rows": rows})
        return summaries


class SurveyExportCsvView(LoginRequiredMixin, PermissionRequiredMixin, SurveyAccessMixin, View):
    permission_required = "surveys.export_survey_results"

    def get(self, request, *args, **kwargs):
        survey = self.get_survey()
        questions = list(survey.questions.filter(is_active=True).order_by("section__order", "order", "id"))
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="encuesta-{survey.pk}.csv"'
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerow(["ID", "Fecha", "Usuario"] + [question.text for question in questions])
        for survey_response in survey.responses.prefetch_related("answers__question", "answers__selected_options"):
            answers = {answer.question_id: answer.display_value for answer in survey_response.answers.all()}
            writer.writerow(
                [
                    survey_response.pk,
                    survey_response.submitted_at,
                    survey_response.respondent or "",
                    *[answers.get(question.pk, "") for question in questions],
                ]
            )
        return response
