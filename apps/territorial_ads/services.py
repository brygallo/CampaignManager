"""Business operations (side effects) for territorial advertising.

Keeps the FSM transitions thin: the ``@transition`` methods on
``PhysicalAdTransitions`` delegate the actual unit creation / bulk retirement
to these class methods. Mirrors sim's ``services.py`` pattern (``OvertimeService``,
``ProcedureService``, ...): stateless classes with ``@classmethod`` operations.
"""
from django.utils import timezone

from apps.territorial_ads.workflows import PhysicalAdUnitWorkflow


class PhysicalAdService:
    unit_workflow = PhysicalAdUnitWorkflow()

    @classmethod
    def add_advertisement(
        cls,
        ad,
        user=None,
        advertisement_type=None,
        quantity=1,
        size=None,
        instructions="",
        assigned_installer=None,
        installer_team="",
    ):
        """Create one or more publicidad units on ``ad`` after approval.

        The request state is unchanged (the transition uses ``target=None``);
        this only materializes the new units. Returns the created unit list.
        """
        unit_workflow = cls.unit_workflow
        type_id = int(getattr(advertisement_type, "pk", advertisement_type))
        try:
            qty = max(1, int(quantity or 1))
        except (TypeError, ValueError):
            qty = 1
        size_id = int(getattr(size, "pk", size)) if size not in (None, "") else None
        installer_id = (
            int(getattr(assigned_installer, "pk", assigned_installer))
            if assigned_installer not in (None, "")
            else None
        )
        # A publicidad added after approval already says who installs it, so the
        # new units are born directly in the matching sub-flow state: ASIGNADA
        # when an installer is given, else CONFIGURADA when a size/instructions
        # are given, else PENDIENTE ("por configurar").
        has_installer = bool(installer_id or installer_team)
        if has_installer:
            unit_state = unit_workflow.ASIGNADA
        elif size_id is not None or instructions:
            unit_state = unit_workflow.CONFIGURADA
        else:
            unit_state = unit_workflow.PENDIENTE
        # Adding a type already in the request just appends more units to its
        # existing item (one item per type — unique constraint), numbering the
        # new units after the current ones. This lets the user add "varias
        # lonas / varios banners" without a duplicate-type error.
        item, _ = ad.items.get_or_create(
            advertisement_type_id=type_id, defaults={"quantity": 0}
        )
        start = item.quantity
        item.quantity = start + qty
        item.save(update_fields=["quantity"])
        created = []
        for number in range(start + 1, start + qty + 1):
            created.append(
                item.units.create(
                    unit_number=number,
                    state=unit_state,
                    size_id=size_id,
                    installation_instructions=instructions or "",
                    assigned_installer_id=installer_id,
                    installer_team=installer_team or "",
                    assigned_by=user if has_installer else None,
                    assigned_at=timezone.now() if has_installer else None,
                )
            )
        return created

    @classmethod
    def retire_all_units(cls, ad, user=None):
        """Retire every active unit of ``ad`` without per-unit request sync.

        The caller (the request ``retire`` transition) sets the request state
        to RETIRADA once, so each unit is retired with ``_skip_sync=True``.
        """
        unit_workflow = cls.unit_workflow
        for item in ad.items.all():
            for unit in item.units.exclude(state=unit_workflow.RETIRADA):
                unit.retire(user=user, _skip_sync=True)
                unit.save()
