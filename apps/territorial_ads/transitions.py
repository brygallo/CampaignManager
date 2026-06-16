"""FSM transitions for territorial advertising.

Two workflows live here:

- ``PhysicalAdTransitions`` — the REQUEST (solicitud): a place is offered,
  approved (materializing one ``PhysicalAdvertisementUnit`` per physical
  unit) and an installer is assigned. Its install/retire states are kept in
  sync automatically from the unit states.
- ``PhysicalAdUnitTransitions`` — each physical UNIT (valla/lona/sticker):
  installation evidence (photo + GPS + notes), damage reports, repair and
  retirement happen per unit.
"""
from django.utils import timezone
from django_fsm import transition

from apps.territorial_ads.conditions import (
    publicidades_decided_status,
    publicidades_installer_status,
    unit_request_approved,
    unit_request_in_installation,
)
from apps.territorial_ads.constants import (
    TRANSITION_APPROVE,
    TRANSITION_ASSIGN_INSTALLATION,
)
from apps.territorial_ads.services import PhysicalAdService
from apps.territorial_ads.workflows import PhysicalAdUnitWorkflow, PhysicalAdWorkflow
from apps.workflows.requirements import Custom, RequirementsValidator


class PhysicalAdTransitions:
    workflow = PhysicalAdWorkflow()

    @transition(
        field="state",
        source=workflow.OFRECIDA,
        target=workflow.APROBADA,
        permission="territorial_ads.approve_physicaladvertisement",
        custom=dict(
            verbose="Aprobar solicitud",
            icon="verify",
            lucide="check",
            color="success",
            title="Aprobar solicitud",
            target_label="Aprobada",
            text=(
                "Confirma la aprobación de la solicitud. Las publicidades ya "
                "existen y se configuran (tamaño e indicaciones) una por una "
                "desde cada tarjeta. ¿Continuar?"
            ),
            help_text=(
                "No puedes aprobar hasta que cada publicidad esté configurada "
                "o marcada como 'No se instalará'."
            ),
            # Hard requirement (also shown as a checklist on the detail page):
            # every publicidad must be decided before the request is approved.
            requirements=[
                Custom(
                    check=publicidades_decided_status,
                    label="Publicidades configuradas o descartadas",
                    icon="layout-grid",
                ),
            ],
        ),
    )
    def approve(self, user=None, **kwargs):
        # Units are materialized when the request is offered/edited and are
        # configured per publicidad (size/instructions) from each card, so
        # approval is now just a confirmation that advances the state — but
        # only once every publicidad has been configured or discarded.
        RequirementsValidator.run(self, TRANSITION_APPROVE)
        self.approved_by = user
        self.approved_at = timezone.now()

    @transition(
        field="state",
        source=workflow.OFRECIDA,
        target=workflow.RECHAZADA,
        permission="territorial_ads.reject_physicaladvertisement",
        custom=dict(
            verbose="Rechazar",
            icon="cross-circle",
            lucide="x",
            color="danger",
            title="Rechazar solicitud",
            text="Indica el motivo por el cual se rechaza esta oferta.",
            form="apps.territorial_ads.forms.RejectPhysicalAdForm",
        ),
    )
    def reject(self, user=None, rejection_reason="", **kwargs):
        self.rejection_reason = rejection_reason or ""
        self.rejected_by = user
        self.rejected_at = timezone.now()

    @transition(
        field="state",
        source=workflow.APROBADA,
        target=workflow.OFRECIDA,
        permission="territorial_ads.approve_physicaladvertisement",
        custom=dict(
            verbose="Devolver a ofrecida",
            back_verbose="Devolver a ofrecida",
            icon="arrow-left",
            lucide="arrow-left",
            color="warning",
            title="Devolver a ofrecida",
            text=(
                "La aprobación se anulará para corregir datos y volver a "
                "aprobar. Las publicidades se conservan. ¿Continuar?"
            ),
        ),
    )
    def revert_to_offered(self, user=None, **kwargs):
        # Units persist across the lifecycle now; reverting only undoes the
        # approval stamp so the request can be edited and re-approved.
        self.approved_by = None
        self.approved_at = None

    @transition(
        field="state",
        source=workflow.APROBADA,
        target=workflow.PENDIENTE_INSTALACION,
        permission="territorial_ads.assign_physicaladvertisement",
        custom=dict(
            verbose="Enviar a instalación",
            icon="user",
            lucide="send",
            color="primary",
            title="Enviar a instalación",
            text=(
                "La solicitud pasa a instalación. Cada publicidad debe tener un "
                "instalador asignado antes de continuar. ¿Continuar?"
            ),
            help_text=(
                "No puedes enviar a instalación hasta que cada publicidad tenga "
                "un instalador (persona o equipo) asignado."
            ),
            # Hard requirement (also shown as a checklist on the detail page):
            # every publicidad to install must have an installer assigned.
            requirements=[
                Custom(
                    check=publicidades_installer_status,
                    label="Publicidades con instalador asignado",
                    icon="user-check",
                ),
            ],
        ),
    )
    def assign_installation(self, user=None, **kwargs):
        # Installer/team are assigned per unit; this transition only moves the
        # request into the installation stage, and only once every publicidad
        # to install already has an installer assigned.
        RequirementsValidator.run(self, TRANSITION_ASSIGN_INSTALLATION)

    # --- Auto transitions driven by unit states (hidden from the UI) ---

    @transition(
        field="state",
        source=workflow.PENDIENTE_INSTALACION,
        target=workflow.INSTALADA,
        permission="territorial_ads.install_physicaladvertisement",
        custom=dict(hidden=True, verbose="Marcar instalada"),
    )
    def mark_installed(self, user=None, **kwargs):
        """Auto-fired when the last pending unit registers its evidence."""
        self.installed_by = user
        self.installed_at = timezone.now()

    @transition(
        field="state",
        source=workflow.INSTALADA,
        target=workflow.PENDIENTE_INSTALACION,
        permission="territorial_ads.install_physicaladvertisement",
        custom=dict(hidden=True, verbose="Volver a pendiente"),
    )
    def revert_to_pending(self, user=None, **kwargs):
        """Auto-fired when an installed unit is sent back to pending."""
        self.installed_at = None
        self.installed_by = None

    @transition(
        field="state",
        source=workflow.INSTALADA,
        target=workflow.RETIRADA,
        permission="territorial_ads.retire_physicaladvertisement",
        custom=dict(hidden=True, verbose="Cerrar por retiro"),
    )
    def retire_request(self, user=None, **kwargs):
        """Auto-fired when the last active unit is retired."""
        self.retired_by = user
        self.retired_at = timezone.now()

    # --- User-facing bulk action ---

    @transition(
        field="state",
        source=workflow.INSTALADA,
        target=workflow.RETIRADA,
        permission="territorial_ads.retire_physicaladvertisement",
        custom=dict(
            verbose="Retirar todas las publicidades",
            icon="cross-circle",
            lucide="archive",
            color="danger",
            title="Retirar todas las publicidades",
            text=(
                "Se retirarán TODAS las publicidades activas de esta "
                "solicitud y la solicitud quedará Retirada. ¿Confirmas?"
            ),
        ),
    )
    def retire(self, user=None, **kwargs):
        # Retire every unit without per-unit request sync; this transition's
        # own target (RETIRADA) sets the request state once.
        PhysicalAdService.retire_all_units(self, user=user)
        self.retired_by = user
        self.retired_at = timezone.now()

    @transition(
        field="state",
        source=[
            workflow.APROBADA,
            workflow.PENDIENTE_INSTALACION,
            workflow.INSTALADA,
        ],
        # ``target=None``: contact typos can be fixed at any point of the
        # flow without reopening the (otherwise read-only) record.
        target=None,
        permission="territorial_ads.change_physicaladvertisement",
        custom=dict(
            verbose="Corregir contacto",
            icon="user",
            lucide="user",
            color="light",
            title="Corregir datos de contacto",
            text="Actualiza el contacto o la referencia sin alterar el avance del flujo.",
            form="apps.territorial_ads.forms.ContactUpdateForm",
        ),
    )
    def update_contact_info(
        self, user=None, owner_name=None, owner_phone=None, reference=None, **kwargs
    ):
        if owner_name is not None:
            self.owner_name = owner_name
        if owner_phone is not None:
            self.owner_phone = owner_phone
        if reference is not None:
            self.reference = reference

    @transition(
        field="state",
        source=[
            workflow.APROBADA,
            workflow.PENDIENTE_INSTALACION,
            workflow.INSTALADA,
        ],
        # ``target=None``: adding a publicidad doesn't change the request
        # state. The form (AddAdvertisementForm) only validates; the new
        # units are created here from the POST kwargs.
        target=None,
        permission="territorial_ads.approve_physicaladvertisement",
        custom=dict(
            verbose="Agregar publicidad",
            icon="plus",
            lucide="plus",
            color="light-primary",
            title="Agregar publicidad",
            text="Agrega una publicidad que no estaba en la oferta original.",
            form="apps.territorial_ads.forms.AddAdvertisementForm",
        ),
    )
    def add_advertisement(
        self,
        user=None,
        advertisement_type=None,
        quantity=1,
        size=None,
        instructions="",
        assigned_installer=None,
        installer_team="",
        **kwargs,
    ):
        PhysicalAdService.add_advertisement(
            self,
            user=user,
            advertisement_type=advertisement_type,
            quantity=quantity,
            size=size,
            instructions=instructions,
            assigned_installer=assigned_installer,
            installer_team=installer_team,
        )


