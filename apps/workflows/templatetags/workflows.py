from django import template
from django.urls import reverse

register = template.Library()


@register.filter
def getattr_dynamic(obj, attr_name):
    """Resolve an attribute by name on ``obj``.

    Enables generic templates (e.g. the reusable sub-workflow include) to
    display a label whose attribute name is provided via context, since the
    Django template language cannot do dynamic attribute lookup natively.
    Falls back to ``display_label`` and then ``str(obj)`` when missing.
    """
    value = getattr(obj, attr_name, None)
    if value is None:
        value = getattr(obj, "display_label", None)
    if value is None:
        return str(obj)
    return value


@register.simple_tag
def transition_perm(user, permission):
    """Check permission workflow"""
    return user.has_perm(f"{permission}")


@register.simple_tag(takes_context=True)
def context_transition_perm(context, list_perm):
    state = False
    if isinstance(list_perm, list):
        state_list = [context.get(perm, False) for perm in list(list_perm)]
        if True in state_list:
            state = True
    if isinstance(list_perm, bool):
        state = list_perm
    return state


@register.simple_tag
def workflow_change_state(instance):
    app_name = instance.__class__._meta.app_label
    model_name = instance._meta.model.__name__
    return reverse("workflow_change_state", args=(app_name, model_name, instance.pk))


@register.simple_tag
def workflow_visible_states(state):
    return state - 1, state, state + 1


@register.simple_tag(takes_context=True)
def split_backward_transitions(context, instance):
    """
    Split backward transitions (target < current_state, target != 0) into:
        - closest: the transition whose target is nearest to the current state
        - others : the remaining backward transitions, sorted by proximity
    Filters out those the user doesn't have permission for.
    """
    request = context.get("request")
    user = getattr(request, "user", None)
    current_state = getattr(instance, "state", None)
    if current_state is None:
        return {"closest": None, "others": []}

    candidates = []
    for transition in instance.get_available_state_transitions():
        target = getattr(transition, "target", None)
        if target is None or target == 0 or target >= current_state:
            continue
        if (getattr(transition, "custom", None) or {}).get("hidden"):
            continue
        if user and getattr(transition, "permission", None):
            if not user.has_perm(transition.permission):
                continue
        candidates.append(transition)

    # Closest-first ordering: highest target < state first
    candidates.sort(key=lambda t: t.target, reverse=True)
    return {
        "closest": candidates[0] if candidates else None,
        "others": candidates[1:],
    }


@register.simple_tag(takes_context=True)
def neutral_transitions(context, instance):
    """
    Transitions that keep the current state (``target=None``), e.g. partial
    evidence uploads or contact fixes. Filtered by user permission.
    """
    request = context.get("request")
    user = getattr(request, "user", None)
    if getattr(instance, "state", None) is None:
        return []
    result = []
    for transition in instance.get_available_state_transitions():
        if getattr(transition, "target", "missing") is not None:
            continue
        if (getattr(transition, "custom", None) or {}).get("hidden"):
            continue
        if user and getattr(transition, "permission", None):
            if not user.has_perm(transition.permission):
                continue
        result.append(transition)
    return result


@register.simple_tag(takes_context=True)
def split_forward_transitions(context, instance):
    """
    Split forward transitions (target >= current_state, target != 0) into:
        - closest: the transition whose target is nearest to the current state
        - others : the remaining forward transitions, sorted by proximity
    Filters out those the user doesn't have permission for.
    """
    request = context.get("request")
    user = getattr(request, "user", None)
    current_state = getattr(instance, "state", None)
    if current_state is None:
        return {"closest": None, "others": []}

    candidates = []
    for transition in instance.get_available_state_transitions():
        target = getattr(transition, "target", None)
        if target is None or target == 0 or target < current_state:
            continue
        if (getattr(transition, "custom", None) or {}).get("hidden"):
            continue
        if user and getattr(transition, "permission", None):
            if not user.has_perm(transition.permission):
                continue
        candidates.append(transition)

    # Closest-first ordering: lowest target >= state first
    candidates.sort(key=lambda t: t.target)
    return {
        "closest": candidates[0] if candidates else None,
        "others": candidates[1:],
    }
