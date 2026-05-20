from apps.workflows import Workflow, WorkflowChoices


class PoliticalAgendaRequestWorkflow(Workflow):
    class Choices(WorkflowChoices):
        CANCELED = 0, "Cancelada", dict(visible=False, read_only=True)
        PENDING = 1, "Pendiente"
        IN_REVIEW = 2, "En revisión", dict(read_only=True)
        APPROVED = 3, "Aprobada", dict(read_only=True)
        REJECTED = 4, "Rechazada", dict(read_only=True)


class PoliticalAgendaEventWorkflow(Workflow):
    class Choices(WorkflowChoices):
        CANCELED = 0, "Cancelado", dict(visible=False, read_only=True)
        DRAFT = 1, "Borrador"
        SCHEDULED = 2, "Agendado", dict(read_only=True)
        RESCHEDULED = 3, "Reprogramado", dict(read_only=True)
        DONE = 4, "Realizado", dict(read_only=True)