class PhysicalAdUnitTransitions:
    workflow = PhysicalAdUnitWorkflow()

    def _sync_request(self, user, my_target_state):
        self.item.advertisement.sync_state_with_units(
            user=user, pending_unit=self, pending_state=my_target_state
        )

    @transition(
        field="state",
        source=[workflow.PENDIENTE, workflow.CONFIGURADA],
        target=workflow.CONFIGURADA,
        permission="territorial_ads.approve_physicaladvertisement",
        custom=dict(
            verbose="Configurar",
            icon="settings-2",
            lucide="settings-2",
            color="light-primary",
            title="Configurar publicidad",
            text="Elige el tamaño e indicaciones de esta publicidad.",
            form="apps.territorial_ads.forms.UnitConfigForm",
        ),
    )
    def configure(self, user=None, size=None, installation_instructions="", **kwargs):
        # First step of the sub-flow: choosing the size configures the publicidad.
        # Re-runnable from CONFIGURADA to edit it before an installer is assigned.
        self.size_id = (
            int(getattr(size, "pk", size)) if size not in (None, "") else None
        )
        self.installation_instructions = installation_instructions or ""

    @transition(
        field="state",
        source=workflow.ASIGNADA,
        target=workflow.INSTALADA,
        permission="territorial_ads.install_physicaladvertisement",
        # An installer must already be assigned (source=ASIGNADA) and the parent
        # request must have been sent to installation.
        conditions=[unit_request_in_installation],
        custom=dict(
            verbose="Marcar instalada",
            icon="check-circle",
            lucide="camera",
            color="success",
            title="Registrar instalación",
            text=(
                "Sube la foto de evidencia y la ubicación GPS real de esta "
                "publicidad instalada."
            ),
            form="apps.territorial_ads.forms.UnitInstallForm",
        ),
    )
    def mark_installed(
        self,
        user=None,
        photo=None,
        latitude=None,
        longitude=None,
        notes="",
        **kwargs,
    ):
        if photo:
            self.photo = photo
        self.latitude = latitude or None
        self.longitude = longitude or None
        self.notes = notes or ""
        self.installed_by = user
        self.installed_at = timezone.now()
        self._sync_request(user, self.workflow.INSTALADA)

    @transition(
        field="state",
        source=workflow.INSTALADA,
        target=workflow.ASIGNADA,
        permission="territorial_ads.install_physicaladvertisement",
        custom=dict(
            verbose="Volver a asignada",
            back_verbose="Volver a asignada",
            icon="arrow-left",
            lucide="arrow-left",
            color="warning",
            title="Volver a asignada",
            text=(
                "La foto, la ubicación y las notas de esta publicidad se "
                "limpiarán para registrar la instalación de nuevo. El instalador "
                "asignado se conserva. ¿Continuar?"
            ),
        ),
    )
    def revert_to_pending(self, user=None, **kwargs):
        self.photo = None
        self.latitude = None
        self.longitude = None
        self.notes = ""
        self.installed_at = None
        self.installed_by = None
        self._sync_request(user, self.workflow.ASIGNADA)

    @transition(
        field="state",
        source=workflow.INSTALADA,
        target=workflow.DANADA,
        permission="territorial_ads.report_damage_physicaladvertisement",
        custom=dict(
            verbose="Reportar daño",
            icon="information-5",
            lucide="alert-triangle",
            color="warning",
            title="Reportar daño",
            text="Registra el daño detectado en esta publicidad.",
            form="apps.territorial_ads.forms.DamageReportForm",
        ),
    )
    def report_damage(self, user=None, damage_notes="", damage_photo=None, **kwargs):
        self.damage_notes = damage_notes or ""
        if damage_photo:
            self.damage_photo = damage_photo
        self.damage_reported_by = user
        self.damage_reported_at = timezone.now()

    @transition(
        field="state",
        source=workflow.DANADA,
        target=workflow.INSTALADA,
        permission="territorial_ads.report_damage_physicaladvertisement",
        custom=dict(
            verbose="Marcar reparada",
            back_verbose="Marcar reparada",
            icon="check-circle",
            lucide="wrench",
            color="success",
            title="Marcar como reparada",
            text=(
                "La publicidad vuelve al estado Instalada. El reporte de "
                "daño queda registrado. ¿Continuar?"
            ),
        ),
    )
    def mark_repaired(self, user=None, **kwargs):
        # Damage fields are kept on purpose: they document the incident
        # even after the unit is repaired.
        pass

    @transition(
        field="state",
        source=[workflow.INSTALADA, workflow.DANADA],
        target=workflow.RETIRADA,
        permission="territorial_ads.retire_physicaladvertisement",
        custom=dict(
            verbose="Retirar",
            icon="cross-circle",
            lucide="archive",
            color="danger",
            title="Retirar publicidad",
            text="¿Confirmas el retiro de esta publicidad?",
        ),
    )
    def retire(self, user=None, _skip_sync=False, **kwargs):
        self.retired_by = user
        self.retired_at = timezone.now()
        if not _skip_sync:
            self._sync_request(user, self.workflow.RETIRADA)

    @transition(
        field="state",
        source=[workflow.PENDIENTE, workflow.CONFIGURADA, workflow.ASIGNADA],
        target=workflow.DESCARTADA,
        permission="territorial_ads.install_physicaladvertisement",
        custom=dict(
            verbose="No se instalará",
            icon="slash",
            lucide="slash",
            color="secondary",
            title="Marcar como no instalada",
            text=(
                "Esta publicidad no se instalará (no se necesita / no se "
                "pudo). No aparecerá en el mapa y no impedirá cerrar la "
                "solicitud. Puedes indicar el motivo."
            ),
            form="apps.territorial_ads.forms.DiscardUnitForm",
        ),
    )
    def discard(self, user=None, notes="", **kwargs):
        if notes:
            self.notes = notes
        # Resolving this unit may let the request reach Instalada (e.g. the
        # other units are already installed).
        self._sync_request(user, self.workflow.DESCARTADA)

    @transition(
        field="state",
        source=workflow.DESCARTADA,
        target=workflow.PENDIENTE,
        permission="territorial_ads.install_physicaladvertisement",
        custom=dict(
            verbose="Reactivar",
            back_verbose="Reactivar",
            icon="rotate-ccw",
            lucide="rotate-ccw",
            color="warning",
            title="Reactivar publicidad",
            text="La publicidad vuelve a quedar pendiente de instalación. ¿Continuar?",
        ),
    )
    def undiscard(self, user=None, **kwargs):
        self._sync_request(user, self.workflow.PENDIENTE)

    @transition(
        field="state",
        source=[workflow.CONFIGURADA, workflow.ASIGNADA],
        target=workflow.ASIGNADA,
        permission="territorial_ads.install_physicaladvertisement",
        # Source=CONFIGURADA already guarantees the publicidad is configured;
        # the parent request must also be approved. Re-runnable from ASIGNADA
        # to change the installer.
        conditions=[unit_request_approved],
        custom=dict(
            verbose="Asignar instalador",
            icon="user-check",
            lucide="user-check",
            color="light-primary",
            title="Asignar instalador",
            text="Indica quién instalará esta publicidad (interno o externo).",
            form="apps.territorial_ads.forms.AssignUnitInstallerForm",
        ),
    )
    def assign_installer(
        self, user=None, assigned_installer=None, installer_team="", **kwargs
    ):
        self.assigned_installer_id = (
            int(getattr(assigned_installer, "pk", assigned_installer))
            if assigned_installer not in (None, "")
            else None
        )
        self.installer_team = installer_team or ""
        self.assigned_by = user
        self.assigned_at = timezone.now()
