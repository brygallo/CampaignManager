from apps.workflows import Workflow, WorkflowChoices


class PoliticalAgendaRequestWorkflow(Workflow):
    class Choices(WorkflowChoices):
        CANCELED = 0, "Cancelada", dict(visible=False)
        PENDING = 1, "Pendiente"
        IN_REVIEW = 2, "En revisión"
        APPROVED = 3, "Aprobada"
        REJECTED = 4, "Rechazada"


class PoliticalAgendaEventWorkflow(Workflow):
    class Choices(WorkflowChoices):
        CANCELED = 0, "Cancelado", dict(visible=False)
        DRAFT = 1, "Borrador"
        SCHEDULED = 2, "Agendado"
        RESCHEDULED = 3, "Reprogramado"
        DONE = 4, "Realizado"
