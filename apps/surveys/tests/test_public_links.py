"""Tests for signed public survey links (django.core.signing token route).

The token route (``surveys:respond_public``) is the anonymous entry point
for open surveys; the slug route (``surveys:respond``) always requires
login now. See ``Survey.public_token`` / ``Survey.resolve_public_token``
and ``SurveyPublicRespondView`` in ``apps/surveys/views.py``.
"""
from django.core import signing
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from apps.surveys.models import Survey, SurveyQuestion, SurveyResponse


class SurveyPublicTokenModelTests(TestCase):
    """Survey.public_token / resolve_public_token round-trip and guards."""

    def setUp(self):
        self.open_survey = Survey.objects.create(
            title="Encuesta abierta",
            slug="token-encuesta-abierta",
            state=Survey.workflow.PUBLISHED,
            requires_login=False,
        )
        self.internal_survey = Survey.objects.create(
            title="Encuesta interna",
            slug="token-encuesta-interna",
            state=Survey.workflow.PUBLISHED,
            requires_login=True,
        )

    def test_token_resolves_back_to_the_survey(self):
        token = self.open_survey.public_token()

        resolved = Survey.resolve_public_token(token)

        self.assertEqual(resolved, self.open_survey)

    def test_garbage_token_resolves_to_none(self):
        self.assertIsNone(Survey.resolve_public_token("not-a-real-token"))

    def test_tampered_token_resolves_to_none(self):
        token = self.open_survey.public_token()

        self.assertIsNone(Survey.resolve_public_token(token + "x"))

    def test_token_for_missing_survey_resolves_to_none(self):
        token = signing.dumps({"survey": self.open_survey.pk + 999}, salt="surveys.public-link")

        self.assertIsNone(Survey.resolve_public_token(token))

    def test_token_for_requires_login_survey_resolves_to_none(self):
        token = self.internal_survey.public_token()

        self.assertIsNone(Survey.resolve_public_token(token))

    def test_get_public_url_uses_token_route_when_login_not_required(self):
        self.assertIn(
            reverse("surveys:respond_public", kwargs={"token": self.open_survey.public_token()})[:20],
            self.open_survey.get_public_url(),
        )

    def test_get_public_url_falls_back_to_slug_route_when_login_required(self):
        self.assertEqual(
            self.internal_survey.get_public_url(),
            reverse("surveys:respond", kwargs={"slug": self.internal_survey.slug}),
        )


@override_settings(
    # test.py flattens django-tenants into the public schema; align the
    # session engine and route the public schema through the tenant
    # URLConf so surveys: routes resolve under testserver.
    SESSION_ENGINE="django.contrib.sessions.backends.signed_cookies",
    PUBLIC_SCHEMA_URLCONF="core.urls",
)
class SurveyPublicRespondViewTests(TestCase):
    def setUp(self):
        self.survey = Survey.objects.create(
            title="Encuesta publica token",
            slug="encuesta-publica-token",
            state=Survey.workflow.PUBLISHED,
            requires_login=False,
        )
        self.question = SurveyQuestion.objects.create(
            survey=self.survey,
            text="Pregunta",
            question_type=SurveyQuestion.QuestionType.SHORT_TEXT,
            order=1,
        )
        self.internal_survey = Survey.objects.create(
            title="Encuesta interna token",
            slug="encuesta-interna-token",
            state=Survey.workflow.PUBLISHED,
            requires_login=True,
        )

    def test_valid_token_renders_form_for_anonymous_visitor(self):
        url = reverse("surveys:respond_public", kwargs={"token": self.survey.public_token()})

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["survey_unavailable"])
        self.assertContains(response, f'name="question_{self.question.pk}"')

    def test_invalid_token_returns_404(self):
        url = reverse("surveys:respond_public", kwargs={"token": "garbage-token"})

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_token_for_requires_login_survey_returns_404(self):
        url = reverse(
            "surveys:respond_public",
            kwargs={"token": self.internal_survey.public_token()},
        )

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_anonymous_slug_access_redirects_to_login(self):
        url = reverse("surveys:respond", kwargs={"slug": self.survey.slug})

        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("authentication:login")))

    def test_anonymous_full_submit_via_token_creates_response_and_reaches_thanks(self):
        url = reverse("surveys:respond_public", kwargs={"token": self.survey.public_token()})

        response = self.client.post(
            url,
            data={f"question_{self.question.pk}": "Respuesta libre"},
        )

        self.assertEqual(response.status_code, 302)
        thanks_url = reverse("surveys:thanks", kwargs={"slug": self.survey.slug})
        self.assertEqual(response.url, thanks_url)

        survey_response = SurveyResponse.objects.get(survey=self.survey)
        self.assertIsNone(survey_response.respondent)

        thanks_response = self.client.get(thanks_url)
        self.assertEqual(thanks_response.status_code, 200)
