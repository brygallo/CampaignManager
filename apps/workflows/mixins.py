class TransitionRequirementsMixin:
    """Helpers to build a consistent transition requirements payload for the UI."""

    @staticmethod
    def build_transition_requirement_item(label, value=None, is_met=False, icon=None):
        return {
            "label": label,
            "value": value,
            "is_met": bool(is_met),
            "icon": icon or "fas fa-check-circle",
        }

    @classmethod
    def build_transition_requirements(
        cls,
        transition_verb,
        items,
        target_label=None,
        help_text=None,
        ready_text=None,
    ):
        pending_count = sum(1 for item in items if not item.get("is_met"))
        return {
            "target_label": target_label,
            "transition_verb": transition_verb,
            "items": items,
            "pending_count": pending_count,
            "help_text": help_text
            or (
                "Completa los requisitos marcados en rojo para habilitar la "
                f"transición {transition_verb} desde el menú de acciones."
            ),
            "ready_text": ready_text
            or f"Puedes ejecutar la transición {transition_verb} desde el menú de acciones.",
        }
