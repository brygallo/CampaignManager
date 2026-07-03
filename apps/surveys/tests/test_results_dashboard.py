"""Tests for the survey results dashboard (pagination, live data, map, filters)."""
import json
from datetime import timedelta

from django.contrib.auth.models import AnonymousUser, Permission
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.utils import timezone

from apps.authentication.tests.factories import UserFactory
from apps.surveys.models import (
    Survey,
    SurveyAnswer,
    SurveyOption,
    SurveyQuestion,
    SurveyResponse,
)
from apps.surveys.reports import filtered_survey_responses
from apps.surveys.views import (
    SurveyResultsDataView,
    SurveyResultsMapDataView,
    SurveyResultsView,
)


def _grant(user, *codenames):
    for codename in codenames:
        user.user_permissions.add(Permission.objects.get(codename=codename))


class ResultsDashboardTestBase(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.survey = Survey.objects.create(
            title="Diagnóstico",
            slug="diagnostico-dashboard",
            status=Survey.Status.PUBLISHED,
        )
        self.text_question = SurveyQuestion.objects.create(
            survey=self.survey,
            text="Comentario",
            question_type=SurveyQuestion.QuestionType.SHORT_TEXT,
            order=1,
        )
        self.choice_question = SurveyQuestion.objects.create(
            survey=self.survey,
            text="Preferencia",
            question_type=SurveyQuestion.QuestionType.SINGLE_CHOICE,
            order=2,
        )
        self.option_a = SurveyOption.objects.create(
            question=self.choice_question, label="Opción A", order=1
        )
        self.option_b = SurveyOption.objects.create(
            question=self.choice_question, label="Opción B", order=2
        )
        self.location_question = SurveyQuestion.objects.create(
            survey=self.survey,
            text="Ubicación",
            question_type=SurveyQuestion.QuestionType.LOCATION,
            order=3,
        )
        self.viewer = UserFactory()
        _grant(self.viewer, "view_survey_results")

    def _make_response(self, *, text="hola", submitted_at=None, lat=None, lng=None):
        response = SurveyResponse.objects.create(survey=self.survey)
        SurveyAnswer.objects.create(
            response=response, question=self.text_question, value_text=text
        )
        answer = SurveyAnswer.objects.create(
            response=response, question=self.choice_question
        )
        answer.selected_options.set([self.option_a])
        if lat is not None and lng is not None:
            SurveyAnswer.objects.create(
                response=response,
                question=self.location_question,
                latitude=lat,
                longitude=lng,
                value_text=f"{lat}, {lng}",
            )
        if submitted_at is not None:
            SurveyResponse.objects.filter(pk=response.pk).update(
                submitted_at=submitted_at
            )
        return response

    def _get(self, path, user, **params):
        request = self.factory.get(path, params)
        request.user = user
        return request


class PaginationTests(ResultsDashboardTestBase):
    def test_responses_are_paginated_and_preserve_filters(self):
        for _ in range(30):
            self._make_response(text="hola")

        request = self._get("/results/", self.viewer, q="hola", page="2")
        response = SurveyResultsView.as_view()(request, pk=self.survey.pk)

        self.assertEqual(response.status_code, 200)
        context = response.context_data
        page_obj = context["page_obj"]
        self.assertEqual(page_obj.number, 2)
        self.assertEqual(page_obj.paginator.per_page, 25)
        self.assertEqual(len(page_obj.object_list), 5)
        self.assertIn("q=hola", context["filters_querystring"])
        self.assertNotIn("page", context["filters_querystring"])


class ResultsDataViewTests(ResultsDashboardTestBase):
    def test_returns_payload_with_choice_and_trend(self):
        self._make_response(text="hola")
        self._make_response(text="hola")

        request = self._get("/results/data/", self.viewer)
        response = SurveyResultsDataView.as_view()(request, pk=self.survey.pk)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["total_responses"], 2)
        self.assertEqual(len(data["trend"]["series"]), 30)
        choice = next(
            row
            for row in data["choice_summaries"]
            if row["question_id"] == self.choice_question.pk
        )
        self.assertEqual(choice["categories"], ["Opción A", "Opción B"])
        self.assertEqual(choice["series"], [2, 0])

    def test_requires_view_permission(self):
        request = self._get("/results/data/", UserFactory())
        with self.assertRaises(PermissionDenied):
            SurveyResultsDataView.as_view()(request, pk=self.survey.pk)


class ResultsMapDataViewTests(ResultsDashboardTestBase):
    def test_returns_only_location_coordinates(self):
        self._make_response(text="hola", lat="-2.100000", lng="-79.100000")
        self._make_response(text="hola")  # no location answer

        request = self._get("/results/map/", self.viewer)
        response = SurveyResultsMapDataView.as_view()(request, pk=self.survey.pk)

        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data["count"], 1)
        self.assertEqual(len(data["points"]), 1)
        point = data["points"][0]
        self.assertAlmostEqual(point["lat"], -2.1)
        self.assertAlmostEqual(point["lng"], -79.1)
        self.assertEqual(point["question"], "Ubicación")

    def test_requires_view_permission(self):
        request = self._get("/results/map/", UserFactory())
        with self.assertRaises(PermissionDenied):
            SurveyResultsMapDataView.as_view()(request, pk=self.survey.pk)

    def test_anonymous_is_redirected(self):
        request = self._get("/results/map/", AnonymousUser())
        response = SurveyResultsMapDataView.as_view()(request, pk=self.survey.pk)
        self.assertEqual(response.status_code, 302)


class FilteredSurveyResponsesTests(ResultsDashboardTestBase):
    def test_date_and_search_filters(self):
        now = timezone.now()
        recent = self._make_response(text="reciente", submitted_at=now)
        old = self._make_response(
            text="antiguo", submitted_at=now - timedelta(days=10)
        )

        by_date = filtered_survey_responses(
            self.survey,
            {"date_from": (now - timedelta(days=2)).date().isoformat()},
        )
        self.assertIn(recent, list(by_date))
        self.assertNotIn(old, list(by_date))

        by_search = filtered_survey_responses(self.survey, {"q": "antiguo"})
        self.assertIn(old, list(by_search))
        self.assertNotIn(recent, list(by_search))
