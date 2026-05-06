"""FSM transitions for election campaigns.

Sim pattern:
  - A mixin class (``CampaignTransitions``) groups all decorated
    `@transition` methods.
  - The `custom=` dict carries UI metadata consumed by
    `templates/workflows/workflow.html`:
      verbose / back_verbose / icon / back_icon / color
      text         (descriptive text for the confirmation modal)
      title        (modal title)
      input        (text|password - asks for one value before execution)
      placeholder  (input placeholder)
      form         (dotted path to a Django Form when data capture is required)
"""
from django_fsm import transition

from apps.campaigns.workflows import CampaignWorkflow
from apps.workflows.exceptions import WorkflowException


class CampaignTransitions:
    workflow = CampaignWorkflow()

    @transition(
        field="state",
        source=workflow.DRAFT,
        target=workflow.ACTIVE,
        custom=dict(
            verbose="Activar campaña",
            icon="rocket",
            color="success",
            title="Activar campaña",
            text="¿Confirmas que esta campaña pasa a estado ACTIVA?",
        ),
    )
    def activate(self, **kwargs):
        """Draft -> Active."""

    @transition(
        field="state",
        source=workflow.ACTIVE,
        target=workflow.CLOSED,
        custom=dict(
            verbose="Cerrar campaña",
            icon="check-square",
            color="primary",
            title="Cerrar campaña",
            text=(
                "¿Cerrar definitivamente esta campaña? "
                "Una vez cerrada no podrá reactivarse."
            ),
        ),
    )
    def close(self, **kwargs):
        deps = self.get_active_dependencies()
        if deps["scheduled_events"] or deps["active_ads"]:
            raise WorkflowException(
                "No puedes cerrar la campaña: quedan "
                f"{deps['scheduled_events']} evento(s) AGENDADO(s) y "
                f"{deps['active_ads']} publicidad(es) activa(s)."
            )

    @transition(
        field="state",
        source=[workflow.DRAFT, workflow.ACTIVE],
        target=workflow.CANCELED,
        custom=dict(
            verbose="Anular",
            icon="cross",
            color="danger",
            title="Anular campaña",
            text=(
                "¿Estás seguro de anular esta campaña? "
                "Esta acción no se puede deshacer."
            ),
        ),
    )
    def cancel(self, **kwargs):
        deps = self.get_active_dependencies()
        if deps["scheduled_events"] or deps["active_ads"]:
            raise WorkflowException(
                "No puedes anular la campaña: cancela primero los "
                f"{deps['scheduled_events']} evento(s) AGENDADO(s) y retira las "
                f"{deps['active_ads']} publicidad(es) activa(s)."
            )
