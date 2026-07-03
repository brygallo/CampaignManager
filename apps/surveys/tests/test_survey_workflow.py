from datetime import timedelta

from django.contrib.auth.models import Permission
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone
from django_fsm import TransitionNotAllowed, has_transition_perm

from apps.authentication.tests.factories import UserFactory
from apps.surveys.models import Survey, SurveyQuestion
from apps.surveys.views import SurveyBuilderView
from apps.workflows.exceptions import WorkflowException


class SurveyWorkflowTests(TestCase):
    def _build_survey(self, *, with_question=True, **overrides):
        data = {"title": "Encuesta workflow", "slug": "encuesta-workflow"}
        data.update(overrides)
        survey = Survey.objects.create(**data)
        if with_question:
            SurveyQuestion.objects.create(
                survey=survey,
                text="Comentario",
                question_type=SurveyQuestion.QuestionType.SHORT_TEXT,
                order=1,
            )
        return survey

    def _publish(self, survey):
        """Drive a survey through publish() and persist it."""
        survey.publish()
        survey.save()
        return survey

    # ----- default state / read-only -----

    def test_default_state_is_draft(self):
        survey = self._build_survey(with_question=False)
        self.assertEqual(survey.state, Survey.workflow.DRAFT)
        self.assertFalse(survey.is_state_read_only())

    def test_read_only_only_for_closed_and_archived(self):
        survey = self._build_survey()
        self.assertFalse(survey.is_state_read_only())  # draft
        self._publish(survey)
        self.assertFalse(survey.is_state_read_only())  # published
        survey.close()
        survey.save()
        self.assertTrue(survey.is_state_read_only())  # closed
        survey.archive()
        survey.save()
        self.assertTrue(survey.is_state_read_only())  # archived

    # ----- publish -----

    def test_publish_blocked_when_issues_present(self):
        survey = self._build_survey(with_question=False)
        with self.assertRaises(WorkflowException):
            survey.publish()
        # State stays DRAFT because the transition body raised before commit.
        self.assertEqual(Survey.objects.get(pk=survey.pk).state, Survey.workflow.DRAFT)

    def test_publish_succeeds_with_valid_form(self):
        survey = self._build_survey()
        self._publish(survey)
        self.assertEqual(survey.state, Survey.workflow.PUBLISHED)

    def test_is_open_reflects_dates_when_published(self):
        now = timezone.now()
        future = self._build_survey(slug="futura", starts_at=now + timedelta(days=1))
        self._publish(future)
        self.assertFalse(future.is_open)

        past = self._build_survey(slug="pasada", ends_at=now - timedelta(days=1))
        self._publish(past)
        self.assertFalse(past.is_open)

        current = self._build_survey(slug="vigente", starts_at=now - timedelta(days=1))
        self._publish(current)
        self.assertTrue(current.is_open)

    # ----- close / reopen -----

    def test_close_published_survey(self):
        survey = self._build_survey(starts_at=timezone.now() - timedelta(days=1))
        self._publish(survey)
        self.assertTrue(survey.is_open)
        survey.close()
        survey.save()
        self.assertEqual(survey.state, Survey.workflow.CLOSED)
        self.assertFalse(survey.is_open)

    def test_reopen_closed_survey(self):
        survey = self._build_survey()
        self._publish(survey)
        survey.close()
        survey.save()
        survey.reopen()
        survey.save()
        self.assertEqual(survey.state, Survey.workflow.PUBLISHED)

    def test_reopen_blocked_when_questions_deactivated(self):
        survey = self._build_survey()
        self._publish(survey)
        survey.close()
        survey.save()
        survey.questions.update(is_active=False)
        with self.assertRaises(WorkflowException):
            survey.reopen()
        self.assertEqual(Survey.objects.get(pk=survey.pk).state, Survey.workflow.CLOSED)

    # ----- archive / illegal transitions -----

    def test_archive_closed_survey(self):
        survey = self._build_survey()
        self._publish(survey)
        survey.close()
        survey.save()
        survey.archive()
        survey.save()
        self.assertEqual(survey.state, Survey.workflow.ARCHIVED)

    def test_illegal_transitions(self):
        draft = self._build_survey(slug="draft-illegal")
        with self.assertRaises(TransitionNotAllowed):
            draft.close()

        published = self._build_survey(slug="published-illegal")
        self._publish(published)
        with self.assertRaises(TransitionNotAllowed):
            published.archive()

        archived = self._build_survey(slug="archived-illegal")
        self._publish(archived)
        archived.close()
        archived.save()
        archived.archive()
        archived.save()
        with self.assertRaises(TransitionNotAllowed):
            archived.reopen()

    # ----- permissions -----

    def test_publish_permission_required(self):
        survey = self._build_survey()
        user = UserFactory()
        self.assertFalse(has_transition_perm(survey.publish, user))
        user.user_permissions.add(Permission.objects.get(codename="publish_survey"))
        user = type(user).objects.get(pk=user.pk)  # refresh cached perms
        self.assertTrue(has_transition_perm(survey.publish, user))

    # ----- transition_requirements payload -----

    def test_transition_requirements_flip_with_form_validity(self):
        survey = self._build_survey(with_question=False)
        req = survey.transition_requirements
        self.assertIsNotNone(req)
        self.assertEqual(len(req["items"]), 1)
        self.assertFalse(req["items"][0]["is_met"])
        self.assertEqual(req["pending_count"], 1)

        SurveyQuestion.objects.create(
            survey=survey,
            text="Comentario",
            question_type=SurveyQuestion.QuestionType.SHORT_TEXT,
            order=1,
        )
        req = survey.transition_requirements
        self.assertTrue(req["items"][0]["is_met"])
        self.assertEqual(req["pending_count"], 0)

    # ----- builder route guard -----

    def test_builder_publish_from_closed_survey_is_rejected(self):
        survey = self._build_survey()
        self._publish(survey)
        survey.close()
        survey.save()

        user = UserFactory()
        user.user_permissions.add(
            Permission.objects.get(codename="change_survey"),
            Permission.objects.get(codename="publish_survey"),
        )
        request = RequestFactory().post(
            reverse("surveys:builder", kwargs={"pk": survey.pk}),
            data={"action": "publish_survey"},
        )
        request.user = user
        SessionMiddleware(lambda req: None).process_request(request)
        MessageMiddleware(lambda req: None).process_request(request)

        response = SurveyBuilderView.as_view()(request, pk=survey.pk)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Survey.objects.get(pk=survey.pk).state, Survey.workflow.CLOSED)
