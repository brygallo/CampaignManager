from django.contrib.auth.models import AnonymousUser
from django.contrib.auth.models import Permission
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
)
from apps.surveys.views import (
    SurveyApplyListView,
    SurveyRespondView,
    SurveyResultsView,
    user_can_apply_survey,
)
from core.form_policies import apply_declared_form_policies
from superadmin import site


class DynamicSurveyResponseFormTests(TestCase):
    def setUp(self):
        self.survey = Survey.objects.create(
            title="Diagnostico",
            slug="diagnostico",
            status=Survey.Status.PUBLISHED,
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


class SurveyRespondViewTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.survey = Survey.objects.create(
            title="Encuesta abierta",
            slug="encuesta-abierta",
            status=Survey.Status.PUBLISHED,
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
        request = self.factory.post(
            reverse("surveys:respond", kwargs={"slug": self.survey.slug}),
            data={f"question_{self.question.pk}": str(self.option.pk)},
        )
        request.user = AnonymousUser()
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        response = SurveyRespondView.as_view()(request, slug=self.survey.slug)

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
            status=Survey.Status.PUBLISHED,
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
            status=Survey.Status.PUBLISHED,
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
            status=Survey.Status.DRAFT,
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

    def test_user_without_field_permissions_cannot_change_status_or_assignment(self):
        form = self._form_for(
            self.editor,
            {
                "title": "Controlada actualizada",
                "slug": "controlada",
                "description": "",
                "status": Survey.Status.PUBLISHED,
                "requires_login": "on",
                "all_users_can_respond": "on",
                "assigned_users": [],
                "thank_you_message": "Gracias",
            },
        )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.survey.refresh_from_db()

        self.assertEqual(self.survey.status, Survey.Status.DRAFT)
        self.assertFalse(self.survey.all_users_can_respond)
        self.assertEqual(list(self.survey.assigned_users.all()), [self.assigned_user])

    def test_user_with_field_permissions_can_change_status_and_assignment(self):
        self.editor.user_permissions.add(
            Permission.objects.get(codename="publish_survey"),
            Permission.objects.get(codename="manage_survey_assignments"),
        )
        form = self._form_for(
            self.editor,
            {
                "title": "Controlada actualizada",
                "slug": "controlada",
                "description": "",
                "status": Survey.Status.PUBLISHED,
                "requires_login": "on",
                "all_users_can_respond": "on",
                "assigned_users": [],
                "thank_you_message": "Gracias",
            },
        )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.survey.refresh_from_db()

        self.assertEqual(self.survey.status, Survey.Status.PUBLISHED)
        self.assertTrue(self.survey.all_users_can_respond)
        self.assertEqual(list(self.survey.assigned_users.all()), [])


class SurveyResultsViewTests(TestCase):
    def test_choice_summaries_include_scale_answers(self):
        survey = Survey.objects.create(
            title="Resultados",
            slug="resultados",
            status=Survey.Status.PUBLISHED,
        )
        question = SurveyQuestion.objects.create(
            survey=survey,
            text="Satisfaccion",
            question_type=SurveyQuestion.QuestionType.SCALE_5,
        )
        response = SurveyResponse.objects.create(survey=survey)
        SurveyAnswer.objects.create(response=response, question=question, value_text="4")

        summaries = SurveyResultsView()._choice_summaries([question])

        self.assertEqual(summaries[0]["rows"], [{"label": "4", "count": 1}])
