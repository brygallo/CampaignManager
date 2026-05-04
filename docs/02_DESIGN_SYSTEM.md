# 02 · Design System – CampaignManager (Metronic v8 demo55)

> Mapa completo de la plantilla `metronic_html_v8.2.0_demo55` para que cualquier
> pantalla nueva del SuperAdmin se construya **reusando** tokens, componentes y
> assets ya disponibles. Pareja con `01_SUPERADMIN_GAP_ANALYSIS.md` y
> `03_SUPERADMIN_IMPLEMENTATION_PLAN.md`.

---

## 1. Identidad del producto

| Token | Valor | Uso |
|---|---|---|
| `brand_name` (context var) | `Control de Campaña` | Header, sidebar logo, login, `<title>` |
| `brand_icon` (static) | `assets/img/control-campana.svg` | Logo SVG sidebar/header (40px / 60px) |
| `default_theme` | `light` (overridable a `dark`/`system`) | `<html data-bs-theme>` |
| Tono | Cívico, operativo, sobrio | Microcopy en español formal |

---

## 2. Color system (tokens Metronic demo55)

### 2.1 Brand & estado (overrides demo55)

> Fuente: `metronic_html_v8.2.0_demo55/demo55/src/sass/components/_variables.custom.scss`

| Token SCSS | Hex | CSS var Bootstrap | Uso semántico |
|---|---|---|---|
| `$primary` | `#3E97FF` | `--bs-primary` | Botones de acción principal, links activos, foco de input |
| `$primary-active` | `#2884EF` | `--bs-primary-active` | Hover/active de botón primary |
| `$primary-light` | `#EEF6FF` | `--bs-primary-light` | Fondos de chips/pills, badges suaves |
| `$primary-light-dark` | `#212E48` | `--bs-primary-light-dark` | Variante dark mode del light |
| `$primary-inverse` | `#FFFFFF` | `--bs-primary-inverse` | Texto sobre fondo primary |
| `$success` | `#50CD89` | `--bs-success` | Estado activo, "creado", confirmaciones |
| `$success-light` | `#E8FFF3` | `--bs-success-light` | Badge `badge-light-success` |
| `$info` | `#7239EA` | `--bs-info` | Información secundaria, tags neutrales |
| `$info-light` | `#F8F5FF` | `--bs-info-light` | Fondos de cards informativos |
| `$warning` | `#FFC700` | `--bs-warning` | "En revisión", advertencias |
| `$warning-light` | `#FFF8DD` | `--bs-warning-light` | Alertas suaves |
| `$danger` | `#F1416C` | `--bs-danger` | Errores, eliminar, "inactivo" |
| `$danger-light` | `#FFF5F8` | `--bs-danger-light` | Fondos de error |

### 2.2 Escala de grises (idéntica a Bootstrap pero re-tonada)

| Token | Hex | Uso |
|---|---|---|
| `$gray-100` | `#F9F9F9` | Fondo body, cards alternos |
| `$gray-200` | `#F1F1F2` | Bordes ligeros, hover sutil |
| `$gray-300` | `#DBDFE9` | Bordes de input, separadores |
| `$gray-400` | `#B5B5C3` | Iconos placeholder |
| `$gray-500` | `#99A1B7` | `text-muted`, labels secundarios |
| `$gray-600` | `#78829D` | Iconos en estado normal |
| `$gray-700` | `#4B5675` | Texto secundario |
| `$gray-800` | `#252F4A` | Texto principal en dark mode |
| `$gray-900` | `#071437` | `body-color`, headings |

### 2.3 Mapa de uso por contexto

