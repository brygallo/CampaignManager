"""Election campaign workflow definition.

Follows the sim project pattern: each state is declared as
`(value, label, dict(custom_attrs))`, where `dict.visible=False`
hides the state from the visual stepper.
"""
from apps.workflows import Workflow, WorkflowChoices


class CampaignWorkflow(Workflow):
    class Choices(WorkflowChoices):
        CANCELED = 0, "Anulada", dict(visible=False)
        DRAFT = 1, "Borrador"
        ACTIVE = 2, "Activa"
        CLOSED = 3, "Cerrada"
