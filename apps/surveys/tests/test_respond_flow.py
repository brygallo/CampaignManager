from django.contrib.auth.models import AnonymousUser, Permission
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.authentication.tests.factories import UserFactory
from apps.surveys.models import Survey, SurveyQuestion, SurveyResponse
from apps.surveys.views import SurveyPublicRespondView, SurveyRespondView


def attach_session_and_messages(request):
    """Wire up session/message storage on a bare RequestFactory request.

    Views that call ``messages.error`` need this middleware plumbing, which
    RequestFactory (unlike the test client) does not provide.
    """
    SessionMiddleware(lambda r: None).process_request(request)
    request.session.save()
    MessageMiddleware(lambda r: None).process_request(request)
    return request


class SurveyRespondNonOpenAccessTests(TestCase):
    """A non-open survey (draft/closed/archived) must never expose the
    answer form to regular visitors; editors may preview it, read-only."""

    def setUp(self):
        self.factory = RequestFactory()
        self.survey = Survey.objects.create(
            title="Encuesta borrador",
            slug="encuesta-borrador",
            status=Survey.Status.DRAFT,
            requires_login=False,
        )
        SurveyQuestion.objects.create(
            survey=self.survey,
            text="Pregunta 1",
            question_type=SurveyQuestion.QuestionType.SHORT_TEXT,
            order=1,
        )

    def _get(self, user):
        request = self.factory.get(reverse("surveys:respond", kwargs={"slug": self.survey.slug}))
        request.user = user
        return SurveyRespondView.as_view()(request, slug=self.survey.slug)

    def test_regular_user_sees_unavailable_state_without_form(self):
        response = self._get(UserFactory())
        response.render()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context_data["survey_unavailable"])
        self.assertNotIn("form", response.context_data)
        self.assertNotIn(b'name="question_', response.content)

    def test_anonymous_visitor_sees_unavailable_state(self):
        # Anonymous visitors no longer reach the slug route at all (see
        # SurveyAnonymousSlugAccessTests below); the non-open preview check
        # for anonymous visitors is exercised through the public token route.
        token = self.survey.public_token()
        request = self.factory.get(reverse("surveys:respond_public", kwargs={"token": token}))
        request.user = AnonymousUser()

        response = SurveyPublicRespondView.as_view()(request, token=token)
        response.render()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context_data["survey_unavailable"])

    def test_editor_sees_preview_with_form_and_notice(self):
        editor = UserFactory()
        editor.user_permissions.add(
            Permission.objects.get(codename="change_survey", content_type__app_label="surveys")
        )

        response = self._get(editor)
        response.render()

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context_data["survey_unavailable"])
        self.assertTrue(response.context_data["is_preview"])
        self.assertIn("Vista previa", response.content.decode())

    def test_post_still_blocked_during_editor_preview(self):
        editor = UserFactory()
        editor.user_permissions.add(
            Permission.objects.get(codename="change_survey", content_type__app_label="surveys")
        )
        request = self.factory.post(
            reverse("surveys:respond", kwargs={"slug": self.survey.slug}),
            data={},
        )
        request.user = editor
        attach_session_and_messages(request)

        response = SurveyRespondView.as_view()(request, slug=self.survey.slug)
        response.render()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(SurveyResponse.objects.filter(survey=self.survey).count(), 0)


class SurveyRespondPrivacyTests(TestCase):
    """Anonymous surveys must not retain identifying request metadata."""

    def setUp(self):
        self.factory = RequestFactory()
        self.survey = Survey.objects.create(
            title="Encuesta anonima",
            slug="encuesta-anonima",
            status=Survey.Status.PUBLISHED,
            requires_login=False,
            is_anonymous=True,
        )
        self.question = SurveyQuestion.objects.create(
            survey=self.survey,
            text="Pregunta",
            question_type=SurveyQuestion.QuestionType.SHORT_TEXT,
            order=1,
        )

    def test_anonymous_survey_does_not_store_ip_or_user_agent(self):
        # Anonymous visitors now submit through the signed public token
        # route rather than the slug route (which requires login).
        token = self.survey.public_token()
        request = self.factory.post(
            reverse("surveys:respond_public", kwargs={"token": token}),
            data={f"question_{self.question.pk}": "Respuesta libre"},
        )
        request.user = AnonymousUser()
        request.META["REMOTE_ADDR"] = "10.0.0.5"
        request.META["HTTP_USER_AGENT"] = "pytest-agent/1.0"

        response = SurveyPublicRespondView.as_view()(request, token=token)

        self.assertEqual(response.status_code, 302)
        survey_response = SurveyResponse.objects.get(survey=self.survey)
        self.assertIsNone(survey_response.ip_address)
        self.assertEqual(survey_response.user_agent, "")


