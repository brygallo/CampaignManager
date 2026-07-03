"""FSM transitions for the survey lifecycle.

A mixin (``SurveyTransitions``) groups all ``@transition``-decorated methods.
The ``custom=`` dict carries UI metadata consumed by
``templates/workflows/workflow.html`` (verbose / icon / color / title / text)
and, for the publish step, a declarative ``requirements`` checklist rendered by
``workflows/includes/transition_requirements.html``.
"""
from django_fsm import transition

from apps.surveys.conditions import publication_status
from apps.surveys.workflows import SurveyWorkflow
from apps.workflows.exceptions import WorkflowException
from apps.workflows.requirements import Custom


class SurveyTransitions:
    workflow = SurveyWorkflow()

    @transition(
        field="state",
        source=workflow.DRAFT,
        target=workflow.PUBLISHED,
        permission="surveys.publish_survey",
        custom=dict(
            verbose="Publicar",
            lucide="radio",
            icon="global",
            color="success",
            title="Publicar encuesta",
            target_label="Publicada",
            text="La encuesta quedará disponible para su audiencia. ¿Continuar?",
            help_text="Corrige los puntos pendientes del formulario para poder publicar.",
            requirements=[
                Custom(
                    check=publication_status,
                    label="Formulario listo para publicar",
                    icon="list-checks",
                ),
            ],
        ),
    )
    def publish(self, **kwargs):
        """Draft -> Published. Hard-blocks when the form has open issues."""
        from apps.surveys.services import get_survey_publication_issues

        issues = get_survey_publication_issues(self)
        if issues:
            raise WorkflowException(" ".join(issues))

    @transition(
        field="state",
        source=workflow.PUBLISHED,
        target=workflow.CLOSED,
        permission="surveys.publish_survey",
        custom=dict(
            verbose="Cerrar encuesta",
            lucide="lock",
            icon="lock-2",
            color="primary",
            title="Cerrar encuesta",
            text="Se dejarán de aceptar respuestas. Podrás reabrirla si es necesario. ¿Continuar?",
        ),
    )
    def close(self, **kwargs):
        """Published -> Closed. Stops accepting responses."""

    @transition(
        field="state",
        source=workflow.CLOSED,
        target=workflow.PUBLISHED,
        permission="surveys.publish_survey",
        custom=dict(
            verbose="Reabrir",
            back_verbose="Reabrir",
            lucide="rotate-ccw",
            color="warning",
            title="Reabrir encuesta",
            text="La encuesta volverá a aceptar respuestas (según sus fechas de vigencia). ¿Continuar?",
        ),
    )
    def reopen(self, **kwargs):
        """Closed -> Published. Re-validates: questions/options may have been
        deactivated while the survey was closed."""
        from apps.surveys.services import get_survey_publication_issues

        issues = get_survey_publication_issues(self)
        if issues:
            raise WorkflowException(" ".join(issues))

    @transition(
        field="state",
        source=workflow.CLOSED,
        target=workflow.ARCHIVED,
        permission="surveys.publish_survey",
        custom=dict(
            verbose="Archivar",
            lucide="archive",
            icon="archive",
            color="secondary",
            title="Archivar encuesta",
            text="La encuesta pasará al archivo histórico. Esta acción no se puede deshacer. ¿Continuar?",
        ),
    )
    def archive(self, **kwargs):
        """Closed -> Archived (terminal)."""
