# 07 · Plan UX/UI – CampaignManager (Metronic v8 demo55)

> Plan completo de mejora de UX/UI sobre la base ya cableada de Metronic 8
> demo55. Pareja con `02_DESIGN_SYSTEM.md` (tokens), `03_SUPERADMIN_IMPLEMENTATION_PLAN.md`
> y `04_LIST_FILTERS_PLAN.md` (filtros de lista).

---

## 0. Diagnóstico

**Lo que ya está bien (no tocar):**
- Base templates unificados (`base/base.html`, `base_list`, `base_form`, `base_detail`).
- Tokens de color y design system documentados en `docs/02_DESIGN_SYSTEM.md`.
- Header con quick-create, notificaciones, theme switcher, perfil.
- Bulk delete, filtros con badges, paginación, breadcrumbs automáticos.
- Workflows con stepper + transition requirements.
- Audit timeline.

**Brechas detectadas:**

| # | Brecha | Impacto |
|---|---|---|
| 1 | Sidebar estático: sin buscador, sin favoritos, sin contadores en items | Navegación lenta cuando crece menú |
| 2 | DataTables con `paging:false`, `dom:'t'` — sin orden por columna, sin export, sin column picker | Listas grandes inutilizables |
| 3 | Forms sin sticky save bar, sin warning de "cambios sin guardar", sin progreso por sección | Riesgo de pérdida de datos |
| 4 | No hay autosave ni HTMX — todo es full reload | Sensación lenta, cara en latencia |
| 5 | Detail solo tabs Información/Auditoría — falta panel de relacionados, comentarios, side-panel de acciones | Operador navega mucho |
| 6 | Listas en mobile usan tabla horizontal (scroll x) | Mala experiencia táctil |
| 7 | No hay skeletons ni loading states sistemáticos | Parpadeo perceptible |
| 8 | Dashboard fijo, no parametrizado por rol/tenant ni con date-range | Mismo home para todos |
| 9 | Sin búsqueda global tipo "spotlight" entre módulos | Solo se busca dentro de la lista actual |
| 10 | Sin onboarding ni tour de primera vez (crítico para SaaS multi-partido) | Nuevos partidos se pierden |
| 11 | Mapa de field_surveys aislado — no hay vista mapa-tabla combinada | Subutiliza geo data |
| 12 | Calendario de agenda política no existe como vista | Tabla para algo intrínsecamente temporal |
| 13 | Accesibilidad: aria-labels inconsistentes, focus trap en modales no auditado | Riesgo legal/sectorial |
| 14 | Sin command palette (⌘K) ni atajos | Power users sin atajos |

---

## 1. Principios rectores

1. **Reusar Metronic, no inventar** — antes de añadir CSS, buscar el componente en `metronic_html_v8.2.0_demo55/demo55/dist/`.
2. **Server-rendered + HTMX progresivo** — no migrar a SPA. Añadir HTMX/Alpine sólo donde quita reload molesto.
3. **Mobile-first** en operativos (levantamientos), desktop-first en panel admin.
4. **Token-driven**: nada hardcoded, todo via `--bs-*` y tokens del design system.
5. **A11y nivel AA mínimo** — todo el flujo navegable por teclado.

---

## 2. Fases

### Fase 0 — Foundation (sem 1)
- Auditoría a11y automatizada (axe-core en CI sobre `pytest-playwright`).
- Snapshot visual baseline de `home`, `list`, `form`, `detail`.
- Extender `02_DESIGN_SYSTEM.md` con motion tokens, spacing scale, breakpoints.
- Inventariar templates que NO extienden `base/base.html` y migrarlos.

### Fase 1 — Shell & navegación (sem 2-3)
- **Sidebar 2.0**: buscador client-side, favoritos (localStorage), recientes, badges de contador.
- **Command Palette ⌘K** indexando menú + recientes + "crear X".
- **Header**: notificaciones live (SSE/polling 60s), atajo `+ N` para nuevo.