| Contexto UI | Clase Metronic | Color base |
|---|---|---|
| Botón primario | `btn btn-primary` | `#3E97FF` |
| Botón secundario | `btn btn-light-primary` | `#EEF6FF` + texto primary |
| Badge "activo" | `badge badge-light-success` | `#E8FFF3` + texto `#50CD89` |
| Badge "inactivo" | `badge badge-light-danger` | `#FFF5F8` + texto `#F1416C` |
| Badge "en proceso" | `badge badge-light-warning` | `#FFF8DD` + texto `#FFC700` |
| Card destacada | `card card-flush` | `#FFFFFF` + sombra `--bs-card-box-shadow` |
| Sidebar activo | `menu-link active` | bg `#EEF6FF` / texto `#3E97FF` |
| Timeline create | `text-success` (`#50CD89`) | `audit/timeline.html` |
| Timeline edit | `text-warning` (`#FFC700`) | `audit/timeline.html` |
| Timeline delete | `text-danger` (`#F1416C`) | `audit/timeline.html` |
| Bordes/inputs | `border` (`--bs-gray-300`) | `#DBDFE9` |
| Placeholder | `text-gray-500` | `#99A1B7` |

### 2.4 Dark mode

Todos los `*-light-dark` se aplican vía `[data-bs-theme="dark"]`. Mantener:

- Fondo body dark: `#1E1E2D` aprox. (Bootstrap dark default)
- Cards dark: `#1E1E2D` con `border-color: #323248`
- Text principal: `#CDCDDE`

> **Regla**: nunca usar hex puro en plantillas Django. Siempre token Metronic
> (`text-primary`, `bg-light-success`, `text-gray-700`, `border-gray-300`…).

---

## 3. Tipografía

| Token | Valor | Uso |
|---|---|---|
| `$font-family-sans-serif` | `Inter, Helvetica, sans-serif` | Global (cargada vía Google Fonts en `css.html`) |
| `$font-size-base` | `1rem` (≈ 13px raíz Metronic) | Body, párrafos |
| `$h1-font-size` | `1.75rem` | `page-heading` |
| `$h2-font-size` | `1.5rem` | Títulos de sección |
| `$h3-font-size` | `1.35rem` | Card title |
| `$h4-font-size` | `1.25rem` | Sub-section |
| `$h5-font-size` | `1.15rem` | Sub-card |
| `$h6-font-size` | `1.075rem` | Labels destacados |
| Helpers Metronic | `fs-1` (1.75rem) … `fs-9` (0.75rem), `fs-2x`, `fs-2qx`, `fs-3hx` | Modificadores rápidos |

### Pesos
- `fw-bold` 600 — labels destacados
- `fw-bolder` 700 — page heading, brand
- `fw-semibold` 500 — body principal
- `fw-normal` 400 — descripciones

### Microcopy (ES)
- Verbos en infinitivo en botones (“Guardar”, “Crear usuario”, “Eliminar permiso”).
- “Tú” formal, evitar “usted”.
- Mensajes de error específicos: “No se pudo guardar la campaña: <razón>.”

---

## 4. Espaciado y radios

| Token | Valor | Uso |
|---|---|---|
| `$spacer` | `1rem` (≈14px) | Base de la escala |
| Helpers | `m-0` … `m-20`, `gap-0` … `gap-20` | Spacing en flex/grid |
| `$border-radius-sm` | `0.55rem` | Inputs pequeños |
| `$border-radius` | `0.65rem` | Botones, inputs, chips |
| `$border-radius-lg` | `1rem` | Cards |
| `$border-radius-xl` | `1.25rem` | Modales, hero blocks |

---

## 5. Layout shell

```
┌─────────────────────────────────────────────────────────┐
│  app-header  (kt_app_header, sticky)                    │
│  ├─ search · theme switcher · user avatar dropdown      │
├──────────┬──────────────────────────────────────────────┤
│          │  app-toolbar (breadcrumbs + actions)         │
│ sidebar  ├──────────────────────────────────────────────┤
│ (250px)  │                                              │
│ menu-    │  app-content > container-fluid               │
│ accordion│  · alerts (django messages)                  │
│ + footer │  · content block                             │
│ user     │                                              │
│          │  app-footer                                   │
└──────────┴──────────────────────────────────────────────┘
```

Atributos clave en `<body>` (`base.html` ya configurados):

```
data-kt-app-header-fixed="true"
data-kt-app-sidebar-enabled="true"
data-kt-app-sidebar-fixed="true"
data-kt-app-sidebar-hoverable="true"
data-kt-app-sidebar-push-header="true"
data-kt-app-sidebar-push-toolbar="true"
```

