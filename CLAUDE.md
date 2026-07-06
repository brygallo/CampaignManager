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
- Mantener las **views delgadas**. La vista debe coordinar HTTP: permisos,
  instanciar formularios, mensajes, redirects/JSON y selección de template. La
  lógica de negocio va en `services.py`, `utils.py` o helpers del dominio.
- Si una operación modifica varias tablas, tiene reglas de dominio, calcula
  alertas, clona objetos, borra datos relacionados, sincroniza líneas/hijos o se
  reutiliza desde más de una vista, crear un **service class/function** en el app
  correspondiente. Ejemplos esperados: `SurveyBuilderResponseService`,
  `ElectoralWatcherReportService`, `clone_survey`,
  `update_survey_question_positions`.
- No duplicar reglas en templates/JS/views. La UI puede ocultar o deshabilitar
  acciones, pero el bloqueo real debe vivir en Python, idealmente en un service o
  policy compartido.
- Los `utils.py` son para helpers puros o casi puros (normalización, parseo,
  pequeñas funciones sin estado). Si el helper toca modelos, transacciones,
  permisos o workflows, preferir `services.py`.
- Cuando una vista necesite la misma guarda en varios endpoints, usar un mixin
  pequeño que delegue en el service; no repetir `get/post` con el mismo `if`.

## Insoles y paneles laterales

- Para crear/editar entidades desde una página, preferir los patrones existentes
  de **Insoles** antes de inventar modales o formularios inline nuevos.
- `insoles-action` abre el modal/flujo nativo de Insoles; `drawer-action` usa el
  mismo contrato backend pero lo muestra en el panel lateral derecho.
- Contrato backend para ambos:
  - `GET` devuelve JSON con `template`, `create_url`, `title`,
    `confirm_button` y opcionalmente `read_only`.
  - `POST create_url` devuelve `{message}` en éxito o `{error, errors}` con
    HTTP 400 en validación.
- Usar `InstanceBaseFormView` cuando el caso es un `ModelForm` estándar. Si el
  formulario es dinámico/no-model o guarda varias tablas, implementar una vista
  compatible con el contrato de Insoles/Drawer, pero mover el guardado a un
  service.
- Para acciones destructivas o de confirmación irreversible (eliminar, vaciar,
  reiniciar, anular, quitar datos relacionados), reutilizar
  `InstanceBaseDeleteView`. Configurar `delete_heading`, `delete_message`,
  `checkbox_label`, `success_message` y sobrescribir `perform_delete()` cuando la
  acción no sea `self.get_object().delete()`. No crear formularios ad hoc con
  textos mágicos como confirmación.
- No dejar formularios grandes pegados en una pantalla si son acciones
  secundarias o de captura puntual. En esos casos, abrirlos en `drawer-action`
  para mantener la página principal como listado/resumen.
- Si el formulario inyectado por drawer necesita JS propio, inicializarlo al
  evento `drawer:shown`; no depender de scripts que solo corren en el load de la
  página.

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
