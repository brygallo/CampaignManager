"""Definición del workflow de Campaña electoral.

Sigue el patrón del proyecto sim: cada estado se declara como
`(value, label, dict(custom_attrs))` donde `dict.visible=False`
oculta el estado del stepper visual.
"""
from apps.workflows import Workflow, WorkflowChoices


class CampaignWorkflow(Workflow):
    class Choices(WorkflowChoices):
        CANCELED = 0, "Anulada", dict(visible=False)
        DRAFT = 1, "Borrador"
        ACTIVE = 2, "Activa"
        CLOSED = 3, "Cerrada"
