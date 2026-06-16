"""Static groupings and transition names for the territorial ads workflows.

Plain, side-effect-free data only (mirrors sim's ``constants.py`` convention):
no business logic lives here, just named values reused across conditions,
services and transitions.
"""
from apps.territorial_ads.workflows import PhysicalAdUnitWorkflow

_unit_workflow = PhysicalAdUnitWorkflow()

# Unit sub-flow states that still represent a publicidad pending installation
# (not yet installed, discarded or retired). Used by the request-level
# checklist/conditions to decide when installers are still missing.
UNIT_STATES_TO_INSTALL = (
    _unit_workflow.PENDIENTE,
    _unit_workflow.CONFIGURADA,
    _unit_workflow.ASIGNADA,
)

# Request transition names referenced when validating hard requirements
# (``RequirementsValidator.run``). Kept as constants so the string and the
# decorated method name can't drift apart silently.
TRANSITION_APPROVE = "approve"
TRANSITION_ASSIGN_INSTALLATION = "assign_installation"
