# 03 · SuperAdmin – Plan de Implementación

> Plan ejecutable y priorizado para cerrar el GAP descrito en
> `01_SUPERADMIN_GAP_ANALYSIS.md`, aplicando los tokens y patrones del
> `02_DESIGN_SYSTEM.md`.
>
> **Branch sugerido**: `feature/superadmin-foundation`
> **Estado base**: `main` @ commit `78b692c` (2026-05-04).

---

## 0. Reglas operativas del plan

1. **Una plantilla nueva = un patrón** del Design System (P1…P6) explícito.
2. **Cero hex hardcodeado**, cero `fa-*`. Solo tokens Metronic + `ki-outline`.
3. **Cada fase termina con QA**: GET de cada URL nueva responde 200 (o 302 a login si LoginRequired).
4. **Tests mínimos por fase**: smoke test de carga (no se rompe template) + permisos.
5. **Commits atómicos** por sub-tarea, mensaje en estilo del repo (verbos en inglés, cuerpo descriptivo).

---

## 1. Fases y prioridades

| Fase | Objetivo | Bloqueante para | Estimación | Prioridad |
|---|---|---|---|---|
| **F1** | Landing del SuperAdmin (`module_list`) + integración menú | F2/F3 | 0.5 día | 🔴 Alta |
| **F2** | Authentication completo (reset, change, matriz permisos) | F4 | 2 días | 🔴 Alta |
| **F3** | CRUDs UI dedicados (User/Group/Permission) | F4 | 1.5 días | 🟠 Media |
| **F4** | Auditoría: lista filtrable + reglas | — | 1.5 días | 🟠 Media |
| **F5** | Perfil con tabs + páginas account | — | 1 día | 🟢 Baja |
| **F6** | Pulido: errores, sidebar accordion, búsqueda, panel ajustes | — | 1.5 días | 🟢 Baja |
| **F7** | Paridad widgets + helpers de includes (stat_card, m2m_pills) | refactor formularios | 1 día | 🟢 Baja |

> **Ruta crítica**: F1 → F2 → F3 → F4. Total ≈ 5.5 días para SuperAdmin operativo.

---

## 2. Fase 1 — Landing del SuperAdmin

**Meta**: al iniciar sesión un staff aterriza en una grid con todos los módulos
registrados (campañas + sistema + auditoría) y en un click va a su listado.

### 2.1 Archivos

| Acción | Ruta | Notas |
|---|---|---|
| Crear | `templates/superadmin/module_list.html` | Patrón **P1** (grid de cards). Adaptar el de `sim/templates/superadmin/module_list.html` a Metronic v8 con `card card-flush hoverable` + `ki-outline` por icono |
| Crear | `core/views.py::SuperAdminLandingView` | `LoginRequiredMixin`. Usa `superadmin.shortcuts` para iterar sites registrados, agruparlos por la sección de `menu.yaml` (`Campañas`, `Sistema`) y resolver URL `list`. Devuelve `module_list.html` |
| Modificar | `core/urls.py` | Añadir `path("admin-panel/", SuperAdminLandingView.as_view(), name="superadmin_home")` |
| Modificar | `templates/base/sidebar.html` | Item “Panel admin” con `ki-element-11` antes de los grupos |
| Modificar | `templates/home.html` | Si user.is_staff redirigir al panel; si no, mantener inicio operativo |

### 2.2 Diseño UI (P1)

