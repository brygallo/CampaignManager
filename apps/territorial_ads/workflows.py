"""Workflow for physical campaign advertisements."""
from apps.workflows import Workflow, WorkflowChoices


class PhysicalAdWorkflow(Workflow):
    class Choices(WorkflowChoices):
        RECHAZADA = 0, "Rechazada", dict(visible=False)
        OFRECIDA = 1, "Ofrecida"
        APROBADA = 2, "Aprobada"
        PENDIENTE_INSTALACION = 3, "Pendiente instalación"
        INSTALADA = 4, "Instalada"
        DANADA = 5, "Dañada"
        RETIRADA = 6, "Retirada"

