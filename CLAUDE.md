# CLAUDE.md — CampaignManager

> Este archivo es **vivo**: cambia con frecuencia. Reléelo en cada sesión y
> actualízalo cuando una regla nueva aparezca o una vieja deje de aplicar.

## Flujo de trabajo

- Si llegan **varios pedidos a la vez** (o uno grande con partes independientes),
  para ir más rápido puedes **lanzar múltiples agentes en paralelo** (tool `Agent`)
  y repartir el trabajo entre ellos. Hazlo sin pedir permiso cuando las partes no
  dependen entre sí; reserva el trabajo secuencial para lo que sí tiene dependencias.
- **Patrón project-manager / revisor:** cuando repartas trabajo entre varios
  agentes, actúa como project manager: asigna explícitamente qué hace cada uno
  ("tú haces esto, tú lo otro") y, al terminar, corre un **agente revisor** que
  valide el output de cada agente (correctitud, convenciones, que no se pisen
  archivos) antes de darlo por hecho. No declares terminado sin ese paso de
  revisión.
- Ante requisitos ambiguos, preguntar antes de implementar (usar `AskUserQuestion`).

## Git

- Nunca hacer `git commit` sin confirmación explícita del usuario.
- Nunca agregar la línea `Co-Authored-By: Claude ...` en los mensajes de commit.

## Plantillas (Django)

- Prohibido dejar comentarios `{# ... #}` ni `<!-- ... -->` dentro de las
  plantillas, sobre todo las que se inyectan en modales vía AJAX (p. ej. el
  detalle del mapa). Pueden quedar visibles en la interfaz. Las explicaciones van
  en el código Python/JS o en el mensaje de commit.

## Workflows y sub-flujos

Patrón para un **modelo hijo con su propio flujo FSM anidado dentro del flujo de
un padre** (p. ej. solicitud↔publicidad). Reutilizable, vive en `apps/workflows`:

- **Derivación (hacia abajo):** el estado del padre se deriva de sus hijos.
  Usar `apps/workflows/subflow.py::ChildDrivenParentMixin` — el padre declara
  `subflow_children()`, `derive_parent_state(states)` y el mapa
  `DERIVED_STATE_TRANSITIONS = {estado_destino: "nombre_transición"}`. Los hijos
  llaman `parent.sync_from_children(pending_child=self, pending_state=...)` desde
  sus transiciones. La derivación solo dispara transiciones del padre que estén
  *disponibles* (su `source` actúa de guarda), así los pasos manuales/gateados no
  se auto-disparan.
- **Gating (hacia arriba):** una transición *forward* del padre se bloquea hasta
  que los hijos lleguen a cierto estado. No requiere maquinaria nueva: declarar un
  `ChildrenComplete`/`Custom` en `custom={"requirements": [...]}` de la transición
  (valida en duro vía `RequirementsValidator.run` y pinta el checklist en la UI).

Ejemplo de referencia: `PhysicalAdvertisement` (padre) ↔ `PhysicalAdvertisementUnit`
(hijo) en `apps/territorial_ads`.

## Código

- Todo el texto a nivel de código (comentarios, docstrings, logs) en **inglés**.
  Español solo para strings visibles al usuario en la UI.

## Form Policies

- Para ocultar, deshabilitar o limpiar campos según usuario/permiso/creador,
  estado del objeto o valor de otro campo, usar `core.form_policies`.
- Declarar reglas en `BaseSite.form_policies` cuando el formulario pertenece al
  superadmin. Usar `Form.Meta.form_policies` solo para formularios standalone o
  acciones que no pasan por un `Site`.
- `FieldPolicy` cubre permisos/backend: `HasPerm`, `IsCreator`, `StateIs`,
  `StateIn`, etc. Usar `ReadOnlyPolicy` cuando la regla se entiende mejor como
  "visible pero no editable". `ConditionalPolicy` cubre UI dinámica por valores
  del mismo formulario: `show`, `hide`, `disable`, `clear`. Usar
  `RequiredPolicy` para campos obligatorios solo bajo una condición.
- No crear JS específico por app para casos genéricos de visibilidad. El JS
  global vive en `static/assets/js/forms/conditional_fields.js` y funciona en
  formularios normales e insoles.
- Ver ejemplos y detalles en `DESIGN.md`.