```
[ Page heading: "Panel de administración" ]

┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  ki-flag 4x      │  │ ki-element-equal │  │ ki-people 4x     │
│                  │  │                  │  │                  │
│  Campañas        │  │  Elecciones      │  │  Usuarios        │
│  Gestiona cam... │  │  Periodos elec...│  │  Cuentas, roles  │
│                  │  │                  │  │                  │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

- Card: `card card-flush border-hover-primary cursor-pointer`
- Hover: elevación con `shadow-sm` → `shadow`
- Icono: `symbol symbol-50px bg-light-primary` con `ki-outline ki-{icon} fs-2x text-primary`

### 2.3 QA F1
- [ ] Ruta `/admin-panel/` responde 200 para staff.
- [ ] Cada card linkea a la URL `list` registrada.
- [ ] Solo módulos donde el usuario tiene permiso `view_*` aparecen.

---

## 3. Fase 2 — Authentication completo

**Meta**: cubrir el ciclo completo de autenticación + matriz de permisos por
usuario.

### 3.1 Sub-tareas

#### F2.1 — Vistas Django (URLs y views)
| Acción | Archivo | Detalle |
|---|---|---|
| Modificar | `apps/authentication/urls.py` | Añadir `password_reset`, `password_reset_done`, `password_reset_confirm`, `password_reset_complete`, `password_change`, `user_permissions` |
| Modificar | `apps/authentication/views.py` | `UserPermissionView(UpdateView)` (matriz) + `PasswordChangeView` (mensaje + redirect a perfil). Adaptar de `sim/apps/authentication/views.py:23-107` |
| Crear | `apps/authentication/forms.py::UserPermissionForm` | Si no existe |

#### F2.2 — Plantillas auth (Patrón blank/auth-bg10)
Adopta el layout split de `templates/registration/login.html` (CM ya lo tiene)
para todas las plantillas de auth.

| Crear | Plantilla | Patrón demo55 |
|---|---|---|
| ⬅ | `templates/registration/password_reset.html` | `authentication/layouts/corporate/reset-password.html` |
| ⬅ | `templates/registration/password_reset_done.html` | `authentication/general/password-confirmation.html` |
| ⬅ | `templates/registration/password_reset_confirm.html` | `authentication/layouts/corporate/new-password.html` |
| ⬅ | `templates/registration/password_reset_complete.html` | `authentication/general/welcome.html` |
| ⬅ | `templates/authentication/email/password_reset_email.html` | Email plain HTML (logo + saludo + botón + link) |

#### F2.3 — Cambio de contraseña (autenticado)
| Crear | `templates/authentication/password_form.html` | Patrón **P3** dentro de `base.html`. Form con campo actual + nuevo + confirmación. Validación inline. Botón Guardar a la derecha. |

#### F2.4 — Matriz de permisos por usuario (Patrón **P5**)
| Crear | `templates/authentication/permission_form.html` |

Plantilla:
- Hero pequeño: avatar usuario + nombre + email + botón “Volver al detalle”.
- Card con tabla scrollable horizontal.
  - Header sticky: `[App / Modelo] [Ver] [Crear] [Editar] [Eliminar] [Otros]`.
  - Filas agrupadas por app, sub-agrupadas por modelo.
  - Cada acción es `<input type="checkbox" name="perm_<codename>" value="<content_type_id>">` con `form-check-input`.
  - Indicador "heredado de grupo X" → badge `badge-light-info` deshabilitando edición o solo informativo.
- Toolbar superior: contador `<span class="fs-2 fw-bolder text-primary">{{ count }}</span> de {{ total }} permisos`.
- Botón "Marcar todos en este modelo" (JS, opcional).
- Footer pegajoso: `Cancelar` | `Guardar permisos`.

### 3.5 QA F2
- [ ] Flujo email reset → click link → set nueva pass → login funciona.
- [ ] `/auth/user/password/change/` actualiza y muestra toast verde.
- [ ] Matriz de permisos persiste correctamente (POST modifica `user.user_permissions`).
- [ ] Acceso a matriz solo `is_staff`.

---

## 4. Fase 3 — CRUDs UI dedicados

**Meta**: reemplazar las vistas genéricas de `BaseSite` para User/Group/Permission
con plantillas que apliquen P2/P3/P4 con datos contextuales.

### 4.1 User (P3 form + P4 detail)
| Acción | Archivo |
|---|---|
| Crear | `templates/authentication/user_form.html` (P3): cards "Datos de acceso" / "Información personal" / "Asignación de grupos" |
| Reescribir | `templates/authentication/user_detail.html` (P4 con tabs): Overview, Permisos (matriz inline), Auditoría (timeline filtrado por `user`) |
| Modificar | `apps/authentication/sites.py` → `form_template_name`, `detail_template_name` |

### 4.2 Group (P3 + P5)
| Acción | Archivo |
|---|---|
| Crear | `templates/authentication/group_form.html`: nombre + matriz permisos (mismo componente F2.4 reutilizable) |
| Reescribir | `templates/authentication/group_detail.html` (P4): info + permisos + usuarios asignados (`components/users_list.html` ya existe) |

### 4.3 Permission (P4 detail)
| Acción | Archivo |
|---|---|
| Reescribir | `templates/authentication/permission_detail.html` (P4): meta del permiso + usuarios con permiso directo + usuarios con permiso vía grupo (`PermissionUsersMixin` ya provee data) |

### 4.4 QA F3
- [ ] User create/update con grupos asignados.
- [ ] Group create/update con permisos asignados.
- [ ] Detail de Permission lista usuarios.
- [ ] Visual idéntico entre crear y editar.

---

## 5. Fase 4 — Auditoría

### 5.1 Lista de Trazas (P2)
| Crear | `templates/audit/trace_list.html` |

- Toolbar: page-heading "Auditoría" + dropdown "Exportar CSV" (futuro).
- Card-header con filtros: usuario (select2), modelo (`content_type`), acción (radio button group: todas/crear/editar/eliminar), rango de fecha (`flatpickr` range).
- Card-body: tabla `dataTable` con columnas `Cuándo · Usuario · Modelo · Acción · IP · Cambios`.
- Card-footer: paginación.
- Botón "Ver detalle" abre modal con `audit/timeline.html` filtrado a esa traza.

### 5.2 Detalle de traza
- Reusar `audit/timeline.html` (ya existe). Embeber en `base_detail.html` cuando se accede a `/auditoría/<id>/`.

### 5.3 Reglas de auditoría (P3)
| Crear | `templates/tracing/rule_form.html` |
- Form simple con `content_type` + 3 toggles (`check_create`, `check_edit`, `check_delete`) + `is_active`.
- Detail: P4 con campos.

### 5.4 QA F4
- [ ] Lista filtra por usuario y rango.
- [ ] Detalle muestra diff con `processed_traces`.
- [ ] Rule activable/desactivable.

---

## 6. Fase 5 — Perfil del usuario actual (P4 con tabs)

| Reescribir | `templates/authentication/profile.html` |

Estructura demo55 `account/`:

```
[ Hero card ]
  avatar 100px · Nombre · email · badge rol · botón "Editar perfil"

