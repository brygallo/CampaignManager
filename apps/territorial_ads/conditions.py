"""State/checklist conditions for the territorial ads workflows.

Module-level functions, like the ``conditions.py`` of sim's planning/procedures/
overtime apps. Each takes the model instance and returns either:

- a ``bool`` — used directly as a django-fsm ``conditions=[...]`` guard, or
- an ``(is_met, value)`` tuple — used as the ``check`` of a ``Custom``
  requirement (hard guard + checklist rendered on the detail page).
"""
from apps.territorial_ads.constants import UNIT_STATES_TO_INSTALL
from apps.territorial_ads.workflows import PhysicalAdUnitWorkflow, PhysicalAdWorkflow

_request_workflow = PhysicalAdWorkflow()
_unit_workflow = PhysicalAdUnitWorkflow()


def publicidades_decided_status(ad):
    """(is_met, value) for the approve checklist: every publicidad must be
    configured (size/instructions set) or discarded — none left untouched."""
    units = list(ad.units)
    total = len(units)
    if total == 0:
        return False, "Sin publicidades"
    pending = sum(1 for unit in units if unit.is_unconfigured_pending)
    return pending == 0, f"{total - pending} de {total} configuradas o descartadas"


def publicidades_installer_status(ad):
    """(is_met, value) for the send-to-installation checklist: every publicidad
    still to be installed must have an installer assigned — i.e. it must have
    reached the ``ASIGNADA`` sub-flow state. Discarded/retired/installed units
    don't count."""
    to_install = [unit for unit in ad.units if unit.state in UNIT_STATES_TO_INSTALL]
    total = len(to_install)
    if total == 0:
        return False, "Sin publicidades por instalar"
    assigned = sum(1 for unit in to_install if unit.state == _unit_workflow.ASIGNADA)
    return assigned == total, f"{assigned} de {total} con instalador"


def unit_request_approved(instance):
    """Condition for ``assign_installer``: the parent request (solicitud) must
    already be approved before installers can be assigned to its publicidades."""
    return instance.advertisement.approved_at is not None


def unit_request_in_installation(instance):
    """Condition for ``mark_installed``: the parent request must be in the
    'pending installation' stage before a unit's installation is registered."""
    return instance.advertisement.state == _request_workflow.PENDIENTE_INSTALACION