class SurveyRespondRespondentIdentityTests(TestCase):
    """Public, non-anonymous surveys should capture an optional name/email
    for visitors who aren't logged in."""

    def setUp(self):
        self.factory = RequestFactory()
        self.survey = Survey.objects.create(
            title="Encuesta publica",
            slug="encuesta-publica",
            status=Survey.Status.PUBLISHED,
            requires_login=False,
            is_anonymous=False,
        )
        self.question = SurveyQuestion.objects.create(
            survey=self.survey,
            text="Pregunta",
            question_type=SurveyQuestion.QuestionType.SHORT_TEXT,
            order=1,
        )

    def test_get_renders_respondent_fields_for_anonymous_visitor(self):
        token = self.survey.public_token()
        request = self.factory.get(reverse("surveys:respond_public", kwargs={"token": token}))
        request.user = AnonymousUser()

        response = SurveyPublicRespondView.as_view()(request, token=token)
        response.render()

        content = response.content.decode()
        self.assertIn('name="respondent_name"', content)
        self.assertIn('name="respondent_email"', content)

    def test_public_non_anonymous_response_captures_respondent_name_and_email(self):
        token = self.survey.public_token()
        request = self.factory.post(
            reverse("surveys:respond_public", kwargs={"token": token}),
            data={
                f"question_{self.question.pk}": "Respuesta libre",
                "respondent_name": "Maria Perez",
                "respondent_email": "maria@example.com",
            },
        )
        request.user = AnonymousUser()
        request.META["REMOTE_ADDR"] = "10.0.0.9"

        response = SurveyPublicRespondView.as_view()(request, token=token)

        self.assertEqual(response.status_code, 302)
        survey_response = SurveyResponse.objects.get(survey=self.survey)
        self.assertEqual(survey_response.respondent_name, "Maria Perez")
        self.assertEqual(survey_response.respondent_email, "maria@example.com")
        self.assertIsNotNone(survey_response.ip_address)


class SurveyRespondAuthenticatedFlowTests(TestCase):
    """Authenticated respondents keep the previous behaviour: no
    respondent_name/email prompt, ip/user_agent still stored."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = UserFactory()
        self.survey = Survey.objects.create(
            title="Encuesta autenticada",
            slug="encuesta-autenticada",
            status=Survey.Status.PUBLISHED,
            requires_login=True,
            all_users_can_respond=True,
            is_anonymous=False,
        )
        self.question = SurveyQuestion.objects.create(
            survey=self.survey,
            text="Pregunta",
            question_type=SurveyQuestion.QuestionType.SHORT_TEXT,
            order=1,
        )

    def test_get_does_not_render_respondent_fields_for_authenticated_user(self):
        request = self.factory.get(reverse("surveys:respond", kwargs={"slug": self.survey.slug}))
        request.user = self.user

        response = SurveyRespondView.as_view()(request, slug=self.survey.slug)
        response.render()

        self.assertNotIn(b'name="respondent_name"', response.content)

    def test_authenticated_user_response_stores_metadata_without_respondent_fields(self):
        request = self.factory.post(
            reverse("surveys:respond", kwargs={"slug": self.survey.slug}),
            data={f"question_{self.question.pk}": "Respuesta"},
        )
        request.user = self.user
        request.META["REMOTE_ADDR"] = "10.0.0.20"
        request.META["HTTP_USER_AGENT"] = "pytest-agent/1.0"

        response = SurveyRespondView.as_view()(request, slug=self.survey.slug)

        self.assertEqual(response.status_code, 302)
        survey_response = SurveyResponse.objects.get(survey=self.survey)
        self.assertEqual(survey_response.respondent, self.user)
        self.assertEqual(survey_response.respondent_name, "")
        self.assertEqual(survey_response.respondent_email, "")
        self.assertEqual(survey_response.ip_address, "10.0.0.20")
        self.assertEqual(survey_response.user_agent, "pytest-agent/1.0")
