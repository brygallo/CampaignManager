"""Reusable "sub-flow" coupling for nested workflows.

A *sub-flow* is a CHILD model that runs its own FSM workflow while living inside
a PARENT that runs its own workflow too (e.g. a request whose line-items, units
or tasks each have an independent lifecycle). Two complementary couplings make
that relationship work, and both are first-class here:

1. **Derivation (downward).** When a child changes state, the parent re-derives
   its own state from the aggregate of its children. That logic — collect child
   states, decide the parent state, fire the matching parent transition — is the
   same for every sub-flow and is encapsulated by :class:`ChildDrivenParentMixin`.
   The parent only declares *what* its children are and *how* their states map to
   a parent state; the mixin does the rest.

2. **Gating (upward).** A parent *forward* transition stays blocked until its
   children reach a required state (e.g. "every publicidad configured", "every
   task signed"). That needs no new machinery: declare a
   :class:`~apps.workflows.requirements.ChildrenComplete` (or ``Custom``)
   requirement on the parent transition's ``custom={"requirements": [...]}`` —
   it both hard-validates (``RequirementsValidator.run``) and renders the UI
   checklist.

Usage (parent side)::

    class Order(BaseModel, OrderTransitions, ChildDrivenParentMixin):
        # target parent state -> the (usually hidden) @transition that reaches it
        DERIVED_STATE_TRANSITIONS = {
            OrderWorkflow.Choices.DONE: "complete",
            OrderWorkflow.Choices.IN_PROGRESS: "reopen",
        }

        def subflow_children(self):
            # Fresh queryset, NOT a cached property: sync must see committed rows.
            return OrderLine.objects.filter(order=self)

        def derive_parent_state(self, child_states):
            if all(s == LineWorkflow.DONE for s in child_states):
                return OrderWorkflow.Choices.DONE
            if any(s == LineWorkflow.IN_PROGRESS for s in child_states):
                return OrderWorkflow.Choices.IN_PROGRESS
            return None  # leave the parent unchanged

Usage (child side): from inside a child transition, before the child row is
saved, notify the parent with the in-flight target state::

    def start(self, user=None, **kwargs):
        self.order.sync_from_children(
            user=user, pending_child=self, pending_state=LineWorkflow.IN_PROGRESS
        )
"""


class ChildDrivenParentMixin:
    """Mixin for a PARENT model whose FSM state is derived from its children.

    The host model must be a django_fsm model (it provides ``state`` and
    ``get_available_state_transitions``). Declare ``DERIVED_STATE_TRANSITIONS``,
    ``subflow_children`` and ``derive_parent_state``; optionally override
    ``child_subflow_state`` if a child stores its state somewhere other than
    ``child.state``.
    """

    #: Map of derived parent target state value -> name of the ``@transition``
    #: method that reaches it. The transition is usually declared ``hidden`` (it
    #: fires automatically, not from a button) and its ``source`` states act as
    #: the guard for *when* the derivation may apply.
    DERIVED_STATE_TRANSITIONS = {}

    def subflow_children(self):
        """Return an iterable of the child instances that drive this parent.

        Return a FRESH queryset rather than a cached property: ``sync_from_children``
        must observe the children's committed states, not a stale prefetch.
        """
        raise NotImplementedError

    def child_subflow_state(self, child):
        """Return a child's workflow state. Override if it lives off ``state``."""
        return child.state

    def _collect_child_states(self, pending_child, pending_state):
        """Child states with the in-flight child's *target* state substituted.

        A child transition calls us BEFORE saving its own row, so the DB still
        holds the child's previous state; ``pending_child``/``pending_state`` let
        the caller override it with the state it is transitioning into.
        """
        states = []
        for child in self.subflow_children():
            if pending_child is not None and child.pk == pending_child.pk:
                states.append(pending_state)
            else:
                states.append(self.child_subflow_state(child))
        return states

    def derive_parent_state(self, child_states):
        """Return the parent state implied by ``child_states``.

        Return ``None`` (or the current state) to leave the parent unchanged.
        Keep this PURE: source-state guards are handled by the transition's own
        ``source`` plus the availability check in ``sync_from_children``.
        """
        raise NotImplementedError

    def sync_from_children(self, user=None, pending_child=None, pending_state=None):
        """Re-derive and apply this parent's state from its children.

        Returns ``True`` when a parent transition was fired, else ``False``. The
        derived transition is only fired when it is currently *available* (its
        ``source`` matches the parent's state), so a derivation that does not
        apply at the current stage is a safe no-op — never a ``TransitionNotAllowed``.
        """
        states = self._collect_child_states(pending_child, pending_state)
        if not states:
            return False
        target = self.derive_parent_state(states)
        if target is None or int(target) == int(self.state):
            return False
        method_name = self.DERIVED_STATE_TRANSITIONS.get(int(target))
        if not method_name:
            return False
        # Respect the transition's own source guard: only fire when allowed from
        # the current state. This is what keeps gated forward steps (e.g. a
        # manually-confirmed "send to installation") from auto-firing.
        available = {t.name for t in self.get_available_state_transitions()}
        if method_name not in available:
            return False
        getattr(self, method_name)(user=user)
        self.save()
        return True

    def apply_to_children(
        self,
        transition_name,
        user=None,
        children=None,
        skip_unavailable=True,
        **kwargs,
    ):
        """Run a CHILD transition across the children, reusing the child's own
        logic (single source of truth — the parent never re-implements it).

        This is the *upward reuse* counterpart to derivation: from the parent you
        drive every child through the same transition you would call on one child
        (e.g. "retire all", "send all"). Each child runs its transition and saves;
        children whose ``source`` does not currently allow the transition are
        skipped when ``skip_unavailable`` is True (otherwise the child raises).
        The parent's own state re-derives via each child's sync, plus a final
        ``sync_from_children`` for safety.

        Returns the list of children that actually transitioned.
        """
        targets = self.subflow_children() if children is None else children
        changed = []
        for child in targets:
            method = getattr(child, transition_name, None)
            if method is None:
                continue
            available = {t.name for t in child.get_available_state_transitions()}
            if transition_name not in available and skip_unavailable:
                continue
            method(user=user, **kwargs)
            child.save()
            changed.append(child)
        self.sync_from_children(user=user)
        return changed
