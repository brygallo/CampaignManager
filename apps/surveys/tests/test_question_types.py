import json
from decimal import Decimal

from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.authentication.tests.factories import UserFactory
from apps.surveys.forms import DynamicSurveyResponseForm, SurveyQuestionBuilderForm
from apps.surveys.models import (
    Survey,
    SurveyAnswer,
    SurveyOption,
    SurveyQuestion,
    SurveyResponse,
)
from apps.surveys.services import SurveyResultsSummary
from apps.surveys.views import SurveyRespondView


def _post_response(survey, data, user=None):
    """POST an answer submission straight to SurveyRespondView.

    The slug route always requires an authenticated user (anonymous access
    goes through the separate signed-token entry point owned elsewhere), so
    a throwaway authenticated user is used here even for
    ``requires_login=False`` surveys — that flag only controls the
    assignment/permission check, not the login-wall in ``dispatch()``.
    """
    request = RequestFactory().post(
        reverse("surveys:respond", kwargs={"slug": survey.slug}),
        data=data,
    )
    request.user = user or UserFactory()
    request.META["REMOTE_ADDR"] = "127.0.0.1"
    return SurveyRespondView.as_view()(request, slug=survey.slug)


class NpsQuestionTests(TestCase):
    def setUp(self):
        self.survey = Survey.objects.create(
            title="NPS",
            slug="nps-survey",
            status=Survey.Status.PUBLISHED,
            requires_login=False,
        )
        self.question = SurveyQuestion.objects.create(
            survey=self.survey,
            text="Que tan probable es que nos recomiendes",
            question_type=SurveyQuestion.QuestionType.NPS,
            is_required=True,
        )

    def test_nps_answer_stores_value_number(self):
        response = _post_response(self.survey, {f"question_{self.question.pk}": "9"})

        self.assertEqual(response.status_code, 302)
        answer = SurveyAnswer.objects.get(question=self.question)
        self.assertEqual(answer.value_number, Decimal("9"))
        self.assertEqual(answer.display_value, "9.00")

    def test_nps_score_is_computed_from_promoters_and_detractors(self):
        # 3 promoters (9, 9, 10), 1 passive (7), 2 detractors (0, 3) -> total 6
        for score in (9, 9, 10, 7, 0, 3):
            survey_response = SurveyResponse.objects.create(survey=self.survey)
            SurveyAnswer.objects.create(
                response=survey_response, question=self.question, value_number=score
            )

        summaries = SurveyResultsSummary(self.survey).nps_summaries

        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0]["answered"], 6)
        self.assertEqual(sum(summaries[0]["series"]), 6)
        # (3 promoters - 2 detractors) / 6 * 100 = 16.66... -> rounds to 17
        self.assertEqual(summaries[0]["nps_score"], 17)

    def test_nps_summary_is_empty_without_responses(self):
        summaries = SurveyResultsSummary(self.survey).nps_summaries

        self.assertEqual(summaries[0]["nps_score"], None)
        self.assertEqual(summaries[0]["answered"], 0)


class RankingQuestionTests(TestCase):
    def setUp(self):
        self.survey = Survey.objects.create(
            title="Ranking",
            slug="ranking-survey",
            status=Survey.Status.PUBLISHED,
            requires_login=False,
        )
        self.question = SurveyQuestion.objects.create(
            survey=self.survey,
            text="Ordena las prioridades",
            question_type=SurveyQuestion.QuestionType.RANKING,
            is_required=True,
        )
        self.first = SurveyOption.objects.create(question=self.question, label="Salud", order=1)
        self.second = SurveyOption.objects.create(question=self.question, label="Educacion", order=2)
        self.third = SurveyOption.objects.create(question=self.question, label="Empleo", order=3)

    def _form(self, raw_value):
        data = {}
        if raw_value is not None:
            data[f"question_{self.question.pk}"] = raw_value
        return DynamicSurveyResponseForm(data=data, survey=self.survey)

    def test_valid_full_order_is_normalized_and_saved(self):
        order = json.dumps([self.second.value, self.third.value, self.first.value])
        form = self._form(order)

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            json.loads(form.cleaned_data[f"question_{self.question.pk}"]),
            [self.second.value, self.third.value, self.first.value],
        )

    def test_incomplete_order_is_rejected(self):
        order = json.dumps([self.first.value, self.second.value])
        form = self._form(order)

        self.assertFalse(form.is_valid())
        self.assertIn(f"question_{self.question.pk}", form.errors)

    def test_tampered_order_with_unknown_value_is_rejected(self):
        order = json.dumps([self.first.value, self.second.value, "not-a-real-option"])
        form = self._form(order)

        self.assertFalse(form.is_valid())
        self.assertIn(f"question_{self.question.pk}", form.errors)

    def test_required_ranking_without_value_is_rejected(self):
        form = self._form(None)

        self.assertFalse(form.is_valid())
        self.assertIn(f"question_{self.question.pk}", form.errors)

    def test_ranking_round_trip_saves_and_displays_positions(self):
        order = [self.second.value, self.first.value, self.third.value]

        response = _post_response(
            self.survey, {f"question_{self.question.pk}": json.dumps(order)}
        )

        self.assertEqual(response.status_code, 302)
        answer = SurveyAnswer.objects.get(question=self.question)
        self.assertEqual(json.loads(answer.value_text), order)
        self.assertEqual(
            answer.display_value,
            f"1. {self.second.label}, 2. {self.first.label}, 3. {self.third.label}",
        )

    def test_ranking_summary_computes_average_position(self):
        response_a = SurveyResponse.objects.create(survey=self.survey)
        SurveyAnswer.objects.create(
            response=response_a,
            question=self.question,
            value_text=json.dumps([self.first.value, self.second.value, self.third.value]),
        )
        response_b = SurveyResponse.objects.create(survey=self.survey)
        SurveyAnswer.objects.create(
            response=response_b,
            question=self.question,
            value_text=json.dumps([self.second.value, self.first.value, self.third.value]),
        )

        summaries = SurveyResultsSummary(self.survey).ranking_summaries

        self.assertEqual(len(summaries), 1)
        rows_by_label = {row["label"]: row for row in summaries[0]["rows"]}
        self.assertEqual(rows_by_label[self.first.label]["avg_position"], 1.5)
        self.assertEqual(rows_by_label[self.third.label]["avg_position"], 3.0)
        self.assertEqual(summaries[0]["answered"], 2)


