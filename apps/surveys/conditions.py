"""State/checklist conditions for the survey workflow.

Module-level functions, following the ``conditions.py`` convention of
``apps/territorial_ads``. Each takes the model instance and returns an
``(is_met, value)`` tuple used as the ``check`` of a ``Custom`` requirement
(hard guard + checklist rendered on the detail page).
"""


def publication_status(survey):
    """(is_met, value) for the publish checklist.

    Wraps ``get_survey_publication_issues`` so the requirement UI shows whether
    the form is ready and, when not, how many issues remain plus the first one.
    """
    from apps.surveys.services import get_survey_publication_issues  # lazy: avoid cycle

    issues = get_survey_publication_issues(survey)
    if not issues:
        return True, "Formulario completo"
    return False, f"{len(issues)} pendiente(s): {issues[0]}"
