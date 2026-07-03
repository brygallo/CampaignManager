import json
import re

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.urls import reverse

from apps.surveys.forms import DynamicSurveyResponseForm, SurveyQuestionBuilderForm
from apps.surveys.models import Survey, SurveyOption, SurveyQuestion
from apps.surveys.views import SurveyRespondView


class VisibilityCycleValidationTests(TestCase):
    """SurveyQuestion.clean() must reject cycles in the visibility_question chain."""

    def setUp(self):
        self.survey = Survey.objects.create(
            title="Ciclos",
            slug="ciclos",
            status=Survey.Status.PUBLISHED,
            requires_login=False,
        )

    def test_direct_self_reference_is_rejected(self):
        question = SurveyQuestion.objects.create(
            survey=self.survey,
            text="A",
            question_type=SurveyQuestion.QuestionType.SHORT_TEXT,
            order=1,
        )
        question.visibility_question = question
        question.visibility_operator = SurveyQuestion.VisibilityOperator.EQUALS
        question.visibility_value = "x"

        with self.assertRaises(ValidationError) as ctx:
            question.full_clean()
        self.assertIn("visibility_question", ctx.exception.message_dict)

    def test_two_hop_cycle_is_rejected(self):
        a = SurveyQuestion.objects.create(
            survey=self.survey,
            text="A",
            question_type=SurveyQuestion.QuestionType.SHORT_TEXT,
            order=1,
        )
        b = SurveyQuestion.objects.create(
            survey=self.survey,
            text="B",
            question_type=SurveyQuestion.QuestionType.SHORT_TEXT,
            order=2,
            visibility_question=a,
            visibility_operator=SurveyQuestion.VisibilityOperator.EQUALS,
            visibility_value="1",
        )

        # Close the loop: A -> B -> A.
        a.visibility_question = b
        a.visibility_operator = SurveyQuestion.VisibilityOperator.EQUALS
        a.visibility_value = "2"

        with self.assertRaises(ValidationError) as ctx:
            a.full_clean()
        self.assertIn("visibility_question", ctx.exception.message_dict)

    def test_three_hop_cycle_is_rejected(self):
        a = SurveyQuestion.objects.create(
            survey=self.survey,
            text="A",
            question_type=SurveyQuestion.QuestionType.SHORT_TEXT,
            order=1,
        )
        b = SurveyQuestion.objects.create(
            survey=self.survey,
            text="B",
            question_type=SurveyQuestion.QuestionType.SHORT_TEXT,
            order=2,
            visibility_question=a,
            visibility_operator=SurveyQuestion.VisibilityOperator.EQUALS,
            visibility_value="1",
        )
        c = SurveyQuestion.objects.create(
            survey=self.survey,
            text="C",
            question_type=SurveyQuestion.QuestionType.SHORT_TEXT,
            order=3,
            visibility_question=b,
            visibility_operator=SurveyQuestion.VisibilityOperator.EQUALS,
            visibility_value="1",
        )

        # Close the loop: A -> B -> C -> A.
        a.visibility_question = c
        a.visibility_operator = SurveyQuestion.VisibilityOperator.EQUALS
        a.visibility_value = "1"

        with self.assertRaises(ValidationError) as ctx:
            a.full_clean()
        self.assertIn("visibility_question", ctx.exception.message_dict)

    def test_valid_non_cyclic_chain_is_accepted(self):
        a = SurveyQuestion.objects.create(
            survey=self.survey,
            text="A",
            question_type=SurveyQuestion.QuestionType.SHORT_TEXT,
            order=1,
        )
        b = SurveyQuestion.objects.create(
            survey=self.survey,
            text="B",
            question_type=SurveyQuestion.QuestionType.SHORT_TEXT,
            order=2,
            visibility_question=a,
            visibility_operator=SurveyQuestion.VisibilityOperator.EQUALS,
            visibility_value="1",
        )
        c = SurveyQuestion(
            survey=self.survey,
            text="C",
            question_type=SurveyQuestion.QuestionType.SHORT_TEXT,
            order=3,
            visibility_question=b,
            visibility_operator=SurveyQuestion.VisibilityOperator.EQUALS,
            visibility_value="1",
        )

        # A legitimate (non-cyclic) three-question chain must validate fine.
        c.full_clean()


