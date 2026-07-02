"""Declarative form policies for permissions and conditional UI behavior."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from django import forms


class Predicate:
    """Boolean expression evaluated against request, object and form values."""

    client_safe = False

    def evaluate(self, context: "PolicyContext") -> bool:
        raise NotImplementedError

    def as_client(self) -> dict[str, Any] | None:
        return None

    def __and__(self, other: "Predicate") -> "Predicate":
        return AllOf((self, ensure_predicate(other)))

    def __or__(self, other: "Predicate") -> "Predicate":
        return AnyOf((self, ensure_predicate(other)))

    def __invert__(self) -> "Predicate":
        return Not(self)


@dataclass(frozen=True)
class Always(Predicate):
    client_safe = True

    def evaluate(self, context: "PolicyContext") -> bool:
        return True

    def as_client(self) -> dict[str, Any]:
        return {"type": "always"}


@dataclass(frozen=True)
class Never(Predicate):
    client_safe = True

    def evaluate(self, context: "PolicyContext") -> bool:
        return False

    def as_client(self) -> dict[str, Any]:
        return {"type": "never"}


@dataclass(frozen=True)
class HasPerm(Predicate):
    permission: str

    def evaluate(self, context: "PolicyContext") -> bool:
        user = getattr(context.request, "user", None)
        return bool(user and user.has_perm(self.permission))


@dataclass(frozen=True)
class IsSuperUser(Predicate):
    def evaluate(self, context: "PolicyContext") -> bool:
        return bool(getattr(getattr(context.request, "user", None), "is_superuser", False))


@dataclass(frozen=True)
class IsStaff(Predicate):
    def evaluate(self, context: "PolicyContext") -> bool:
        return bool(getattr(getattr(context.request, "user", None), "is_staff", False))


@dataclass(frozen=True)
class IsOwner(Predicate):
    field_name: str = "created_by"

    def evaluate(self, context: "PolicyContext") -> bool:
        obj = context.obj
        user = getattr(context.request, "user", None)
        if obj is None or user is None or not getattr(user, "is_authenticated", False):
            return False
        owner = getattr(obj, self.field_name, None)
        owner_id = getattr(obj, f"{self.field_name}_id", None)
        return bool(owner_id == user.pk or getattr(owner, "pk", None) == user.pk)


@dataclass(frozen=True)
class StateIs(Predicate):
    state: str
    field_name: str = "status"

    def evaluate(self, context: "PolicyContext") -> bool:
        return context.get_object_state(self.field_name) == self.state


@dataclass(frozen=True)
class StateIn(Predicate):
    states: tuple[str, ...]
    field_name: str = "status"

    def __init__(self, *states: str, field_name: str = "status"):
        object.__setattr__(self, "states", tuple(states))
        object.__setattr__(self, "field_name", field_name)

    def evaluate(self, context: "PolicyContext") -> bool:
        return context.get_object_state(self.field_name) in self.states


@dataclass(frozen=True)
class FieldValue(Predicate):
    field_name: str
    operator: str = "equals"
    value: Any = None
    client_safe = True

    def evaluate(self, context: "PolicyContext") -> bool:
        return compare_value(context.get_field_value(self.field_name), self.operator, self.value)

    def as_client(self) -> dict[str, Any]:
        return {
            "type": "field",
            "field": self.field_name,
            "operator": self.operator,
            "value": self.value,
        }


@dataclass(frozen=True)
class AllOf(Predicate):
    predicates: tuple[Predicate, ...]

    def evaluate(self, context: "PolicyContext") -> bool:
        return all(predicate.evaluate(context) for predicate in self.predicates)

    def as_client(self) -> dict[str, Any] | None:
        parts = [predicate.as_client() for predicate in self.predicates]
        if any(part is None for part in parts):
            return None
        return {"type": "all", "predicates": parts}


@dataclass(frozen=True)
class AnyOf(Predicate):
    predicates: tuple[Predicate, ...]

    def evaluate(self, context: "PolicyContext") -> bool:
        return any(predicate.evaluate(context) for predicate in self.predicates)

    def as_client(self) -> dict[str, Any] | None:
        parts = [predicate.as_client() for predicate in self.predicates]
        if any(part is None for part in parts):
            return None
        return {"type": "any", "predicates": parts}


@dataclass(frozen=True)
class Not(Predicate):
    predicate: Predicate

    def evaluate(self, context: "PolicyContext") -> bool:
        return not self.predicate.evaluate(context)

    def as_client(self) -> dict[str, Any] | None:
        part = self.predicate.as_client()
        if part is None:
            return None
        return {"type": "not", "predicate": part}


IsCreator = IsOwner


@dataclass(frozen=True)
class FieldPolicy:
    fields: str | Iterable[str]
    visible_if: Predicate = field(default_factory=Always)
    editable_if: Predicate = field(default_factory=Always)
    readonly_mode: str = "disabled"
    disabled_reason: str = ""


def FieldPermissionPolicy(
    *,
    fields: str | Iterable[str],
    view_permission: str | None = None,
    edit_permission: str | None = None,
    readonly_mode: str = "disabled",
    disabled_reason: str = "",
) -> FieldPolicy:
    """Build a field policy from Django permissions."""
    edit_permission = edit_permission or view_permission
    return FieldPolicy(
        fields=fields,
        visible_if=HasPerm(view_permission) if view_permission else Always(),
        editable_if=HasPerm(edit_permission) if edit_permission else Always(),
        readonly_mode=readonly_mode,
        disabled_reason=disabled_reason,
    )


@dataclass(frozen=True)
class RequiredPolicy:
    fields: str | Iterable[str]
    required_if: Predicate = field(default_factory=Always)
    message: str = "Este campo es requerido."

    def as_client(self) -> dict[str, Any] | None:
        condition = self.required_if.as_client()
        if condition is None:
            return None
        return {
            "kind": "required",
            "targets": list(normalize_fields(self.fields)),
            "condition": condition,
        }


def ReadOnlyPolicy(
    *,
    fields: str | Iterable[str],
    readonly_if: Predicate = Always(),
    visible_if: Predicate = Always(),
    readonly_mode: str = "disabled",
    disabled_reason: str = "",
) -> FieldPolicy:
    """Build a FieldPolicy using read-only language at declaration sites."""
    return FieldPolicy(
        fields=fields,
        visible_if=visible_if,
        editable_if=~readonly_if,
        readonly_mode=readonly_mode,
        disabled_reason=disabled_reason,
    )


@dataclass(frozen=True)
class ConditionalPolicy:
    source: str
    targets: tuple[str, ...]
    condition: Predicate
    effects: tuple[str, ...] = ("hide", "disable")

    def __init__(
        self,
        *,
        source: str,
        targets: str | Iterable[str],
        condition: Predicate | None = None,
        operator: str = "equals",
        value: Any = None,
        effects: Iterable[str] = ("hide", "disable"),
    ):
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "targets", normalize_fields(targets))
        object.__setattr__(self, "condition", condition or FieldValue(source, operator, value))
        object.__setattr__(self, "effects", tuple(effects))

    def is_active(self, context: "PolicyContext") -> bool:
        return self.condition.evaluate(context)

    def suppresses_target(self, context: "PolicyContext") -> bool:
        active = self.is_active(context)
        if "show" in self.effects and "hide" not in self.effects:
            return not active
        return active

    def as_client(self) -> dict[str, Any] | None:
        condition = self.condition.as_client()
        if condition is None:
            return None
        return {
            "kind": "conditional",
            "source": self.source,
            "targets": list(self.targets),
            "condition": condition,
            "effects": list(self.effects),
        }


@dataclass
class PolicyContext:
    request: Any = None
    obj: Any = None
    form: forms.BaseForm | None = None
    cleaned_data: dict[str, Any] | None = None

    def get_object_state(self, field_name: str) -> Any:
        if self.obj is None:
            return None
        if hasattr(self.obj, field_name):
            return getattr(self.obj, field_name)
        if hasattr(self.obj, "get_current_state"):
            state = self.obj.get_current_state()
            return getattr(state, "value", getattr(state, "name", state))
        return None

    def get_field_value(self, field_name: str) -> Any:
        form = self.form
        if form is None:
            return None
        if self.cleaned_data is not None and field_name in self.cleaned_data:
            return self.cleaned_data.get(field_name)
        field = form.fields.get(field_name)
        if field is None:
            return None
        prefixed = form.add_prefix(field_name)
        if form.is_bound:
            if getattr(field, "disabled", False):
                return form.initial.get(field_name, field.initial)
            if hasattr(form.data, "getlist"):
                values = form.data.getlist(prefixed)
                if len(values) > 1:
                    return values
                if values:
                    return values[0]
            return form.data.get(prefixed)
        return form.initial.get(field_name, field.initial)


def ensure_predicate(value: Predicate | bool) -> Predicate:
    if isinstance(value, Predicate):
        return value
    return Always() if value else Never()


def normalize_fields(fields: str | Iterable[str]) -> tuple[str, ...]:
    if fields == "__all__":
        return ("__all__",)
    if isinstance(fields, str):
        return (fields,)
    return tuple(fields)


def compare_value(actual: Any, operator: str, expected: Any = None) -> bool:
    operator = str(operator or "equals").lower()
    if operator == "checked":
        return str(actual).lower() in {"1", "true", "on", "yes", "si", "sí"}
    if operator == "unchecked":
        return str(actual).lower() not in {"1", "true", "on", "yes", "si", "sí"}
    if operator == "empty":
        return actual in (None, "", [], (), {})
    if operator == "not_empty":
        return actual not in (None, "", [], (), {})
    if operator == "in":
        return actual in (expected or ())
    if operator == "not_in":
        return actual not in (expected or ())
    if operator in {">", "gt", ">=", "gte", "<", "lt", "<=", "lte"}:
        try:
            actual_number = float(actual)
            expected_number = float(expected)
        except (TypeError, ValueError):
            return False
        if operator in {">", "gt"}:
            return actual_number > expected_number
        if operator in {">=", "gte"}:
            return actual_number >= expected_number
        if operator in {"<", "lt"}:
            return actual_number < expected_number
        return actual_number <= expected_number
    if operator == "contains":
        if isinstance(actual, (list, tuple, set)):
            return expected in actual
        return str(expected) in str(actual)
    if operator == "startswith":
        return str(actual).startswith(str(expected))
    if operator == "endswith":
        return str(actual).endswith(str(expected))
    if operator == "regex":
        try:
            return re.search(str(expected), str(actual)) is not None
        except re.error:
            return False
    if operator == "not_equals":
        return str(actual) != str(expected)
    return str(actual) == str(expected)


def policy_from_dict(config: dict[str, Any]) -> FieldPolicy | ConditionalPolicy | RequiredPolicy:
    if "required_if" in config:
        return RequiredPolicy(
            fields=config.get("fields") or config.get("targets", ()),
            required_if=config.get("required_if", Always()),
            message=config.get("message", "Este campo es requerido."),
        )
    if "source" in config or "targets" in config:
        return ConditionalPolicy(
            source=config["source"],
            targets=config.get("targets") or config.get("fields", ()),
            operator=config.get("operator") or config.get("when", "equals"),
            value=config.get("value"),
            effects=config.get("effects", ("hide", "disable")),
        )
    return FieldPolicy(
        fields=config.get("fields", ()),
        visible_if=config.get("visible_if", Always()),
        editable_if=config.get("editable_if", Always()),
        readonly_mode=config.get("readonly_mode", "disabled"),
        disabled_reason=config.get("disabled_reason", ""),
    )


def normalize_policies(policies: Iterable[Any]) -> tuple[FieldPolicy | ConditionalPolicy | RequiredPolicy, ...]:
    result = []
    for policy in policies or ():
        if isinstance(policy, dict):
            result.append(policy_from_dict(policy))
        else:
            result.append(policy)
    return tuple(result)


def resolve_policy_fields(form: forms.BaseForm, fields: str | Iterable[str]) -> tuple[str, ...]:
    names = normalize_fields(fields)
    if names == ("__all__",):
        return tuple(form.fields.keys())
    return tuple(name for name in names if name in form.fields)


def clear_cleaned_value(form: forms.BaseForm, cleaned_data: dict[str, Any], field_name: str) -> None:
    field = form.fields.get(field_name)
    if field is None:
        return
    if hasattr(field, "queryset"):
        cleaned_data[field_name] = field.queryset.none() if getattr(field.widget, "allow_multiple_selected", False) else None
    elif getattr(field.widget, "allow_multiple_selected", False):
        cleaned_data[field_name] = []
    elif isinstance(field, forms.BooleanField):
        cleaned_data[field_name] = False
    else:
        cleaned_data[field_name] = None if not isinstance(field, forms.CharField) else ""


def apply_form_policies(
    form: forms.BaseForm,
    *,
    request: Any = None,
    obj: Any = None,
    policies: Iterable[Any] = (),
) -> forms.BaseForm:
    policies = normalize_policies(policies)
    context = PolicyContext(request=request, obj=obj, form=form)
    conditional_policies = [policy for policy in policies if isinstance(policy, ConditionalPolicy)]
    required_policies = [policy for policy in policies if isinstance(policy, RequiredPolicy)]

    for policy in conditional_policies:
        for field_name in resolve_policy_fields(form, policy.targets):
            if any(effect in policy.effects for effect in ("show", "hide", "disable", "clear")):
                form.fields[field_name].required = False
    for policy in required_policies:
        for field_name in resolve_policy_fields(form, policy.fields):
            form.fields[field_name].required = False

    for policy in policies:
        if not isinstance(policy, FieldPolicy):
            continue
        for field_name in resolve_policy_fields(form, policy.fields):
            field = form.fields.get(field_name)
            if field is None:
                continue
            if not policy.visible_if.evaluate(context):
                form.fields.pop(field_name, None)
                continue
            if policy.editable_if.evaluate(context):
                continue
            if policy.readonly_mode == "hidden":
                form.fields.pop(field_name, None)
                continue
            field.disabled = True
            field.required = False
            if policy.disabled_reason:
                field.help_text = f"{field.help_text} {policy.disabled_reason}".strip()
                field.widget.attrs["data-policy-disabled-reason"] = policy.disabled_reason

    client_policies = [
        policy.as_client()
        for policy in [*conditional_policies, *required_policies]
        if policy.as_client() is not None
    ]
    form.conditional_policies_json = json.dumps(
        client_policies,
        ensure_ascii=False,
    )
    wrap_clean(form, conditional_policies, required_policies, request, obj)
    return form


def form_meta_policies(form: forms.BaseForm) -> tuple[FieldPolicy | ConditionalPolicy, ...]:
    meta = getattr(form, "Meta", None)
    return normalize_policies(getattr(meta, "form_policies", ()) or ())


def apply_declared_form_policies(
    form: forms.BaseForm,
    *,
    request: Any = None,
    obj: Any = None,
    site: Any = None,
) -> forms.BaseForm:
    policies = ()
    if site is not None and hasattr(site, "get_form_policies"):
        policies = site.get_form_policies(request, obj=obj)
    policies = tuple(policies or ()) + form_meta_policies(form)
    return apply_form_policies(form, request=request, obj=obj, policies=policies)


def wrap_clean(
    form: forms.BaseForm,
    conditional_policies: Iterable[ConditionalPolicy],
    required_policies: Iterable[RequiredPolicy],
    request: Any,
    obj: Any,
) -> None:
    if getattr(form, "_conditional_policies_clean_wrapped", False):
        return
    original_clean = form.clean

    def clean():
        cleaned_data = original_clean()
        context = PolicyContext(request=request, obj=obj, form=form, cleaned_data=cleaned_data)
        for policy in conditional_policies:
            if not policy.suppresses_target(context) or "clear" not in policy.effects:
                continue
            for field_name in resolve_policy_fields(form, policy.targets):
                clear_cleaned_value(form, cleaned_data, field_name)
        for policy in required_policies:
            if not policy.required_if.evaluate(context):
                continue
            for field_name in resolve_policy_fields(form, policy.fields):
                value = cleaned_data.get(field_name)
                if value in (None, "", [], (), {}):
                    form.add_error(field_name, policy.message)
        return cleaned_data

    form.clean = clean
    form._conditional_policies_clean_wrapped = True
