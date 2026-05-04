# 01 · SuperAdmin – Análisis GAP SIM vs CampaignManager

> Comparación funcional + UI/UX entre el módulo **SuperAdmin** del proyecto referencia
> `/Users/usuario/gad/sim` y el estado actual de `/Users/usuario/gad/CampaignManager`
> (rama `main`, 2026-05-04). Pareja con `02_DESIGN_SYSTEM.md` y `03_SUPERADMIN_IMPLEMENTATION_PLAN.md`.

---

## 1. Resumen ejecutivo

| Eje | Estado SIM | Estado CM | Brecha |
|---|---|---|---|
| Listado dinámico de módulos (`module_list`) | ✅ Card grid con SVG | ❌ No existe | **Alta** |
| Login + Reset password (4 vistas) | ✅ Plantillas Metronic v7 | ⚠️ Solo login custom | **Alta** |
| User CRUD vía superadmin | ✅ `UserSite` + form/detail dedicados | ✅ Registrado, faltan templates dedicados | **Media** |
| Group CRUD | ✅ `GroupSite` + `group_form`/`detail` | ⚠️ Detail sí, form no | **Media** |
| Permission CRUD/lectura | ✅ Listado + detail + matriz | ⚠️ Lista + detail mínimos | **Media** |
| Edición de permisos por usuario (`UserPermissionView`) | ✅ Vista dedicada con matriz | ❌ No existe | **Alta** |
| Cambio de contraseña (perfil) | ✅ `PasswordChangeView` Metronic | ❌ No existe | **Alta** |
| Auditoría (Trace timeline + filtros) | ✅ `TraceSite` + `audit/timeline.html` | ⚠️ Timeline existe, falta listado y filtros | **Media** |
| Reglas de auditoría (`Rule`) | ✅ CRUD completo | ⚠️ Registrado en site, falta UI | **Media** |
| Mi perfil + tabs (overview, security, activity) | ✅ Esqueleto con tabs | ⚠️ `profile.html` mínimo | **Alta** |
| Layout base (header, sidebar, panels) | ✅ Header móvil, settings panel, scrolltop | ✅ Header + sidebar Metronic v8 | **Baja** (mejor que SIM) |
| Componentes de form (formset, fieldset) | ✅ 7 plantillas | ✅ 7 plantillas (paridad) | **OK** |
| Widgets (date, time, ckeditor, json…) | ✅ 13 widgets | ⚠️ 6 widgets | **Media** |

**Lectura rápida:** la base layout-Metronic-v8 de CM está más moderna que la v7 de SIM,
pero al SuperAdmin de CM le faltan **vistas funcionales clave** (matriz de permisos
por usuario, password change, módulos, reset, perfil con tabs) y **plantillas
visuales propias** para `User/Group/Permission` cuando se renderizan dentro del
superadmin.

---

## 2. Mapa funcional comparativo

### 2.1 Authentication app

| Vista / template | SIM | CampaignManager | Acción |
|---|---|---|---|
| `auth/login` | `templates/authentication/login.html` (split layout) | `templates/registration/login.html` (split layout) | ✅ Paridad — refinar con tokens design system |
| `auth/logout` | `LogoutView` | `views.logout_view` | ✅ |
| `auth/password_reset` | `templates/authentication/reset.html` | ❌ | **Crear** |
| `auth/password_reset_done` | `reset_password_done.html` | ❌ | **Crear** |
| `auth/password_reset_confirm` | `reset_password_complete.html` | ❌ | **Crear** |
| `auth/password_reset_complete` | `reset_password_done_complete.html` | ❌ | **Crear** |
| `auth/password_change` | `user/password_form.html` + `PasswordChangeView` | ❌ | **Crear** |
| `authentication/email/password_reset_email.html` | ✅ HTML email | ❌ | **Crear** |
| `auth/user_permissions` (matriz) | `user/permission_form.html` + `UserPermissionView` | ❌ | **Crear** (alta prioridad) |
| `auth/employee_data` (AJAX) | ✅ | ❌ (no aplica, no hay employees) | Skip |

