import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Max, Q
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import ListView, TemplateView, View

from apps.insoles.views import InstanceBaseFormView
from apps.reporting.views import ReportExportView

from .forms import (
    DynamicSurveyResponseForm,
    SurveyQuestionBuilderForm,
    SurveySectionBuilderForm,
)
from .reports import filtered_survey_responses, survey_responses_report
from .models import (
    Survey,
    SurveyAnswer,
    SurveyOption,
    SurveyQuestion,
    SurveyResponse,
    SurveySection,
)
from .services import (
    SurveyResultsSummary,
    get_survey_publication_issues,
    update_survey_question_positions,
)

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
                "unsectioned_questions": survey.questions.filter(
                    is_active=True,
                    section__isnull=True,
                ).prefetch_related("options"),
                "form": kwargs.get("form") or SurveyQuestionBuilderForm(survey=survey),
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
        if not self.request.user.has_perm("surveys.publish_survey"):
            raise PermissionDenied
        if status == Survey.Status.PUBLISHED:
            issues = get_survey_publication_issues(self.survey)
            if issues:
                for issue in issues:
                    messages.error(self.request, issue)
                return HttpResponseRedirect(reverse("surveys:builder", kwargs={"pk": self.survey.pk}))
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
        elif self.request.GET.get("section"):
            kwargs["initial"] = {"section": self.request.GET.get("section")}
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

    # The slug route is reached by name/URL guessing, so it always requires
    # login for anonymous visitors. The shareable anonymous entry point is
    # the signed token route (SurveyPublicRespondView below), which flips
    # this flag on for surveys that don't require login.
    allow_anonymous_public_access = False

    def dispatch(self, request, *args, **kwargs):
        self.survey = self.get_survey()
        # Editors can preview a non-open survey even if they are not part of
        # the assigned audience; the preview never allows submitting (POST
        # is still rejected for non-open surveys below).
        self.can_preview = request.user.has_perm("surveys.change_survey")
        anonymous_allowed = self.allow_anonymous_public_access and not self.survey.requires_login
        if not request.user.is_authenticated and not anonymous_allowed:
            from django.contrib.auth.views import redirect_to_login

            return redirect_to_login(request.get_full_path())
        if not user_can_apply_survey(request.user, self.survey):
            is_preview_bypass = self.can_preview and not self.survey.is_open
            if not is_preview_bypass:
                messages.error(request, "No tienes asignada esta encuesta.")
                return HttpResponseRedirect(reverse("surveys:apply_list"))
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        if not self.survey.is_open and not self.can_preview:
            return self.render_to_response(self.get_unavailable_context())
        return super().get(request, *args, **kwargs)

    def get_unavailable_context(self):
        return {
            "survey": self.survey,
            "survey_unavailable": True,
            "page_title": self.survey.title,
        }

    def get_form(self):
        return DynamicSurveyResponseForm(
            self.request.POST or None,
            self.request.FILES or None,
            survey=self.survey,
            user=self.request.user,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["survey"] = self.survey
        form = kwargs.get("form") or self.get_form()
        context["form"] = form
        context["question_groups"] = form.grouped_bound_fields()
        context["page_title"] = self.survey.title
        context["survey_unavailable"] = False
        context["is_preview"] = not self.survey.is_open and self.can_preview
        return context

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if not self.survey.is_open:
            messages.error(request, "Esta encuesta no está disponible.")
            if not self.can_preview:
                return self.render_to_response(self.get_unavailable_context())
            return self.render_to_response(self.get_context_data(form=form))
        if self._has_existing_response(request):
            messages.error(request, "Ya registraste una respuesta para esta encuesta.")
            return self.render_to_response(self.get_context_data(form=form))
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))
        respondent_name = ""
        respondent_email = ""
        if getattr(form, "include_respondent_fields", False):
            respondent_name = form.cleaned_data.get("respondent_name", "")
            respondent_email = form.cleaned_data.get("respondent_email", "")
        response = SurveyResponse.objects.create(
            survey=self.survey,
            respondent=None if self.survey.is_anonymous else request.user if request.user.is_authenticated else None,
            respondent_name=respondent_name,
            respondent_email=respondent_email,
            # Anonymous surveys must not retain identifying request metadata.
            ip_address=None if self.survey.is_anonymous else self._client_ip(),
            user_agent="" if self.survey.is_anonymous else request.META.get("HTTP_USER_AGENT", ""),
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
            if qtype in {SurveyQuestion.QuestionType.NUMBER, SurveyQuestion.QuestionType.NPS}:
                answer.value_number = value
            elif qtype == SurveyQuestion.QuestionType.DATE:
                answer.value_date = value
            elif qtype == SurveyQuestion.QuestionType.TIME:
                answer.value_time = value
            elif qtype in {SurveyQuestion.QuestionType.FILE, SurveyQuestion.QuestionType.IMAGE}:
                answer.value_file = value
            elif qtype == SurveyQuestion.QuestionType.SINGLE_CHOICE:
                if question.allow_other and value == form.OTHER_VALUE:
                    answer.value_text = form.cleaned_data.get(form.other_field_name(question), "")
                elif value:
                    selected_option_ids = [value]
            elif qtype == SurveyQuestion.QuestionType.MULTIPLE_CHOICE:
                values = value or []
                if question.allow_other and form.OTHER_VALUE in values:
                    answer.value_text = form.cleaned_data.get(form.other_field_name(question), "")
                    selected_option_ids = [v for v in values if v != form.OTHER_VALUE]
                else:
                    selected_option_ids = values
            elif qtype == SurveyQuestion.QuestionType.RANKING:
                answer.value_text = value or ""
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


class SurveyPublicRespondView(SurveyRespondView):
    """Anonymous entry point for open surveys, reached via a signed token
    instead of the slug (see ``Survey.public_token``/``resolve_public_token``).

    Everything else (form rendering, submission, respondent fields) is
    inherited unchanged from ``SurveyRespondView``; only survey resolution
    and the anonymous-access gate differ.
    """

    allow_anonymous_public_access = True

    def get_survey(self):
        survey = Survey.resolve_public_token(self.kwargs.get("token"))
        if survey is None:
            raise Http404("Enlace no válido.")
        return survey


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
        summary = SurveyResultsSummary(survey, self.request.GET)

        paginator = Paginator(summary.responses, 25)
        page_obj = paginator.get_page(self.request.GET.get("page"))

        filter_params = self.request.GET.copy()
        filter_params.pop("page", None)

        context.update(
            {
                "survey": survey,
                "questions": summary.questions,
                "payload": summary.payload(),
                "page_obj": page_obj,
                "responses": page_obj.object_list,
                "filters": {
                    "q": self.request.GET.get("q", ""),
                    "date_from": self.request.GET.get("date_from", ""),
                    "date_to": self.request.GET.get("date_to", ""),
                },
                "filters_querystring": filter_params.urlencode(),
                "page_title": f"Resultados: {survey.title}",
                "has_location_questions": summary.has_location_questions,
                "results_data_url": reverse("surveys:results_data", kwargs={"pk": survey.pk}),
                "results_map_data_url": reverse(
                    "surveys:results_map_data", kwargs={"pk": survey.pk}
                ),
                "question_summaries": summary.question_summaries,
            }
        )
        return context


class SurveyResultsDataView(
    LoginRequiredMixin, PermissionRequiredMixin, SurveyAccessMixin, View
):
    """Live JSON feed for the results dashboard (tiles + charts + trend).

    Honors the same GET filters as ``SurveyResultsView`` so the page can
    re-render without a full reload.
    """

    permission_required = "surveys.view_survey_results"

    def get(self, request, *args, **kwargs):
        survey = self.get_survey()
        return JsonResponse(SurveyResultsSummary(survey, request.GET).payload())


class SurveyResultsMapDataView(
    LoginRequiredMixin, PermissionRequiredMixin, SurveyAccessMixin, View
):
    """Return geo points for LOCATION-type answers, honoring active filters."""

    permission_required = "surveys.view_survey_results"

    def get(self, request, *args, **kwargs):
        survey = self.get_survey()
        points = SurveyResultsSummary(survey, request.GET).location_points
        return JsonResponse({"points": points, "count": len(points)})


class SurveyExportView(LoginRequiredMixin, PermissionRequiredMixin, SurveyAccessMixin, ReportExportView):
    permission_required = "surveys.export_survey_results"
    file_format = "csv"

    def get_report(self):
        survey = self.get_survey()
        return survey_responses_report(
            survey,
            responses=filtered_survey_responses(survey, self.request.GET),
        )


class SurveyExportCsvView(SurveyExportView):
    file_format = "csv"