### Anchuras
- Sidebar: `250px` (drawer en mobile)
- Container: `container-fluid` con max ≈ 1320px en xl
- Forms: `col-lg-8` o `col-lg-6` para evitar inputs demasiado anchos
- Modales superadmin: `modal-dialog modal-dialog-centered modal-lg`

---

## 6. Componentes Metronic mapeados al SuperAdmin

> Cada item indica **dónde lo usaremos**, **el HTML referencia** y la **clase
> Metronic principal**. Todos viven en
> `metronic_html_v8.2.0_demo55/demo55/dist/`.

### 6.1 Navegación
| Componente | Ref. demo55 | Clase | Uso CM |
|---|---|---|---|
| Sidebar accordion | `index.html` (sidebar) | `menu menu-column menu-rounded menu-sub-indention menu-accordion` | Refactor `sidebar_items.html` |
| Header search | `index.html` líneas 73-110 | `header-search` | Búsqueda global Fase 3 |
| Theme switcher | `index.html` user-menu | `data-kt-element="theme-mode-menu"` | Ya implementado |
| User dropdown | `index.html` líneas 220+ | `menu-content` con avatar | Header CM |
| Notifications drawer | `index.html` (campana) | `data-kt-menu-trigger` | Fase 4 |
| Breadcrumbs | `apps/user-management/users/list.html` | `breadcrumb breadcrumb-separatorless` | Implementado en `base.html` |

### 6.2 Listados
| Componente | Ref. demo55 | Clase | Uso CM |
|---|---|---|---|
| Toolbar de lista | `apps/user-management/users/list.html` | `card-header` con `card-toolbar` | `base_list.html` |
| Tabla con filtros | mismo | `table table-row-bordered table-row-gray-100 align-middle gs-0 gy-3` | Listas SuperAdmin |
| Datatables | `assets/plugins/custom/datatables/` | `dataTable` + KTDatatable | Audit list, User list |
| State filter cards | (custom SIM) | `card card-flush` con badge contador | **Portar** de SIM `state_filter_cards.html` |
| Stat cards (KPIs) | `widgets/statistics.html` | `card card-flush bgi-no-repeat bgi-position-top-end` | Inicio del SuperAdmin |
| Pagination | `paginator.html` | `pagination` Bootstrap + Metronic styling | Existe en CM |

### 6.3 Formularios
| Componente | Ref. demo55 | Clase / pattern | Uso CM |
|---|---|---|---|
| Form card | `apps/user-management/users/list.html` (modal create) | `card`, `card-header`, `card-body`, `card-footer` | `base_form.html` |
| Inputs solid | login | `form-control form-control-solid` | Login y campos sensibles |
| Inputs default | resto | `form-control` (border `--bs-gray-300`) | CRUDs |
| Radio buttons | `pages/team.html` | `form-check form-check-custom form-check-solid` | Filtros |
| Checkbox | misma | `form-check form-check-custom form-check-solid` | Filtros, m2m simple |
| Select2 | `assets/js/widgets.bundle.js` | `data-control="select2"` | Ya integrado |
| Flatpickr (date) | mismo | `form-control flatpickr-input` | `widgets/dateinput.html` |
| Tagify (m2m) | mismo | `data-tagify="true"` | Reusable en formsets |
| Repeater (formsets) | `assets/plugins/custom/formrepeater` | `data-repeater-list` + `data-repeater-item` | Ya en `tabular_formset_remove_add.html` |
| Wizard | `utilities/wizards/` | `stepper` | Para campaña/elección Fase 5 |
| Stepper | `utilities/wizards/horizontal.html` | `stepper-item` | Onboarding nuevo movimiento |

### 6.4 Detalle
| Componente | Ref. demo55 | Clase | Uso CM |
|---|---|---|---|
| Profile header (cover + tabs) | `apps/user-management/users/view.html` | `card card-flush` + `nav nav-tabs` | `user_detail.html`, `profile.html` |
| Two-column detail | `account/overview.html` | `row` con `col-xl-3` (sidebar) + `col-xl-9` (contenido) | Perfil |
| Avatar grupos | `account/overview.html` | `symbol-group symbol-hover` | Group detail |
| Properties list | `account/overview.html` | `dl` con `row` y `col-lg-4`/`col-lg-8` | Detail sections |