class AllowOtherQuestionTests(TestCase):
    def setUp(self):
        self.survey = Survey.objects.create(
            title="Otro",
            slug="otro-survey",
            status=Survey.Status.PUBLISHED,
            requires_login=False,
        )
        self.question = SurveyQuestion.objects.create(
            survey=self.survey,
            text="Canal preferido",
            question_type=SurveyQuestion.QuestionType.SINGLE_CHOICE,
            is_required=True,
            allow_other=True,
        )
        self.option = SurveyOption.objects.create(question=self.question, label="WhatsApp")

    def test_other_selection_requires_text(self):
        form = DynamicSurveyResponseForm(
            data={f"question_{self.question.pk}": "other"},
            survey=self.survey,
        )

        self.assertFalse(form.is_valid())
        self.assertIn(f"question_{self.question.pk}_other", form.errors)

    def test_regular_option_does_not_require_other_text(self):
        form = DynamicSurveyResponseForm(
            data={f"question_{self.question.pk}": str(self.option.pk)},
            survey=self.survey,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_other_selection_saves_text_and_appears_in_summary(self):
        response = _post_response(
            self.survey,
            {
                f"question_{self.question.pk}": "other",
                f"question_{self.question.pk}_other": "Redes sociales",
            },
        )

        self.assertEqual(response.status_code, 302)
        answer = SurveyAnswer.objects.get(question=self.question)
        self.assertEqual(answer.value_text, "Redes sociales")
        self.assertEqual(answer.selected_options.count(), 0)
        self.assertEqual(answer.display_value, "Otro: Redes sociales")

        summaries = SurveyResultsSummary(self.survey).choice_summaries
        rows = {row["label"]: row["count"] for row in summaries[0]["rows"]}
        self.assertEqual(rows.get("Otro"), 1)


class SelectionLimitsTests(TestCase):
    def setUp(self):
        self.survey = Survey.objects.create(
            title="Limites",
            slug="limites-survey",
            status=Survey.Status.PUBLISHED,
            requires_login=False,
        )
        self.question = SurveyQuestion.objects.create(
            survey=self.survey,
            text="Elige hasta 2",
            question_type=SurveyQuestion.QuestionType.MULTIPLE_CHOICE,
            is_required=True,
            min_selections=1,
            max_selections=2,
        )
        self.option_a = SurveyOption.objects.create(question=self.question, label="A")
        self.option_b = SurveyOption.objects.create(question=self.question, label="B")
        self.option_c = SurveyOption.objects.create(question=self.question, label="C")

    def test_exceeding_max_selections_is_rejected(self):
        form = DynamicSurveyResponseForm(
            data={
                f"question_{self.question.pk}": [
                    str(self.option_a.pk),
                    str(self.option_b.pk),
                    str(self.option_c.pk),
                ]
            },
            survey=self.survey,
        )

        self.assertFalse(form.is_valid())
        self.assertIn(f"question_{self.question.pk}", form.errors)

    def test_below_min_selections_is_rejected(self):
        form = DynamicSurveyResponseForm(
            data={f"question_{self.question.pk}": []},
            survey=self.survey,
        )

        self.assertFalse(form.is_valid())
        self.assertIn(f"question_{self.question.pk}", form.errors)

    def test_within_limits_is_accepted(self):
        form = DynamicSurveyResponseForm(
            data={f"question_{self.question.pk}": [str(self.option_a.pk), str(self.option_b.pk)]},
            survey=self.survey,
        )

        self.assertTrue(form.is_valid(), form.errors)


class NumberRangeTests(TestCase):
    def setUp(self):
        self.survey = Survey.objects.create(
            title="Rango",
            slug="rango-survey",
            status=Survey.Status.PUBLISHED,
            requires_login=False,
        )
        self.question = SurveyQuestion.objects.create(
            survey=self.survey,
            text="Edad",
            question_type=SurveyQuestion.QuestionType.NUMBER,
            min_value=Decimal("18"),
            max_value=Decimal("99"),
        )

    def test_value_below_minimum_is_rejected(self):
        form = DynamicSurveyResponseForm(
            data={f"question_{self.question.pk}": "10"},
            survey=self.survey,
        )

        self.assertFalse(form.is_valid())
        self.assertIn(f"question_{self.question.pk}", form.errors)

    def test_value_above_maximum_is_rejected(self):
        form = DynamicSurveyResponseForm(
            data={f"question_{self.question.pk}": "150"},
            survey=self.survey,
        )

        self.assertFalse(form.is_valid())
        self.assertIn(f"question_{self.question.pk}", form.errors)

    def test_value_within_range_is_accepted(self):
        form = DynamicSurveyResponseForm(
            data={f"question_{self.question.pk}": "45"},
            survey=self.survey,
        )

        self.assertTrue(form.is_valid(), form.errors)


class SurveyQuestionModelConstraintTests(TestCase):
    def setUp(self):
        self.survey = Survey.objects.create(
            title="Modelo",
            slug="modelo-survey",
            status=Survey.Status.DRAFT,
        )

    def test_allow_other_on_non_choice_type_is_rejected(self):
        question = SurveyQuestion(
            survey=self.survey,
            text="Cuantos anios tienes",
            question_type=SurveyQuestion.QuestionType.NUMBER,
            allow_other=True,
        )

        with self.assertRaises(Exception):
            question.full_clean()

    def test_min_value_on_non_number_type_is_rejected(self):
        question = SurveyQuestion(
            survey=self.survey,
            text="Comentario",
            question_type=SurveyQuestion.QuestionType.SHORT_TEXT,
            min_value=Decimal("1"),
        )

        with self.assertRaises(Exception):
            question.full_clean()


class SurveyQuestionBuilderFormConstraintTests(TestCase):
    def setUp(self):
        self.survey = Survey.objects.create(
            title="Constructor tipos",
            slug="constructor-tipos-survey",
            status=Survey.Status.DRAFT,
        )

    def _data(self, **overrides):
        data = {
            "text": "Pregunta",
            "help_text": "",
            "question_type": SurveyQuestion.QuestionType.SHORT_TEXT,
            "visibility_operator": SurveyQuestion.VisibilityOperator.ALWAYS,
            "visibility_value": "",
        }
        data.update(overrides)
        return data

    def test_min_selections_on_non_multiple_choice_is_rejected(self):
        form = SurveyQuestionBuilderForm(
            data=self._data(min_selections="1"),
            survey=self.survey,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("min_selections", form.errors)

    def test_min_value_on_non_number_is_rejected(self):
        form = SurveyQuestionBuilderForm(
            data=self._data(min_value="1"),
            survey=self.survey,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("min_value", form.errors)

    def test_allow_other_on_number_is_rejected(self):
        form = SurveyQuestionBuilderForm(
            data=self._data(question_type=SurveyQuestion.QuestionType.NUMBER, allow_other="on"),
            survey=self.survey,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("allow_other", form.errors)

    def test_ranking_requires_at_least_two_options(self):
        form = SurveyQuestionBuilderForm(
            data=self._data(
                question_type=SurveyQuestion.QuestionType.RANKING,
                option_lines=["Solo una"],
            ),
            survey=self.survey,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("option_lines", form.errors)

    def test_valid_multiple_choice_with_selection_limits_saves(self):
        form = SurveyQuestionBuilderForm(
            data=self._data(
                question_type=SurveyQuestion.QuestionType.MULTIPLE_CHOICE,
                option_lines=["A", "B", "C"],
                min_selections="1",
                max_selections="2",
            ),
            survey=self.survey,
        )

        self.assertTrue(form.is_valid(), form.errors)
        question = form.save()
        self.assertEqual(question.min_selections, 1)
        self.assertEqual(question.max_selections, 2)

    def test_min_selections_above_max_is_rejected(self):
        form = SurveyQuestionBuilderForm(
            data=self._data(
                question_type=SurveyQuestion.QuestionType.MULTIPLE_CHOICE,
                option_lines=["A", "B", "C"],
                min_selections="3",
                max_selections="1",
            ),
            survey=self.survey,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("max_selections", form.errors)