[ Tabs ]
  [ Overview ] [ Seguridad ] [ Actividad ] [ Permisos ]

  Overview: card "Información personal" + card "Equipo (grupos)"
  Seguridad: cambiar contraseña (link a F2.3) + sesiones activas + 2FA (placeholder)
  Actividad: timeline (audit) últimos 30 días
  Permisos: usar componente F2.4 en modo solo lectura
```

### QA F5
- [ ] Cualquier usuario logueado accede solo a su perfil.
- [ ] Tab Permisos muestra origen (directo / grupo X).

---

## 7. Fase 6 — Pulido

### 7.1 Errores Metronic
| Reescribir | `templates/errors/403.html` (auth/general/account-deactivated.html) |
| Reescribir | `templates/errors/404.html` (auth/general/error-404.html) |
| Reescribir | `templates/errors/500.html` (auth/general/error-500.html) |

### 7.2 Sidebar accordion
- Refactor `templates/base/sidebar_items.html`: cuando un grupo del `menu.yaml` tiene >5 hijos o tiene anidación, generar `menu-accordion`.

### 7.3 Búsqueda global (mínimo viable)
- Endpoint `GET /buscar/?q=...` que retorna JSON con sites + objetos coincidentes.
- Conectar en header (`#kt_header_search`). Por ahora limitar a User/Group/Trace + Campaign/Election/Candidate.

