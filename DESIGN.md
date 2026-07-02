# CampaignManager Design Notes

## Form Policies

Form behavior that depends on permissions, ownership, object state, or another
field value must be declared as a policy instead of custom per-form JavaScript.
Policies live in `core.form_policies` and are applied automatically by
`BaseSite` on normal superadmin forms. Insoles forms also apply the same policy
pipeline when their forms are created manually.

### FieldPolicy

Use `FieldPolicy` when access depends on request/user/object context.

```python
from core.form_policies import FieldPolicy, HasPerm, IsCreator, StateIs


class SurveySite(BaseSite):
    form_policies = (
        FieldPolicy(
            fields="__all__",
            editable_if=IsCreator("created_by") & StateIs("draft"),
        ),
        FieldPolicy(
            fields=("status",),
            editable_if=HasPerm("surveys.publish_survey"),
        ),
    )
```

Rules are enforced server-side. If a user forges a POST for a disabled field,
Django ignores the submitted value because the field is marked disabled before
validation.

Use `ReadOnlyPolicy` when the business rule is clearer in read-only language:

```python
from core.form_policies import ReadOnlyPolicy, HasPerm


class EmployeeSite(BaseSite):
    form_policies = (
        ReadOnlyPolicy(
            fields=("salary",),
            readonly_if=~HasPerm("employees.change_salary"),
            disabled_reason="No tienes permiso para modificar el salario.",
        ),
    )
```

This keeps the field visible, but disables it and preserves the original value
server-side if a forged POST tries to modify it.

Common predicates:

- `HasPerm("app.permission")`
- `IsSuperUser()`
- `IsStaff()`
- `IsCreator("created_by")`
- `IsOwner("user")`
- `StateIs("draft")`
- `StateIn("draft", "published")`
- predicates can be composed with `&`, `|`, and `~`

### ConditionalPolicy

Use `ConditionalPolicy` when behavior depends on another value in the same
form. These policies are serialized into the form HTML as JSON and executed by
`static/assets/js/forms/conditional_fields.js`.

```python
from core.form_policies import ConditionalPolicy


class SurveySite(BaseSite):
    form_policies = (
        ConditionalPolicy(
            source="all_users_can_respond",
            operator="checked",
            targets=("assigned_users",),
            effects=("hide", "disable", "clear"),
        ),
    )
```

Use `show` for the inverse case: the target is shown only when the condition is
true.

```python
ConditionalPolicy(
    source="question_type",
    operator="in",
    value=("single_choice", "multiple_choice"),
    targets=("option_lines",),
    effects=("show", "disable", "clear"),
)
```

Supported operators:

- `equals`
- `not_equals`
- `in`
- `not_in`
- `>`, `gt`
- `>=`, `gte`
- `<`, `lt`
- `<=`, `lte`
- `contains`
- `startswith`
- `endswith`
- `regex`
- `checked`
- `unchecked`
- `empty`
- `not_empty`

Supported effects:

- `show`: show target only when the condition is true
- `hide`: hide target when the condition is true
- `disable`: disable target while suppressed
- `clear`: clear target while suppressed

Conditional target fields are marked `required=False` before validation because
hidden/disabled fields may not be posted by the browser. If the field is
conditionally required when visible, add a matching `RequiredPolicy`.

### RequiredPolicy

Use `RequiredPolicy` when a field is only mandatory under a condition. This is
the declarative version of "when this field is visible, it is required".

```python
from core.form_policies import ConditionalPolicy, FieldValue, RequiredPolicy


option_question = FieldValue(
    "question_type",
    "in",
    ("single_choice", "multiple_choice"),
)

class QuestionForm(forms.ModelForm):
    class Meta:
        form_policies = (
            ConditionalPolicy(
                source="question_type",
                condition=option_question,
                targets=("option_lines",),
                effects=("show", "disable", "clear"),
            ),
            RequiredPolicy(
                fields=("option_lines",),
                required_if=option_question,
                message="Agrega al menos una opción.",
            ),
        )
```

`RequiredPolicy` is enforced server-side and also toggles the browser's
`required` attribute plus the label's required marker when the condition can be
serialized to the frontend. It can depend on form values with `FieldValue`, or
on backend-only predicates such as `HasPerm`, `IsCreator`, or `StateIs`.

### Form.Meta fallback

Forms that do not belong to a `BaseSite` can declare policies in `Meta`:

```python
class MyActionForm(forms.Form):
    class Meta:
        form_policies = (
            ConditionalPolicy(
                source="mode",
                operator="equals",
                value="advanced",
                targets=("advanced_notes",),
                effects=("show", "disable", "clear"),
            ),
        )
```

Use `Site.form_policies` when the form is registered in superadmin. Use
`Meta.form_policies` only for standalone or action forms.