### 6.5 Feedback
| Componente | Ref. demo55 | Clase | Uso CM |
|---|---|---|---|
| Alert dismissible | `index.html` muestra | `alert alert-{level} alert-dismissible` | Ya en `base.html` 51-65 |
| Toast | `assets/js/widgets.bundle.js` | SweetAlert2 (ya integrado) | Migrar de Lobibox (commit `d7d2aee`) |
| Modal confirm delete | `apps/user-management/users/list.html` | `modal modal-dialog modal-dialog-centered` | `base_confirm_delete.html` |
| Empty state | `apps/file-manager/folders.html` | Card con SVG ilustración + CTA | Audit/timeline empty (ya hay) |
| Skeleton placeholder | `assets/js/components/blockui.js` | `data-bs-toggle="blockui"` | Loaders en datatables |
| Spinner | login | `indicator-progress` con `spinner-border` | Botones submit |

### 6.6 Iconografía
- **KeenIcons** — cargados en `assets/plugins/global`. Nomenclatura `<i class="ki-outline ki-<nombre>">`.
- Variantes: `ki-outline`, `ki-duotone` (con `<span>` por path), `ki-filled`, `ki-solid`.
- **Mapa SuperAdmin** (definitivo, usar estos):

| Concepto | Icono |
|---|---|
| Inicio | `ki-home-2` |
| Sistema | `ki-setting-2` |
| Usuarios | `ki-profile-circle` |
| Grupos / roles | `ki-people` |
| Permisos | `ki-shield-tick` |
| Auditoría | `ki-time` |
| Reglas | `ki-rule` |
| Campañas | `ki-flag` |
| Elecciones | `ki-element-equal` |
| Candidatos | `ki-user-tick` |
| Movimientos políticos | `ki-abstract-26` |
| Cargos | `ki-medal-star` |
| Editar | `ki-pencil` |
| Eliminar | `ki-trash` |
| Crear | `ki-plus-square` |
| Ver detalle | `ki-eye` |
| Filtrar | `ki-filter` |
| Buscar | `ki-magnifier` |
| Exportar | `ki-exit-down` |
| Importar | `ki-entrance-right` |
| Cerrar sesión | `ki-exit-right` |
| Notificaciones | `ki-notification-on` |
| Ajustes | `ki-setting-3` |
| Información | `ki-information-5` |
| Éxito | `ki-check-circle` |
| Error | `ki-cross-circle` / `ki-shield-cross` |

> **Regla**: prohibir `fa-*` (Font Awesome). Si se encuentra (ej.
> `audit/timeline.html` ya usa `ki-outline`, pero `sim/templates/.../user_list.html`
> aún tiene `fas fa-pen`), reemplazar al portar.

---

## 7. Bundles JS / CSS disponibles

> Path base CM: `static/assets/`

| Bundle | Path | Carga global |
|---|---|---|
| `plugins.bundle.css` | `assets/plugins/global/plugins.bundle.css` | ✅ login + base |
| `style.bundle.css` | `assets/css/style.bundle.css` | ✅ |
| `plugins.bundle.js` | `assets/plugins/global/plugins.bundle.js` | ✅ |
| `scripts.bundle.js` | `assets/js/scripts.bundle.js` | ✅ |
| `widgets.bundle.js` | `assets/js/widgets.bundle.js` | bajo demanda (forms con select2/flatpickr) |
| `custom/datatables/datatables.bundle.css/js` | `assets/plugins/custom/datatables/` | bajo demanda en listas grandes |
| `custom/fullcalendar/*` | `assets/plugins/custom/fullcalendar/` | módulo agenda Fase 5 |
| `custom/formrepeater` | `assets/plugins/custom/formrepeater/` | formsets dinámicos |

> Nuevas vistas → cargar plugins **solo en bloques** `{% block extra_css %}` /
> `{% block extra_js %}`, no globalmente. Ya el patrón está en `base/css.html`/`js.html`.

