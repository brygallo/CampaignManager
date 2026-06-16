"""Declarative transition requirements.

A ``@transition`` declares the data it needs via
``custom={"requirements": [...]}``. The list drives two things:

* The UI checklist exposed by a model's ``transition_requirements`` property
  (``RequirementsValidator.for_next_forward_transition``), consumed by
  ``workflows/includes/transition_requirements.html``.
* Hard validation inside the transition body via ``RequirementsValidator.run``,
  which raises ``WorkflowException`` listing every failing item.

A single source of truth: new conditions are added once, in the transition.
Ported from the sim project.
"""

from apps.workflows.exceptions import WorkflowException

DEFAULT_ICON = "fas fa-check-circle"


def _resolve_path(instance, dotted):
    """Walk ``a.b.c`` returning ``None`` on any missing link."""
    obj = instance
    for part in dotted.split("."):
        if obj is None:
            return None
        obj = getattr(obj, part, None)
    return obj


def _resolve(value, instance):
    """Pass-through for plain values; call callables with ``instance``."""
    return value(instance) if callable(value) else value


class Requirement:
    """Base class. Subclasses implement :meth:`check`.

    ``label`` and ``icon`` accept either a plain string or a callable
    ``(instance) -> str``. ``when=callable(instance) -> bool`` makes the
    requirement appear only when the predicate is truthy.
    """

    def __init__(self, label, icon=None, when=None):
        self.label = label
        self.icon = icon or DEFAULT_ICON
        self.when = when

    def check(self, instance):
        """Return ``(is_met, value)`` where ``value`` is what the UI renders."""
        raise NotImplementedError

    def evaluate(self, instance):
        if self.when is not None and not self.when(instance):
            return None
        is_met, value = self.check(instance)
        return {
            "label": _resolve(self.label, instance),
            "value": value,
            "is_met": bool(is_met),
            "icon": _resolve(self.icon, instance),
        }


class Field(Requirement):
    """Requires the attribute (dotted path supported) to be truthy."""

    def __init__(self, field, label, icon=None, formatter=None, when=None):
        super().__init__(label, icon, when)
        self.field = field
        self.formatter = formatter

    def check(self, instance):
        value = _resolve_path(instance, self.field)
        if not value:
            return False, None
        display = self.formatter(value) if self.formatter else value
        return True, display


class File(Requirement):
    """Requires a FileField to be populated; renders just the basename."""

    def __init__(self, field, label, icon=None, when=None):
        super().__init__(label, icon, when)
        self.field = field

    def check(self, instance):
        file_field = _resolve_path(instance, self.field)
        name = getattr(file_field, "name", "") if file_field else ""
        if not name:
            return False, None
        return True, name.split("/")[-1]


class ChildrenComplete(Requirement):
    """Requires every item produced by ``getter`` to satisfy ``predicate``.

    An empty collection is treated as met. ``value_formatter(complete, total)``
    customises the displayed status text.
    """

    def __init__(
        self, getter, predicate, label, icon=None, value_formatter=None, when=None
    ):
        super().__init__(label, icon, when)
        self.getter = getter
        self.predicate = predicate
        self.value_formatter = value_formatter

    def check(self, instance):
        items = list(self.getter(instance) or [])
        total = len(items)
        if total == 0:
            return True, "Sin pendientes"
        complete = sum(1 for it in items if self.predicate(it))
        is_met = complete == total
        value = (
            self.value_formatter(complete, total)
            if self.value_formatter
            else "{} de {}".format(complete, total)
        )
        return is_met, value


class Custom(Requirement):
    """Escape hatch — caller passes ``check(instance) -> (is_met, value)``."""

    def __init__(self, check, label, icon=None, when=None):
        super().__init__(label, icon, when)
        self._check_func = check

    def check(self, instance):
        return self._check_func(instance)


class RequirementsValidator:
    """Bridges declarative requirements with model/template consumers."""

    @staticmethod
    def _requirements(transition):
        custom = getattr(transition, "custom", {}) or {}
        return custom.get("requirements") or []

    @staticmethod
    def _next_forward_transition(instance):
        current_state = getattr(instance, "state", None)
        if current_state is None:
            return None
        candidates = []
        for transition in instance.get_available_state_transitions():
            target = getattr(transition, "target", None)
            if target is None or target == 0 or target < current_state:
                continue
            candidates.append(transition)
        candidates.sort(key=lambda t: t.target)
        return candidates[0] if candidates else None

    @staticmethod
    def _named_transition(instance, name):
        method = getattr(instance, name, None)
        fsm_meta = getattr(method, "_django_fsm", None) if method else None
        if fsm_meta is not None:
            transitions = getattr(fsm_meta, "transitions", {}) or {}
            trans = transitions.get(instance.state) or transitions.get("*")
            if trans is not None:
                return trans
        for transition in instance.get_available_state_transitions():
            if transition.name == name:
                return transition
        return None

    @staticmethod
    def _payload(transition, items):
        custom = getattr(transition, "custom", {}) or {}
        pending = sum(1 for item in items if not item.get("is_met"))
        return {
            "target_label": custom.get("target_label"),
            "transition_verb": custom.get("verbose") or transition.name,
            "items": items,
            "pending_count": pending,
            "help_text": custom.get("help_text")
            or "Completa estos datos para poder avanzar:",
            "ready_text": custom.get("ready_text")
            or "Ya puedes avanzar desde el menú de acciones.",
        }

    @classmethod
    def for_transition(cls, instance, transition):
        if transition is None:
            return None
        items = []
        for req in cls._requirements(transition):
            item = req.evaluate(instance)
            if item is not None:
                items.append(item)
        if not items:
            return None
        return cls._payload(transition, items)

    @classmethod
    def for_next_forward_transition(cls, instance):
        transition = cls._next_forward_transition(instance)
        return cls.for_transition(instance, transition)

    @classmethod
    def run(cls, instance, transition_name):
        """Validate the requirements bound to ``transition_name``.

        Raises ``WorkflowException`` listing every failing requirement label.
        No-ops when the transition is unknown or declares no requirements.
        """
        transition = cls._named_transition(instance, transition_name)
        if transition is None:
            return
        failures = []
        for req in cls._requirements(transition):
            item = req.evaluate(instance)
            if item is None:
                continue
            if not item["is_met"]:
                failures.append(item["label"])
        if failures:
            raise WorkflowException(
                "No se puede avanzar. Datos faltantes o inválidos: "
                + "; ".join(failures)
            )
