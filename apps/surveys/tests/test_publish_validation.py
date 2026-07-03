from django.contrib.auth.models import Permission
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.authentication.tests.factories import UserFactory
from apps.surveys.models import Survey, SurveyOption, SurveyQuestion
from apps.surveys.views import SurveyBuilderView


class SurveyPublishValidationTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = UserFactory()
        self.user.user_permissions.add(
            Permission.objects.get(codename="change_survey"),
            Permission.objects.get(codename="publish_survey"),
        )

    def _publish(self, survey):
        request = self.factory.post(
            reverse("surveys:builder", kwargs={"pk": survey.pk}),
            data={"action": "publish_survey"},
        )
        request.user = self.user
        # The view emits django.contrib.messages entries, which need session
        # and message middleware attached to a bare RequestFactory request.
        SessionMiddleware(lambda req: None).process_request(request)
        MessageMiddleware(lambda req: None).process_request(request)
        return SurveyBuilderView.as_view()(request, pk=survey.pk)

    def test_publishing_survey_without_questions_is_blocked(self):
        survey = Survey.objects.create(
            title="Sin preguntas",
            slug="sin-preguntas",
            status=Survey.Status.DRAFT,
        )

        response = self._publish(survey)

        self.assertEqual(response.status_code, 302)
        survey.refresh_from_db()
        self.assertEqual(survey.status, Survey.Status.DRAFT)

    def test_publishing_valid_survey_succeeds(self):
        survey = Survey.objects.create(
            title="Encuesta valida",
            slug="encuesta-valida",
            status=Survey.Status.DRAFT,
        )
        question = SurveyQuestion.objects.create(
            survey=survey,
            text="Servicio preferido",
            question_type=SurveyQuestion.QuestionType.SINGLE_CHOICE,
            order=1,
        )
        SurveyOption.objects.create(question=question, label="Salud", order=1)
        SurveyOption.objects.create(question=question, label="Educacion", order=2)

        response = self._publish(survey)

        self.assertEqual(response.status_code, 302)
        survey.refresh_from_db()
        self.assertEqual(survey.status, Survey.Status.PUBLISHED)
