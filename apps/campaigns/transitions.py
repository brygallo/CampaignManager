"""Transiciones FSM para Campaña electoral.

Patrón sim:
  - Una clase mixin (``CampaignTransitions``) agrupa todos los
    métodos `@transition` decorados.
  - El `dict custom=` lleva los datos de UI consumidos por
    `templates/workflows/workflow.html`:
      verbose / back_verbose / icon / back_icon / color
      text         (texto descriptivo del modal de confirmación)
      title        (título del modal)
      input        (text|password — pide un único valor antes de ejecutar)
      placeholder  (placeholder del input)
      form         (dotted path a un Form Django si se requiere captura)
"""
from django_fsm import transition

from apps.campaigns.workflows import CampaignWorkflow


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
        """Borrador → Activa."""

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
        """Activa → Cerrada."""

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
        """Borrador / Activa → Anulada."""