### 2.2 SuperAdmin shell

| Vista / template | SIM | CampaignManager | Acción |
|---|---|---|---|
| `templates/superadmin/module_list.html` | Grid de cards con SVG | ❌ | **Crear** (entrada al panel) |
| `templates/base/base.html` | Layout v7 | Layout v8 | ✅ (CM mejor) |
| `templates/base/sidebar.html` | Vertical menu v7 | Vertical menu v8 + footer user | ✅ (CM mejor) |
| `templates/base/header.html` | Top bar + search + user panel | Top bar + search disabled + user dropdown | ✅ |
| `templates/base/header_mobile.html` | ✅ | ❌ (responsive integrado en header) | OK |
| `templates/base/footer.html` | ✅ | ✅ | OK |
| `templates/base/user_panel.html` (drawer) | ✅ | ❌ | **Opcional** (Fase 3) |
| `templates/base/settings_panel.html` (theme builder) | ✅ | ❌ | **Opcional** (Fase 3) |
| `templates/base/notifications/*` | ✅ | ❌ | **Opcional** (Fase 4) |

### 2.3 CRUDs registrados (`@register`)

| Modelo | SIM | CampaignManager | Falta UI dedicada |
|---|---|---|---|
| `authentication.User` | `UserSite` con form/detail dedicado | `UserSite` registrado | `user_form.html`, `user_detail.html` (existe vacío) |
| `auth.Group` | `GroupSite` con permission matrix | `GroupSite` registrado | `group_form.html` con matriz |
| `auth.Permission` | Matriz + listas de usuarios | `PermissionSite` registrado | `permission_detail.html` (existe vacío) |
| `tracing.Trace` | Lista + detalle con timeline | `TraceSite` registrado | Lista propia + filtros + timeline reusable |
| `tracing.Rule` | CRUD completo | `RuleSite` registrado | Form/detail propios |

### 2.4 Componentes de UI reutilizables

| Componente | SIM | CM | Notas |
|---|---|---|---|
| `components/permissions_list.html` (matriz por app/modelo) | ✅ | ✅ | Mantener |
| `components/users_list.html` (chips de usuarios) | ✅ | ✅ | Mantener |
| `components/permissions.html` (selector visual) | ✅ | ❌ | **Crear** |
| `audit/timeline.html` | ✅ | ✅ | Reusar |
| `forms/*` (formset, fieldset, formgroup) | 7 | 7 | OK |
| `widgets/*` | 13 (incluye ckeditor, json, time, file, m2m_pills) | 6 | Faltan: `fileinput`, `timeinput`, `radioinput`, `json`, `checkboxselectmultiple`, `base_input`, `textsearch` |
| `base/includes/state_filter_cards.html` | ✅ | ❌ | **Portar** (filtros visuales por estado) |
| `base/includes/m2m_pills.html` | ✅ | ❌ | **Portar** |
| `base/includes/stat_card.html` | ✅ | ❌ | **Portar** (KPIs en listas) |

---

## 3. Análisis UI/UX

### 3.1 Fortalezas actuales (CM)

1. **Stack Metronic v8 moderno**: `data-kt-app-*`, dark mode con `data-bs-theme`,
   `app-sidebar` hoverable, fonts `Inter`. SIM aún en v7 (`aside`, `kt_body`).
2. **Layout limpio**: separación `app-header / app-sidebar / app-main` con
   `container-fluid`. El usuario no se pierde.
3. **Breadcrumbs + page-heading** ya presentes en `base.html` (líneas 67-98).
4. **Theme switcher** light/dark/system funcional en header.
5. **Toolbar slot** (`{% block breadcrumb_actions %}`) para botones contextuales.
6. **Mensajes Django** ya con estilo `alert-{tag}` + iconos KI (líneas 51-65).