### 7.4 Settings / user panels (drawer)
- Adaptar `metronic_html_v8.2.0_demo55/demo55/dist/index.html` (settings panel + user panel) a `templates/base/settings_panel.html` + `user_panel.html`.
- Toggle desde header.

### QA F6
- [ ] 404 estilizada. 500 estilizada. 403 estilizada.
- [ ] Sidebar plegable mantiene estado (localStorage).
- [ ] Buscador devuelve resultados consistentes.

---

## 8. Fase 7 — Paridad de widgets + includes

### 8.1 Widgets faltantes (de `sim/templates/widgets/`)
- `timeinput.html`
- `radioinput.html`
- `fileinput.html`
- `json.html`
- `checkboxselectmultiple.html`
- `base_input.html`
- `textsearch.html`

Portar uno por uno; revisar JS asociado (ej. flatpickr para `timeinput`).
Registrar en `core/widgets.py` si SIM lo hace.

### 8.2 Includes reutilizables
- `templates/base/includes/stat_card.html` (KPI card)
- `templates/base/includes/m2m_pills.html` (chips de relaciones)
- `templates/base/includes/state_filter_cards.html` (filtros visuales por estado en listas)

### QA F7
- [ ] Cada widget renderiza sin error en un form de prueba.
- [ ] `stat_card` usado en al menos un listado (ej. trace_list).

---

## 9. Cobertura de tests sugerida

| Test | Ámbito | Marca |
|---|---|---|
| `test_superadmin_landing_renders` | F1 | smoke |
| `test_password_reset_flow` | F2 | integration |
| `test_user_permission_matrix_post_persists` | F2 | integration |
| `test_user_form_groups_assignment` | F3 | integration |
| `test_audit_list_filters_by_user` | F4 | integration |
| `test_profile_tabs_load_for_authenticated_user` | F5 | smoke |
| `test_404_renders_metronic_template` | F6 | smoke |

---

## 10. Checklist de aceptación global (Definition of Done)

- [ ] Cualquier vista nueva referencia un patrón del DS (P1…P6) en su comentario superior `{# Pattern P{n} #}`.
- [ ] No hay literales hex en plantillas (`grep -r "#[0-9A-Fa-f]\{6\}" templates/` vacío salvo en login bg).
- [ ] No hay `fa-*` (`grep -r "fa-" templates/` vacío).
- [ ] Dark mode probado en cada vista nueva.
- [ ] Responsive ≤768px (sidebar drawer, tablas con scroll-x).
- [ ] Mensajes Django se mapean a `alert-{level}` (success/danger/warning/info).
- [ ] Botón primario siempre a la derecha en footers de form.
- [ ] Acceso protegido por `LoginRequiredMixin` o `PermissionRequiredMixin` cuando aplica.
- [ ] Comentario superior de cada plantilla nueva con: patrón, propósito y ref demo55.

---

## 11. Quick-start sugerido

```bash
git checkout -b feature/superadmin-foundation
# F1 — landing
git add templates/superadmin/module_list.html core/views.py core/urls.py templates/base/sidebar.html
git commit -m "Add SuperAdmin landing module list with Metronic v8 card grid"

# F2 — authentication completo
# (commits separados: views/urls, password reset templates, password change, user permission matrix)

# F3 — CRUDs UI
# (commits separados por modelo)

# ...
```

---

## 12. Archivos referencia rápidos

- **GAP funcional** → `docs/01_SUPERADMIN_GAP_ANALYSIS.md`
- **Tokens, paleta, componentes** → `docs/02_DESIGN_SYSTEM.md`
- **Plantilla viva** → `metronic_html_v8.2.0_demo55/demo55/dist/`
- **Proyecto referencia (SIM)** → `/Users/usuario/gad/sim/`
- **Bundle CSS/JS Metronic** → `static/assets/`