class NumericVisibilityOperatorModelTests(TestCase):
    """SurveyQuestion.clean() must reject greater_than/less_than on a non-numeric source."""

    def setUp(self):
        self.survey = Survey.objects.create(
            title="Operadores numericos",
            slug="operadores-numericos",
            status=Survey.Status.PUBLISHED,
            requires_login=False,
        )

    def test_greater_than_on_non_numeric_source_is_rejected(self):
        source = SurveyQuestion.objects.create(
            survey=self.survey,
            text="Texto libre",
            question_type=SurveyQuestion.QuestionType.SHORT_TEXT,
            order=1,
        )
        dependent = SurveyQuestion(
            survey=self.survey,
            text="Depende",
            question_type=SurveyQuestion.QuestionType.SHORT_TEXT,
            order=2,
            visibility_question=source,
            visibility_operator=SurveyQuestion.VisibilityOperator.GREATER_THAN,
            visibility_value="5",
        )

        with self.assertRaises(ValidationError) as ctx:
            dependent.full_clean()
        self.assertIn("visibility_operator", ctx.exception.message_dict)

    def test_less_than_on_choice_source_is_rejected(self):
        source = SurveyQuestion.objects.create(
            survey=self.survey,
            text="Sexo",
            question_type=SurveyQuestion.QuestionType.SINGLE_CHOICE,
            order=1,
        )
        dependent = SurveyQuestion(
            survey=self.survey,
            text="Depende",
            question_type=SurveyQuestion.QuestionType.SHORT_TEXT,
            order=2,
            visibility_question=source,
            visibility_operator=SurveyQuestion.VisibilityOperator.LESS_THAN,
            visibility_value="5",
        )

        with self.assertRaises(ValidationError):
            dependent.full_clean()

    def test_greater_than_on_numeric_source_is_accepted(self):
        for question_type in (
            SurveyQuestion.QuestionType.NUMBER,
            SurveyQuestion.QuestionType.SCALE_5,
            SurveyQuestion.QuestionType.SCALE_10,
        ):
            source = SurveyQuestion.objects.create(
                survey=self.survey,
                text=f"Fuente {question_type}",
                question_type=question_type,
                order=1,
            )
            dependent = SurveyQuestion(
                survey=self.survey,
                text="Depende",
                question_type=SurveyQuestion.QuestionType.SHORT_TEXT,
                order=2,
                visibility_question=source,
                visibility_operator=SurveyQuestion.VisibilityOperator.GREATER_THAN,
                visibility_value="3",
            )
            dependent.full_clean()