### Fase 2 — Listas pro (sem 4-5)
- Server-side sorting por columna (header click → `?ordering=field`).
- **Column picker** (visibles persistidas en localStorage por modelo).
- **Densidad** (compact / normal / comfortable).
- **Export** (CSV, Excel, PDF) reusando datatables export.
- **Saved views** (filtros + ordering + columnas como vista guardada).
- **Inline edit** en celdas de catálogo.
- **Mobile cards** (intercambio table↔cards en `<md`).
- **Vistas alternativas**: Kanban (modelos con workflow), Mapa (field_surveys, ads), Calendario (agenda).

### Fase 3 — Forms a prueba de errores (sem 6-7)
- **Sticky action bar** + resumen de errores con scroll-to-first.
- **Unsaved changes guard** (`beforeunload`).
- **Stepper** para forms con >3 fieldsets.
- **Conditional fields** (`data-show-when="field=value"`).
- **Autosave borradores** (cada 30s a `UserDraft`).
- **Inline-create de FK** vía modal genérico.

### Fase 4 — Detail pages como dashboard del registro (sem 8)
- Layout 2-col: tabs (8/12) + sidebar sticky (4/12) con workflow + acciones rápidas + relacionados.
- Tabs adicionales: Relacionados, Notas (modelo `Note`), Documentos.
- Activity feed unificado (traces + notes + transiciones).

### Fase 5 — Dashboard parametrizado (sem 9)
- Date-range global.
- Widgets por rol (registry `core/dashboards.py`).
- Mapa de calor de cobertura territorial.
- Funnel de campaña.
- Drill-down click → lista filtrada.

### Fase 6 — Domain-specific (sem 10-11)
- **Field surveys PWA**: instalable, offline-first, foto comprimida, GPS auto-fill.
- **Agenda calendario**: FullCalendar con drag-to-reschedule, conflictos visuales.
- **Publicidad territorial mapa**: clustering por sector + filtros laterales + before/after fotos.
- **Auditoría global**: `/audit/` con filtros y export.

### Fase 7 — Multi-tenant branding & onboarding (sem 12)
- **White-label real**: logo, color primario, fuente por tenant inyectados como CSS vars.
- **Onboarding wizard** de 5 pasos para primer usuario de un partido.
- **Tour contextual** (driver.js) en cada vista nueva.

### Fase 8 — Performance UX & accesibilidad (sem 13)
- **HTMX progresivo**: filtros, paginación, mass-delete, modales.
- **Skeletons** (componente `templates/base/_skeleton.html`).
- **Lazy load** imágenes + charts con `IntersectionObserver`.
- **A11y sweep**: axe-core en CI, focus trap modales, contraste AA dark mode.

---

## 3. Quick wins

| # | Cambio | Archivo | Esfuerzo | Estado |
|---|---|---|---|---|
| QW1 | Sort por columna en datatable | `base_list.html` | 30 min | ✅ |
| QW2 | `loading="lazy"` en imágenes | varios | 30 min | ✅ |
| QW3 | Sticky save bar en mobile | `base_form.html` | 1 h | ✅ |
| QW4 | Unsaved-changes warning | `base_form.html` | 30 min | ✅ |
| QW5 | Buscador client-side en sidebar | `sidebar.html` | 1 h | ✅ |
| QW6 | Empty states con CTAs | varios | 1 h | revisado |
| QW7 | Atajos `g+letra` (gmail-style) | `assets/js/shortcuts.js` | 1 h | ✅ |
| QW8 | Toast tras submit | flujos | 30 min | ya OK |

---

## 4. Roadmap

```
Sem 1   : Fase 0 + Quick Wins
Sem 2-3 : Fase 1 (shell)
Sem 4-5 : Fase 2 (listas)
Sem 6-7 : Fase 3 (forms)
Sem 8   : Fase 4 (detail)
Sem 9   : Fase 5 (dashboard)
Sem 10-11: Fase 6 (domain)
Sem 12  : Fase 7 (branding+onboarding)
Sem 13  : Fase 8 (perf+a11y)
```

## 5. Métricas de éxito

- **Time-on-task** crear levantamiento: < 60s en mobile.
- **Reload count** por sesión: −50% (HTMX).
- **Lighthouse mobile**: 90+ Performance, A11y, Best Practices.
- **axe-core violations**: 0 en CI.
- **Onboarding completion rate** (nuevo tenant): > 80%.
