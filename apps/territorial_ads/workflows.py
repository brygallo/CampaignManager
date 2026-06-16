from apps.workflows import Workflow, WorkflowChoices


class PhysicalAdWorkflow(Workflow):

    class Choices(WorkflowChoices):
        RECHAZADA = 0, "Rechazada", dict(visible=False, read_only=True)
        OFRECIDA = 1, "Ofrecida"
        APROBADA = 2, "Aprobada", dict(read_only=True)
        PENDIENTE_INSTALACION = 3, "Pendiente instalación", dict(read_only=True)
        INSTALADA = 4, "Instalada", dict(read_only=True)
        RETIRADA = 5, "Retirada", dict(visible=False, read_only=True)


class PhysicalAdUnitWorkflow(Workflow):
    # Per-publicidad sub-flow. Members are declared in FLOW order (not value
    # order) so the UI stepper reads naturally: Por configurar → Configurada →
    # Asignada → Instalada. Values are kept stable for existing data.
    class Choices(WorkflowChoices):
        RETIRADA = 0, "Retirada", dict(visible=False, read_only=True)
        PENDIENTE = 1, "Por configurar"
        CONFIGURADA = 5, "Configurada"
        ASIGNADA = 6, "Asignada"
        INSTALADA = 2, "Instalada", dict(read_only=True)
        DANADA = 3, "Dañada", dict(visible=False, read_only=True)
        DESCARTADA = 4, "No instalada", dict(visible=False, read_only=True)
