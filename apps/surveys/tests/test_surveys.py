from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.authentication.tests.factories import UserFactory
from apps.surveys.forms import (
    DynamicSurveyResponseForm,
    SurveyForm,
)
from apps.surveys.models import (
    Survey,
    SurveyAnswer,
    SurveyOption,
    SurveyQuestion,
    SurveyResponse,
    SurveySection,
)
from apps.surveys.services import SurveyResultsSummary
from apps.surveys.views import (
    SurveyApplyListView,
    SurveyBuilderView,
    SurveyBuilderQuestionInsoleView,
    SurveyPublicRespondView,
    user_can_apply_survey,
)
from core.form_policies import apply_declared_form_policies
from superadmin import site


class DynamicSurveyResponseFormTests(TestCase):
    def setUp(self):
        self.survey = Survey.objects.create(
            title="Diagnostico",
            slug="diagnostico",
            state=Survey.workflow.PUBLISHED,
            requires_login=False,
        )
        self.parent = SurveyQuestion.objects.create(
            survey=self.survey,
            text="Canales",
            question_type=SurveyQuestion.QuestionType.MULTIPLE_CHOICE,
            is_required=True,
            order=1,
        )
        self.whatsapp = SurveyOption.objects.create(
            question=self.parent,
            label="WhatsApp",
            order=1,
        )
        self.email = SurveyOption.objects.create(
            question=self.parent,
            label="Correo",
            order=2,
        )
        self.follow_up = SurveyQuestion.objects.create(
            survey=self.survey,
            text="Telefono",
            question_type=SurveyQuestion.QuestionType.PHONE,
            is_required=True,
            order=2,
            visibility_question=self.parent,
            visibility_option=self.whatsapp,
        )

    def test_hidden_required_conditional_question_does_not_block_submit(self):
        form = DynamicSurveyResponseForm(
            data={f"question_{self.parent.pk}": [str(self.email.pk)]},
            survey=self.survey,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_visible_required_conditional_question_requires_value(self):
        form = DynamicSurveyResponseForm(
            data={f"question_{self.parent.pk}": [str(self.whatsapp.pk)]},
            survey=self.survey,
        )

        self.assertFalse(form.is_valid())
        self.assertIn(f"question_{self.follow_up.pk}", form.errors)

    def test_grouped_fields_use_global_question_numbers(self):
        section = SurveySection.objects.create(survey=self.survey, title="Datos")
        self.parent.section = section
        self.parent.save(update_fields=["section"])
        self.follow_up.section = section
        self.follow_up.save(update_fields=["section"])
        SurveyQuestion.objects.create(
            survey=self.survey,
            text="Observacion",
            question_type=SurveyQuestion.QuestionType.SHORT_TEXT,
            order=3,
        )

        form = DynamicSurveyResponseForm(survey=self.survey)
        numbers = [
            item["question_number"]
            for group in form.grouped_bound_fields()
            for item in group["fields"]
        ]

        self.assertEqual(numbers, [1, 2, 3])


class SurveyRespondViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.survey = Survey.objects.create(
            title="Encuesta abierta",
            slug="encuesta-abierta",
            state=Survey.workflow.PUBLISHED,
            requires_login=False,
        )
        self.question = SurveyQuestion.objects.create(
            survey=self.survey,
            text="Servicio preferido",
            question_type=SurveyQuestion.QuestionType.SINGLE_CHOICE,
            is_required=True,
        )
        self.option = SurveyOption.objects.create(question=self.question, label="Salud")

    def test_post_creates_response_and_selected_option_answer(self):
        # Anonymous visitors submit through the signed public token route;
        # the slug route now always requires login for anonymous users.
        token = self.survey.public_token()
        request = self.factory.post(
            reverse("surveys:respond_public", kwargs={"token": token}),
            data={f"question_{self.question.pk}": str(self.option.pk)},
        )
        request.user = AnonymousUser()
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        response = SurveyPublicRespondView.as_view()(request, token=token)

        self.assertEqual(response.status_code, 302)
        survey_response = SurveyResponse.objects.get(survey=self.survey)
        answer = SurveyAnswer.objects.get(response=survey_response, question=self.question)
        self.assertEqual(list(answer.selected_options.values_list("pk", flat=True)), [self.option.pk])


class SurveyAccessTests(TestCase):
    def setUp(self):
        self.assigned_user = UserFactory()
        self.other_user = UserFactory()
        self.survey = Survey.objects.create(
            title="Asignada",
            slug="asignada",
            state=Survey.workflow.PUBLISHED,
            requires_login=True,
        )
        self.survey.assigned_users.add(self.assigned_user)

    def test_user_can_apply_only_assigned_survey_without_global_permission(self):
        self.assertTrue(user_can_apply_survey(self.assigned_user, self.survey))
        self.assertFalse(user_can_apply_survey(self.other_user, self.survey))

    def test_apply_all_permission_allows_any_survey(self):
        self.other_user.user_permissions.add(Permission.objects.get(codename="apply_all_surveys"))

        self.assertTrue(user_can_apply_survey(self.other_user, self.survey))

    def test_all_users_flag_allows_authenticated_users(self):
        self.survey.all_users_can_respond = True
        self.survey.save(update_fields=["all_users_can_respond"])

        self.assertTrue(user_can_apply_survey(self.other_user, self.survey))

    def test_apply_list_filters_to_assigned_surveys(self):
        public = Survey.objects.create(
            title="Publica",
            slug="publica",
            state=Survey.workflow.PUBLISHED,
            requires_login=False,
        )
        request = RequestFactory().get(reverse("surveys:apply_list"))
        request.user = self.assigned_user
        view = SurveyApplyListView()
        view.request = request

        self.assertEqual(list(view.get_queryset()), [self.survey, public])


class SurveyFormPolicyTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.assigned_user = UserFactory()
        self.editor = UserFactory()
        self.survey = Survey.objects.create(
            title="Controlada",
            slug="controlada",
            state=Survey.workflow.DRAFT,
            requires_login=True,
        )
        self.survey.assigned_users.add(self.assigned_user)
        self.survey_site = site._registry[Survey]

    def _form_for(self, user, data):
        request = self.factory.post("/encuestas/1/editar/", data=data)
        request.user = user
        form = SurveyForm(data=data, instance=self.survey)
        return apply_declared_form_policies(
            form,
            request=request,
            obj=self.survey,
            site=self.survey_site,
        )

    def test_user_without_assignment_permission_cannot_change_assignment(self):
        # ``state`` is a protected FSM field driven by the workflow, so it is no
        # longer part of the form; a posted ``state`` key must be ignored.
        form = self._form_for(
            self.editor,
            {
                "title": "Controlada actualizada",
                "slug": "controlada",
                "description": "",
                "state": Survey.workflow.PUBLISHED,
                "requires_login": "on",
                "all_users_can_respond": "on",
                "assigned_users": [],
                "thank_you_message": "Gracias",
            },
        )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        survey = Survey.objects.get(pk=self.survey.pk)

        self.assertEqual(survey.state, Survey.workflow.DRAFT)
        self.assertFalse(survey.all_users_can_respond)
        self.assertEqual(list(survey.assigned_users.all()), [self.assigned_user])

    def test_user_with_assignment_permission_can_change_assignment(self):
        self.editor.user_permissions.add(
            Permission.objects.get(codename="manage_survey_assignments"),
        )
        form = self._form_for(
            self.editor,
            {
                "title": "Controlada actualizada",
                "slug": "controlada",
                "description": "",
                "state": Survey.workflow.PUBLISHED,
                "requires_login": "on",
                "all_users_can_respond": "on",
                "assigned_users": [],
                "thank_you_message": "Gracias",
            },
        )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        survey = Survey.objects.get(pk=self.survey.pk)

        # The workflow owns state; the form never publishes it.
        self.assertEqual(survey.state, Survey.workflow.DRAFT)
        self.assertTrue(survey.all_users_can_respond)
        self.assertEqual(list(survey.assigned_users.all()), [])


class SurveyBuilderQuestionInsoleViewTests(TestCase):
    def test_section_query_param_initializes_question_section(self):
        survey = Survey.objects.create(
            title="Constructor",
            slug="constructor",
            state=Survey.workflow.DRAFT,
        )
        section = survey.sections.create(title="Territorio")
        view = SurveyBuilderQuestionInsoleView()
        view.request = RequestFactory().get(
            reverse("surveys:builder_question_modal", kwargs={"pk": survey.pk}),
            data={"section": section.pk},
        )
        view.kwargs = {"pk": survey.pk}

        kwargs = view.get_form_kwargs()

        self.assertEqual(kwargs["initial"], {"section": str(section.pk)})


class SurveyBuilderResponseLockTests(TestCase):
    def setUp(self):
        self.user = UserFactory()
        self.user.user_permissions.add(Permission.objects.get(codename="change_survey"))
        self.client.force_login(self.user)
        self.survey = Survey.objects.create(
            title="Con respuestas",
            slug="con-respuestas",
            state=Survey.workflow.DRAFT,
        )
        self.question = SurveyQuestion.objects.create(
            survey=self.survey,
            text="Nombre",
            question_type=SurveyQuestion.QuestionType.TEXT_SHORT,
        )
        self.response = SurveyResponse.objects.create(survey=self.survey, respondent=self.user)
        SurveyAnswer.objects.create(
            response=self.response,
            question=self.question,
            value_text="Ana",
        )

    def test_builder_rejects_structure_changes_while_survey_has_responses(self):
        response = self.client.post(
            reverse("surveys:builder", kwargs={"pk": self.survey.pk}),
            {
                "text": "Nueva pregunta",
                "question_type": SurveyQuestion.QuestionType.TEXT_SHORT,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(SurveyQuestion.objects.filter(text="Nueva pregunta").exists())

    def test_clear_responses_requires_checkbox_confirmation(self):
        response = self.client.post(
            reverse("surveys:builder_clear_responses", kwargs={"pk": self.survey.pk}),
            {},
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(SurveyResponse.objects.filter(pk=self.response.pk).exists())
        self.assertTrue(self.survey.has_responses)

    def test_clear_responses_deletes_answers_and_unlocks_builder(self):
        response = self.client.post(
            reverse("surveys:builder_clear_responses", kwargs={"pk": self.survey.pk}),
            {"confirm_button": "1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(SurveyResponse.objects.filter(survey=self.survey).exists())
        self.assertFalse(SurveyAnswer.objects.filter(question=self.question).exists())
        self.assertFalse(Survey.objects.get(pk=self.survey.pk).has_responses)

    def test_question_modal_is_blocked_while_survey_has_responses(self):
        response = self.client.get(
            reverse("surveys:builder_question_modal", kwargs={"pk": self.survey.pk})
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"],
            "Vacía las respuestas antes de modificar la estructura.",
        )


class SurveyBuilderPermissionTests(TestCase):
    def test_change_survey_permission_does_not_allow_publish(self):
        survey = Survey.objects.create(
            title="Borrador",
            slug="borrador",
            state=Survey.workflow.DRAFT,
        )
        user = UserFactory()
        user.user_permissions.add(Permission.objects.get(codename="change_survey"))
        request = RequestFactory().post(
            reverse("surveys:builder", kwargs={"pk": survey.pk}),
            data={"action": "publish_survey"},
        )
        request.user = user

        with self.assertRaises(PermissionDenied):
            SurveyBuilderView.as_view()(request, pk=survey.pk)
        survey = Survey.objects.get(pk=survey.pk)

        self.assertEqual(survey.state, Survey.workflow.DRAFT)


class SurveyResultsViewTests(TestCase):
    def test_choice_summaries_include_scale_answers(self):
        survey = Survey.objects.create(
            title="Resultados",
            slug="resultados",
            state=Survey.workflow.PUBLISHED,
        )
        question = SurveyQuestion.objects.create(
            survey=survey,
            text="Satisfaccion",
            question_type=SurveyQuestion.QuestionType.SCALE_5,
        )
        response = SurveyResponse.objects.create(survey=survey)
        SurveyAnswer.objects.create(response=response, question=question, value_text="4")

        summaries = SurveyResultsSummary(survey).choice_summaries

        self.assertEqual(summaries[0]["rows"], [{"label": "4", "count": 1, "percent": 100}])