---

## 8. Patrones de página (página "tipo")

Cada vista del SuperAdmin debe seguir uno de estos 6 patrones. Cualquier
implementación nueva referencia uno por nombre.

### P1 — Module landing (grid)
- Layout: `row > col-md-4 col-lg-3` cards
- Card: `card card-flush hoverable` con `card-body` + icono `ki-{module}` 4x + título + descripción + link
- Ejemplo: `templates/superadmin/module_list.html` (a crear, ver SIM ref)

### P2 — Lista CRUD
- Toolbar: page-heading + `Crear` button
- Card: `card-header` con búsqueda + filtros, `card-body p-0` con tabla, `card-footer` con paginación
- Acciones por fila: dropdown `data-kt-menu-trigger="click"` con Editar/Ver/Eliminar
- Empty state: ilustración `assets/media/illustrations/sketchy-1/5.png` + CTA

### P3 — Form CRUD
- 1 columna `col-xl-8 mx-auto` (max ≈ 800px)
- Card por sección con `card-header` + `card-body`
- Footer pegajoso con `Cancelar` (btn-light) + `Guardar` + `Guardar y continuar` + `Guardar y agregar otro`

### P4 — Detail con tabs
- Hero: `card mb-5 mb-xl-10` con avatar + nombre + meta info
- Tabs: `nav nav-tabs nav-line-tabs nav-stretch fs-6 border-0`
- Cada tab → card por sección

### P5 — Matriz (permisos × app/modelo)
- Card con tabla scrollable
- Header sticky, primera columna sticky
- Checkboxes `form-check form-check-custom form-check-solid`
- Footer con resumen contadores + Guardar

### P6 — Timeline (audit)
- Lista filtrable arriba (state_filter_cards)
- Body: `timeline timeline-border-dashed` (ya en `audit/timeline.html`)
- Item: icono coloreado por acción + meta + diff de campos en grid de 2 col

---

## 9. Reglas de coherencia (do / don't)

| ✅ Hacer | ❌ Evitar |
|---|---|
| Usar tokens (`text-primary`, `bg-light-success`) | Hex en plantillas |
| `ki-outline ki-*` para todos los iconos | `fa-*`, `bi-*`, SVG inline |
| `fs-{n}`/`fw-{...}` para tamaños/pesos | `style="font-size:..."` |
| Botones acción primaria a la derecha en footers | Mezclar orden de acciones |
| Plurales y mayúsculas consistentes en encabezados | "USUARIO" en uppercase salvo eyebrows `text-uppercase fs-7` |
| Cards con `border-radius` `lg` | Cards sin radio o cuadradas |
| Mensajes Django como `alert-success/danger/...` (ya mapeado) | Toasts para errores de validación de form (poner inline) |
| Confirmar deletes con modal | Confirmar con `confirm()` JS nativo |
| Dark mode con tokens automáticos | Estilos forzados por theme |

---

## 10. Estructura de archivos resultante (después del plan)

