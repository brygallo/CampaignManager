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

from apps.territorial_ads.workflows import PhysicalAdUnitWorkflow, PhysicalAdWorkflow


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
            title="Aprobar solicitud",
            text=(
                "Selecciona el tamaño de cada publicidad solicitada y las "
                "indicaciones de instalación por tipo. Al aprobar se crean "
                "las publicidades individuales."
            ),
            form="apps.territorial_ads.forms.ApprovalForm",
        ),
    )
    def approve(
        self,
        user=None,
        width_meters=None,
        height_meters=None,
        **kwargs,
    ):
        # Legacy callers may still send global dimensions; per-unit sizes
        # are the source of truth now.
        if width_meters is not None:
            self.width_meters = width_meters
        if height_meters is not None:
            self.height_meters = height_meters
        for item in self.items.all():
            # Approval materializes the physical units. A re-approval (after
            # ``revert_to_offered``) recreates them: at that point units are
            # still PENDIENTE, so nothing meaningful is lost.
            item.units.all().delete()
            unit_states = PhysicalAdUnitWorkflow()
            for number in range(1, item.quantity + 1):
                approved = bool(kwargs.get(f"unit_approved_{item.pk}_{number}"))
                raw = kwargs.get(f"item_size_{item.pk}_{number}")
                size_id = None
                if raw not in (None, ""):
                    # ChangeStateView forwards raw POST strings.
                    size_id = int(getattr(raw, "pk", raw))
                instructions = kwargs.get(f"unit_instructions_{item.pk}_{number}") or ""
                # A unit left unchecked is kept as DESCARTADA ("No instalada")
                # so it stays visible and can be reactivated later, instead of
                # silently vanishing.
                item.units.create(
                    unit_number=number,
                    size_id=size_id,
                    installation_instructions=instructions,
                    state=unit_states.PENDIENTE if approved else unit_states.DESCARTADA,
                )
        self._create_new_items_from_approval(kwargs)
        self.approved_by = user
        self.approved_at = timezone.now()

    def _create_new_items_from_approval(self, kwargs):
        """Materialize brand-new advertisements added in the approval form.

        Rows carry indexed names (``new_type_0``, ``new_quantity_0``…). The
        form has already validated that each type is new and not duplicated,
        so creating the item can't hit the unique-per-type constraint.
        """
        prefix = "new_type_"
        indices = sorted(
            int(key[len(prefix):])
            for key in kwargs
            if key.startswith(prefix) and key[len(prefix):].isdigit()
        )
        for i in indices:
            type_raw = kwargs.get(f"new_type_{i}")
            if not type_raw:
                continue
            type_id = int(getattr(type_raw, "pk", type_raw))
            try:
                quantity = max(1, int(kwargs.get(f"new_quantity_{i}") or 1))
            except (TypeError, ValueError):
                quantity = 1
            size_raw = kwargs.get(f"new_size_{i}")
            size_id = (
                int(getattr(size_raw, "pk", size_raw))
                if size_raw not in (None, "")
                else None
            )
            instructions = kwargs.get(f"new_instructions_{i}") or ""
            new_item = self.items.create(
                advertisement_type_id=type_id, quantity=quantity
            )
            for number in range(1, quantity + 1):
                new_item.units.create(
                    unit_number=number,
                    size_id=size_id,
                    installation_instructions=instructions,
                )

    @transition(
        field="state",
        source=workflow.OFRECIDA,
        target=workflow.RECHAZADA,
        permission="territorial_ads.reject_physicaladvertisement",
        custom=dict(
            verbose="Rechazar",
            icon="cross-circle",
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
            color="warning",
            title="Devolver a ofrecida",
            text=(
                "La aprobación se anulará para corregir datos y volver a "
                "aprobar. Las publicidades creadas se eliminarán y se "
                "volverán a generar al aprobar. ¿Continuar?"
            ),
        ),
    )
    def revert_to_offered(self, user=None, **kwargs):
        for item in self.items.all():
            item.units.all().delete()
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
            color="primary",
            title="Enviar a instalación",
            text=(
                "La solicitud pasa a instalación. El instalador se asigna por "
                "publicidad desde cada tarjeta. ¿Continuar?"
            ),
        ),
    )
    def assign_installation(self, user=None, **kwargs):
        # Installer/team are assigned per unit now; this transition only moves
        # the request into the installation stage.
        pass

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
        unit_workflow = PhysicalAdUnitWorkflow()
        # Retire every unit without per-unit request sync; this transition's
        # own target (RETIRADA) sets the request state once.
        for item in self.items.all():
            for unit in item.units.exclude(state=unit_workflow.RETIRADA):
                unit.retire(user=user, _skip_sync=True)
                unit.save()
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
        **kwargs,
    ):
        type_id = int(getattr(advertisement_type, "pk", advertisement_type))
        try:
            qty = max(1, int(quantity or 1))
        except (TypeError, ValueError):
            qty = 1
        size_id = int(getattr(size, "pk", size)) if size not in (None, "") else None
        new_item = self.items.create(advertisement_type_id=type_id, quantity=qty)
        for number in range(1, qty + 1):
            new_item.units.create(
                unit_number=number,
                size_id=size_id,
                installation_instructions=instructions or "",
            )


class PhysicalAdUnitTransitions:
    workflow = PhysicalAdUnitWorkflow()

    def _sync_request(self, user, my_target_state):
        self.item.advertisement.sync_state_with_units(
            user=user, pending_unit=self, pending_state=my_target_state
        )

    @transition(
        field="state",
        source=workflow.PENDIENTE,
        target=workflow.INSTALADA,
        permission="territorial_ads.install_physicaladvertisement",
        custom=dict(
            verbose="Marcar instalada",
            icon="check-circle",
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
        target=workflow.PENDIENTE,
        permission="territorial_ads.install_physicaladvertisement",
        custom=dict(
            verbose="Volver a pendiente",
            back_verbose="Volver a pendiente",
            icon="arrow-left",
            color="warning",
            title="Volver a pendiente",
            text=(
                "La foto, la ubicación y las notas de esta publicidad se "
                "limpiarán para registrar la instalación de nuevo. ¿Continuar?"
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
        self._sync_request(user, self.workflow.PENDIENTE)

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
        source=workflow.PENDIENTE,
        target=workflow.DESCARTADA,
        permission="territorial_ads.install_physicaladvertisement",
        custom=dict(
            verbose="No se instalará",
            icon="slash",
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
            color="warning",
            title="Reactivar publicidad",
            text="La publicidad vuelve a quedar pendiente de instalación. ¿Continuar?",
        ),
    )
    def undiscard(self, user=None, **kwargs):
        self._sync_request(user, self.workflow.PENDIENTE)

    @transition(
        field="state",
        source=[workflow.PENDIENTE, workflow.INSTALADA],
        # ``target=None``: assigning an installer doesn't change the unit
        # state. The form (AssignUnitInstallerForm) only validates; the
        # fields are written here from the POST kwargs.
        target=None,
        permission="territorial_ads.install_physicaladvertisement",
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
