"""Survey lifecycle workflow definition.

Follows the project pattern (see ``apps/campaigns/workflows.py``): each state
is declared as ``(value, label, dict(custom_attrs))`` where ``read_only=True``
forbids edits through the standard update view. Values follow flow order 1..4
so the visual stepper and ``_next_forward_transition`` resolve the natural
lifecycle. There is no ``0`` state: surveys have no cancel/reject terminal.
"""
from apps.workflows import Workflow, WorkflowChoices


class SurveyWorkflow(Workflow):
    class Choices(WorkflowChoices):
        DRAFT = 1, "Borrador"
        PUBLISHED = 2, "Publicada"
        CLOSED = 3, "Cerrada", dict(read_only=True)
        ARCHIVED = 4, "Archivada", dict(read_only=True)
