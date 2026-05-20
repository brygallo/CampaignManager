"""Workflow for physical campaign advertisements."""
from apps.workflows import Workflow, WorkflowChoices


class PhysicalAdWorkflow(Workflow):
    class Choices(WorkflowChoices):
        RECHAZADA = 0, "Rechazada", dict(visible=False, read_only=True)
        OFRECIDA = 1, "Ofrecida"
        APROBADA = 2, "Aprobada", dict(read_only=True)
        PENDIENTE_INSTALACION = 3, "Pendiente instalación", dict(read_only=True)
        INSTALADA = 4, "Instalada", dict(read_only=True)
        DANADA = 5, "Dañada", dict(read_only=True)
        RETIRADA = 6, "Retirada", dict(read_only=True)