### 3.2 Debilidades / oportunidades

| # | Problema | Impacto | Solución propuesta |
|---|---|---|---|
| U1 | No hay landing del SuperAdmin (al hacer login se ve `home`, no un panel admin) | Alto — el operador no encuentra los módulos | `module_list.html` reescrito con cards Metronic v8 + iconos KI por módulo |
| U2 | Buscador global deshabilitado (placeholder “Buscar...”) | Medio — desperdicia espacio | Implementar búsqueda contra Trace + sites registrados, o eliminar el input hasta tenerlo |
| U3 | Sidebar carece de **secciones colapsables** (`menu-accordion`) que SIM sí usa | Medio — al crecer el menú se vuelve plano | Refactor `sidebar_items.html` con `menu-accordion` Metronic |
| U4 | Sin **breadcrumbs persistentes** ni `kt_app_toolbar` separado | Bajo — pero rompe el patrón Metronic | Migrar el bloque `{% block toolbar %}` a `kt_app_toolbar` siguiendo demo55 |
| U5 | Matriz de permisos ausente → operador edita uno por uno desde admin Django | Alto — fricción operativa | Vista `UserPermissionView` (replicar de SIM) con matriz `app × modelo × acción` |
| U6 | Audit timeline no filtrable por usuario/fecha/acción | Medio | Lista superadmin con `state_filter_cards` + datatables + timeline lateral |
| U7 | Login no usa el `auth-bg` real de Metronic v8 | Bajo | Adoptar `auth/bg10.jpeg` + tagline coherente |
| U8 | Errores 403/404/500 son muy planos | Bajo | Plantillas Metronic `general/error-404.html`, `error-500.html`, `account-deactivated.html` |
| U9 | `profile.html` es una sola página sin pestañas | Medio | Layout pestañas: Overview · Seguridad · Actividad · Permisos (estilo demo55 `account/`) |
| U10 | Sin paneles drawer (settings, user) que la base ya soporta | Bajo | Fase 3 |
| U11 | Iconografía mezcla `ki-outline` con `fas fa-` (timeline.html) | Bajo | Estandarizar 100% en KeenIcons (`ki-outline ki-*`) |

### 3.3 Heurísticas Nielsen aplicadas

- **Visibilidad del estado** — alertas Django ✅ pero faltan toasts (no hay polyfill SweetAlert configurado en panel admin).
- **Coherencia y estándares** — Metronic v8 establece patrón; URLs en español (`/listar/`, `/crear/`) está bien pero requiere consistencia documentada.
- **Prevención de errores** — confirmar deletes con `base_confirm_delete.html` (existe). Falta confirmar cambios de permisos con `data-bs-toggle="confirm"`.
- **Reconocer mejor que recordar** — sidebar siempre muestra módulo activo ✅. Falta breadcrumbs en módulos profundos.
- **Eficiencia** — falta búsqueda global (#U2) y atajos.
- **Estética minimalista** — buena base, pero login y errores hoy se ven “a medias”.

---

## 4. Conclusiones del GAP

1. **Prioridad 1 (bloqueantes)**: `module_list`, `UserPermissionView` + matriz, `PasswordChangeView`, vistas `password_reset/*`.
2. **Prioridad 2 (UX completa)**: plantillas dedicadas `user_form/detail`, `group_form` con matriz, `permission_detail` con usuarios, perfil con tabs, audit list filtrable.
3. **Prioridad 3 (pulido)**: error pages Metronic, settings panel, notifications drawer, búsqueda global.
4. **Prioridad 4 (deuda técnica)**: paridad de widgets (faltan 7), unificar iconografía, portar `stat_card`/`state_filter_cards`/`m2m_pills`.

→ Ver plan ejecutable en `03_SUPERADMIN_IMPLEMENTATION_PLAN.md`.
