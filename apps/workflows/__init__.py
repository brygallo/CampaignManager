# Python
import enum
from types import DynamicClassAttribute
from functools import partialmethod

# Django
from django.db.models.enums import ChoicesMeta
from django.utils.functional import Promise
from django.db.models.query_utils import DeferredAttribute


def get_all_states(cls, Choices):
    return Choices


def get_visible_states(self, Choices):
    return Choices.visible_members


def get_current_state(self, Choices):
    for member in Choices.members:
        if self.state == member.value:
            return member


def is_state_read_only(self, Choices):
    """``True`` when the instance's current workflow state forbids edits.

    A state opts in by declaring ``dict(read_only=True)`` next to its label.
    Lets list/detail templates show a "solo lectura" badge, lets the
    ``BlockEditOnReadOnlyStateMixin`` short-circuit ``update_view``, and
    lets API serializers expose the flag.
    """
    # NOTE: ``current`` is an ``IntEnum`` member whose truthiness mirrors
    # its integer value, so ``bool(member)`` is False for any state with
    # value 0 (e.g. Campaign.CANCELED, PhysicalAd.RECHAZADA). Use an
    # explicit ``is None`` check instead.
    current = get_current_state(self, Choices)
    if current is None:
        return False
    return bool(getattr(current, "read_only", False))


class WorkflowChoicesMeta(ChoicesMeta):
    def __new__(metacls, classname, bases, classdict, **kwds):
        customs = []
        for key in classdict._member_names:
            value = classdict[key]
            if (
                isinstance(value, (list, tuple))
                and len(value) == 3
                and isinstance(value[-1], (Promise, dict))
                and isinstance(value[-2], (Promise, str))
            ):
                *value, custom = value
                value = tuple(value)
            else:
                custom = {}
            customs.append(custom)
            # Use dict.__setitem__() to suppress defenses against double
            # assignment in enum's classdict.
            dict.__setitem__(classdict, key, value)
        cls = super().__new__(metacls, classname, bases, classdict, **kwds)
        for member, custom in zip(cls.__members__.values(), customs):
            for key in custom:
                setattr(member, key, custom[key])
        return enum.unique(cls)

    @property
    def members(cls):
        return cls.__members__.values()

    @property
    def visible_members(cls):
        return [
            member
            for member in cls.__members__.values()
            if not hasattr(member, "visible") or member.visible is not False
        ]


class WorkflowChoices(enum.IntEnum, metaclass=WorkflowChoicesMeta):
    @DynamicClassAttribute
    def label(self):
        return self._label_

    @property
    def do_not_call_in_templates(self):
        return True

    def __str__(self):
        """
        Use value when cast to str, so that Choices set as model instance
        attributes are rendered as expected in templates and similar contexts.
        """
        return str(self.value)


class Workflow:
    def __init__(self, **kwargs):
        for member in self.Choices.members:
            setattr(self, member.name, member)

    def get_state(self, instance):
        return DeferredAttribute(self).__get__(instance)

    @property
    def choices(self):
        return self.Choices.choices

    def contribute_to_class(self, cls, name, **kwargs):
        setattr(
            cls,
            "get_all_states",
            partialmethod(classmethod(get_all_states), Choices=self.Choices),
        )
        setattr(
            cls,
            "get_visible_states",
            partialmethod(get_visible_states, Choices=self.Choices),
        )
        setattr(
            cls,
            "get_current_state",
            partialmethod(get_current_state, Choices=self.Choices),
        )
        setattr(
            cls,
            "is_state_read_only",
            partialmethod(is_state_read_only, Choices=self.Choices),
        )
