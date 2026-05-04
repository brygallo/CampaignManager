"""FSM transitions for territorial physical advertisements."""
from django_fsm import transition

from apps.territorial_ads.workflows import PhysicalAdWorkflow


class PhysicalAdTransitions:
    workflow = PhysicalAdWorkflow()

    @transition(
        field="state",
        source=workflow.OFRECIDA,
        target=workflow.APROBADA,
        permission="territorial_ads.approve_physicaladvertisement",
        custom=dict(
            verbose="Aprobar",
            icon="verify",
            color="success",
            title="Aprobar publicidad",
            text="¿Confirmas que este lugar ofrecido queda aprobado para instalación?",
        ),
    )
    def approve(self, user=None, **kwargs):
        self.approved_by = user

    @transition(
        field="state",
        source=workflow.APROBADA,
        target=workflow.PENDIENTE_INSTALACION,
        permission="territorial_ads.assign_physicaladvertisement",
        custom=dict(
            verbose="Asignar instalación",
            icon="user",
            color="primary",
            title="Asignar instalación",
            text="Selecciona instalador o registra el equipo responsable.",
            form="apps.territorial_ads.forms.AssignInstallationForm",
        ),
    )
    def assign_installation(self, user=None, assigned_installer=None, installer_team="", **kwargs):
        self.assigned_installer_id = assigned_installer or None
        self.installer_team = installer_team or ""
        self.assigned_by = user

    @transition(
        field="state",
        source=workflow.PENDIENTE_INSTALACION,
        target=workflow.INSTALADA,
        permission="territorial_ads.install_physicaladvertisement",
        custom=dict(
            verbose="Marcar instalada",
            icon="check-circle",
            color="success",
            title="Registrar instalación",
            text="Carga la evidencia y las coordenadas GPS reales del momento de instalación.",
            form="apps.territorial_ads.forms.InstallationEvidenceForm",
        ),
    )
    def mark_installed(
        self,
        user=None,
        installation_photo=None,
        installed_latitude=None,
        installed_longitude=None,
        installation_notes="",
        **kwargs,
    ):
        self.installation_photo = installation_photo
        self.installed_latitude = installed_latitude
        self.installed_longitude = installed_longitude
        self.installation_notes = installation_notes or ""
        self.installed_by = user

    @transition(
        field="state",
        source=workflow.INSTALADA,
        target=workflow.DANADA,
        permission="territorial_ads.report_damage_physicaladvertisement",
        custom=dict(
            verbose="Reportar daño",
            icon="information-5",
            color="warning",
            title="Reportar daño",
            text="Registra el daño detectado para control posterior.",
            form="apps.territorial_ads.forms.DamageReportForm",
        ),
    )
    def report_damage(self, user=None, damage_notes="", damage_photo=None, **kwargs):
        self.damage_notes = damage_notes or ""
        if damage_photo:
            self.damage_photo = damage_photo
        self.damage_reported_by = user

    @transition(
        field="state",
        source=[workflow.INSTALADA, workflow.DANADA],
        target=workflow.RETIRADA,
        permission="territorial_ads.retire_physicaladvertisement",
        custom=dict(
            verbose="Retirar",
            icon="cross-circle",
            color="danger",
            title="Retirar publicidad",
            text="Confirma el retiro de la publicidad física.",
            form="apps.territorial_ads.forms.RetirementForm",
        ),
    )
    def retire(self, user=None, retirement_notes="", retirement_photo=None, **kwargs):
        self.retirement_notes = retirement_notes or ""
        if retirement_photo:
            self.retirement_photo = retirement_photo
        self.retired_by = user