```
templates/
├── base/
│   ├── base.html              ✅ existe
│   ├── header.html            ✅ existe
│   ├── sidebar.html           ✅ existe (refactorar accordion)
│   ├── sidebar_items.html     ✅ existe
│   ├── footer.html            ✅ existe
│   ├── css.html / js.html     ✅ existe
│   ├── base_list.html         ✅ existe (revisar P2)
│   ├── base_form.html         ✅ existe (revisar P3)
│   ├── base_detail.html       ✅ existe (revisar P4)
│   ├── base_confirm_delete.html ✅
│   ├── _field.html            ✅
│   ├── paginator.html         ✅
│   └── includes/              ⬅ NUEVO
│       ├── stat_card.html     ⬅ portar
│       ├── m2m_pills.html     ⬅ portar
│       └── state_filter_cards.html ⬅ portar
├── superadmin/                ⬅ NUEVO
│   └── module_list.html       ⬅ Patrón P1
├── authentication/            ✅ existe
│   ├── profile.html           ⚠ rehacer P4 con tabs
│   ├── user_detail.html       ⚠ rehacer P4
│   ├── user_form.html         ⬅ NUEVO P3
│   ├── permission_form.html   ⬅ NUEVO P5 (matriz por usuario)
│   ├── group_form.html        ⬅ NUEVO P3 + P5 (form + matriz)
│   ├── group_detail.html      ⚠ rehacer P4
│   ├── permission_detail.html ⚠ rehacer P4
│   ├── password_form.html     ⬅ NUEVO P3 (cambiar contraseña)
│   ├── password_reset.html    ⬅ NUEVO (auth-blank P3)
│   ├── password_reset_done.html ⬅
│   ├── password_reset_complete.html ⬅
│   ├── password_reset_done_complete.html ⬅
│   ├── email/
│   │   └── password_reset_email.html ⬅ NUEVO
│   └── components/            ✅ existe
├── audit/
│   ├── timeline.html          ✅ existe
│   └── trace_list.html        ⬅ NUEVO P2 + filtros
├── widgets/                   ⚠ ampliar
│   ├── (existentes)
│   ├── timeinput.html         ⬅ portar
│   ├── radioinput.html        ⬅ portar
│   ├── fileinput.html         ⬅ portar
│   ├── json.html              ⬅ portar
│   ├── checkboxselectmultiple.html ⬅ portar
│   ├── base_input.html        ⬅ portar
│   └── textsearch.html        ⬅ portar
├── errors/                    ⚠ rehacer Metronic
│   ├── 403.html               (auth/general/account-deactivated.html)
│   ├── 404.html               (auth/general/error-404.html)
│   └── 500.html               (auth/general/error-500.html)
└── registration/
    └── login.html             ✅ existe (refinar)
```

---

## 11. Cómo "agarrar" un componente nuevo

1. Buscar la página de referencia más cercana en `metronic_html_v8.2.0_demo55/demo55/dist/` (sección 6 lo lista por componente).
2. Abrir esa página en navegador o `Read`. Copiar el bloque exacto.
3. Reemplazar:
   - rutas relativas (`assets/...`) por `{% static 'assets/...' %}`
   - textos en inglés por microcopy ES
   - datos hardcoded por context vars Django
   - `<a href="...">` por `{% url '...' %}`
4. Pasar la plantilla por las **reglas Sección 9**.
5. Validar dark mode (`Cmd/Ctrl + D` switch).
6. Validar responsive (sidebar drawer en `<992px`).

---

## 12. Tokens en CSS variables (referencia rápida runtime)

Las versiones compiladas inyectan en `:root`:

```css
--bs-primary: #3E97FF;
--bs-success: #50CD89;
--bs-info: #7239EA;
--bs-warning: #FFC700;
--bs-danger: #F1416C;
--bs-gray-100..900: ...
--bs-body-bg: #FFFFFF;
--bs-body-color: #071437;
--bs-border-radius: .65rem;
--bs-border-radius-lg: 1rem;
```

Útil para custom CSS puntual (`color: var(--bs-primary);`).

---

## 13. Referencias rápidas

- Plantilla viva: `metronic_html_v8.2.0_demo55/demo55/dist/`
  - Listado usuarios → `apps/user-management/users/list.html`
  - Detalle usuario → `apps/user-management/users/view.html`
  - Roles → `apps/user-management/roles/list.html`, `view.html`
  - Permisos matrix → `apps/user-management/permissions.html`
  - Account tabs → `account/overview.html`, `settings.html`, `security.html`, `activity.html`
  - Auth split layout → `authentication/layouts/corporate/sign-in.html`
  - Auth reset → `authentication/layouts/corporate/reset-password.html`, `new-password.html`
  - 404/500/Deactivated → `authentication/general/error-404.html`, `error-500.html`, `account-deactivated.html`
  - Wizard → `utilities/wizards/horizontal.html`
- Tokens fuente: `metronic_html_v8.2.0_demo55/demo55/src/sass/components/_variables.custom.scss`
- KeenIcons demo: abrir cualquier página y buscar `class="ki-`

→ Implementación priorizada en `03_SUPERADMIN_IMPLEMENTATION_PLAN.md`.