class NumericVisibilityOperatorBuilderFormTests(TestCase):
    """The builder form must enforce the same numeric-source constraint as the model."""

    def setUp(self):
        self.survey = Survey.objects.create(
            title="Constructor numerico",
            slug="constructor-numerico",
            status=Survey.Status.PUBLISHED,
            requires_login=False,
        )
        self.text_source = SurveyQuestion.objects.create(
            survey=self.survey,
            text="Comentario",
            question_type=SurveyQuestion.QuestionType.SHORT_TEXT,
            order=1,
        )
        self.number_source = SurveyQuestion.objects.create(
            survey=self.survey,
            text="Edad",
            question_type=SurveyQuestion.QuestionType.NUMBER,
            order=2,
        )

    def _form_data(self, visibility_question, visibility_operator, visibility_value):
        return {
            "text": "Pregunta dependiente",
            "help_text": "",
            "question_type": SurveyQuestion.QuestionType.SHORT_TEXT,
            "visibility_question": str(visibility_question.pk),
            "visibility_operator": visibility_operator,
            "visibility_value": visibility_value,
            "option_lines": [],
        }

    def test_rejects_numeric_operator_for_non_numeric_source(self):
        form = SurveyQuestionBuilderForm(
            data=self._form_data(
                self.text_source, SurveyQuestion.VisibilityOperator.GREATER_THAN, "5"
            ),
            survey=self.survey,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("visibility_operator", form.errors)

    def test_accepts_numeric_operator_for_numeric_source(self):
        form = SurveyQuestionBuilderForm(
            data=self._form_data(
                self.number_source, SurveyQuestion.VisibilityOperator.LESS_THAN, "18"
            ),
            survey=self.survey,
        )

        self.assertTrue(form.is_valid(), form.errors)


class NumericVisibilityServerSideTests(TestCase):
    """DynamicSurveyResponseForm.is_question_visible must honor greater_than/less_than."""

    def setUp(self):
        self.survey = Survey.objects.create(
            title="Edad minima",
            slug="edad-minima",
            status=Survey.Status.PUBLISHED,
            requires_login=False,
        )
        self.age = SurveyQuestion.objects.create(
            survey=self.survey,
            text="Edad",
            question_type=SurveyQuestion.QuestionType.NUMBER,
            is_required=True,
            order=1,
        )
        self.id_number = SurveyQuestion.objects.create(
            survey=self.survey,
            text="Cedula",
            question_type=SurveyQuestion.QuestionType.SHORT_TEXT,
            is_required=True,
            order=2,
            visibility_question=self.age,
            visibility_operator=SurveyQuestion.VisibilityOperator.GREATER_THAN,
            visibility_value="17",
        )

    def test_hidden_required_question_does_not_block_submit_when_condition_false(self):
        form = DynamicSurveyResponseForm(
            data={f"question_{self.age.pk}": "10"},
            survey=self.survey,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_visible_required_question_is_enforced_when_condition_true(self):
        form = DynamicSurveyResponseForm(
            data={f"question_{self.age.pk}": "25"},
            survey=self.survey,
        )

        self.assertFalse(form.is_valid())
        self.assertIn(f"question_{self.id_number.pk}", form.errors)

    def test_less_than_operator(self):
        self.id_number.visibility_operator = SurveyQuestion.VisibilityOperator.LESS_THAN
        self.id_number.visibility_value = "18"
        self.id_number.save(update_fields=["visibility_operator", "visibility_value"])

        visible_form = DynamicSurveyResponseForm(
            data={f"question_{self.age.pk}": "10"},
            survey=self.survey,
        )
        self.assertFalse(visible_form.is_valid())
        self.assertIn(f"question_{self.id_number.pk}", visible_form.errors)

        hidden_form = DynamicSurveyResponseForm(
            data={f"question_{self.age.pk}": "25"},
            survey=self.survey,
        )
        self.assertTrue(hidden_form.is_valid(), hidden_form.errors)


class RespondPageConditionalPoliciesTests(TestCase):
    """respond.html must emit the shared [data-form-conditional-policies] JSON block."""

    def setUp(self):
        self.factory = RequestFactory()
        self.survey = Survey.objects.create(
            title="Con condiciones",
            slug="con-condiciones",
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
        self.whatsapp = SurveyOption.objects.create(question=self.parent, label="WhatsApp", order=1)
        SurveyOption.objects.create(question=self.parent, label="Correo", order=2)
        self.follow_up = SurveyQuestion.objects.create(
            survey=self.survey,
            text="Telefono",
            question_type=SurveyQuestion.QuestionType.PHONE,
            is_required=True,
            order=2,
            visibility_question=self.parent,
            visibility_operator=SurveyQuestion.VisibilityOperator.EQUALS,
            visibility_option=self.whatsapp,
        )
        self.age = SurveyQuestion.objects.create(
            survey=self.survey,
            text="Edad",
            question_type=SurveyQuestion.QuestionType.NUMBER,
            is_required=True,
            order=3,
        )
        self.adult_only = SurveyQuestion.objects.create(
            survey=self.survey,
            text="Cedula",
            question_type=SurveyQuestion.QuestionType.SHORT_TEXT,
            is_required=True,
            order=4,
            visibility_question=self.age,
            visibility_operator=SurveyQuestion.VisibilityOperator.GREATER_THAN,
            visibility_value="17",
        )

    def _get_rendered_respond_page(self):
        request = self.factory.get(reverse("surveys:respond", kwargs={"slug": self.survey.slug}))
        request.user = AnonymousUser()
        response = SurveyRespondView.as_view()(request, slug=self.survey.slug)
        response.render()
        return response.content.decode()

    def test_policies_json_block_is_present_with_expected_rules(self):
        html = self._get_rendered_respond_page()

        self.assertIn("data-form-conditional-policies", html)
        match = re.search(
            r'<script type="application/json" data-form-conditional-policies>(.*?)</script>',
            html,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        policies = json.loads(match.group(1))
        self.assertTrue(policies)

        parent_field = f"question_{self.parent.pk}"
        follow_up_field = f"question_{self.follow_up.pk}"
        age_field = f"question_{self.age.pk}"
        adult_field = f"question_{self.adult_only.pk}"

        follow_up_policy = next(p for p in policies if follow_up_field in p["targets"])
        self.assertEqual(follow_up_policy["condition"]["field"], parent_field)
        # multiple_choice sources submit a list of checked option ids, so
        # equals is expressed as list-membership ("contains") on the client.
        self.assertEqual(follow_up_policy["condition"]["operator"], "contains")
        self.assertEqual(follow_up_policy["condition"]["value"], str(self.whatsapp.pk))
        self.assertEqual(follow_up_policy["effects"], ["show", "disable"])

        adult_policy = next(p for p in policies if adult_field in p["targets"])
        self.assertEqual(adult_policy["condition"]["field"], age_field)
        self.assertEqual(adult_policy["condition"]["operator"], ">")
        self.assertEqual(adult_policy["condition"]["value"], "17")
        self.assertEqual(adult_policy["effects"], ["show", "disable"])

    def test_field_containers_target_the_right_question_cards(self):
        html = self._get_rendered_respond_page()

        self.assertIn(f'data-form-field-container="question_{self.follow_up.pk}"', html)
        self.assertIn(f'data-form-field-container="question_{self.adult_only.pk}"', html)

    def test_visibility_value_with_script_tag_is_escaped_in_policies_json(self):
        # visibility_value is a free-text field the survey editor controls;
        # a malicious/careless editor could put a script-terminating
        # sequence in it and, without escaping, break out of the
        # <script type="application/json"> block on the public respond page.
        payload = '</script><script>alert(1)</script>'
        source = SurveyQuestion.objects.create(
            survey=self.survey,
            text="Comentario",
            question_type=SurveyQuestion.QuestionType.SHORT_TEXT,
            order=5,
        )
        dependent = SurveyQuestion.objects.create(
            survey=self.survey,
            text="Depende del comentario",
            question_type=SurveyQuestion.QuestionType.SHORT_TEXT,
            order=6,
            visibility_question=source,
            visibility_operator=SurveyQuestion.VisibilityOperator.EQUALS,
            visibility_value=payload,
        )

        html = self._get_rendered_respond_page()

        self.assertNotIn(payload, html)
        self.assertNotIn("</script><script>alert(1)", html)

        match = re.search(
            r'<script type="application/json" data-form-conditional-policies>(.*?)</script>',
            html,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        block = match.group(1)
        # No literal "</script" may appear inside the JSON payload itself —
        # that's precisely what would prematurely close the tag.
        self.assertNotIn("</script", block)

        policies = json.loads(block)
        dependent_field = f"question_{dependent.pk}"
        dependent_policy = next(p for p in policies if dependent_field in p["targets"])
        # Escaping must round-trip cleanly back to the original value.
        self.assertEqual(dependent_policy["condition"]["value"], payload)
