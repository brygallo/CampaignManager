# 08 · Audit follow-ups (HIGH priority)

> Resultado de la auditoría UX/UI + clean code + seguridad de 2026-05-07.
> Los hallazgos críticos (C1-C5) y los altos rápidos (A3, A5, A8, A12) ya
> están aplicados en `main`. Los siguientes 8 ítems requieren decisión de
> scope, diseño o coordinación, así que viven aquí hasta que se conviertan
> en PRs.
>
> Cada sección sigue el formato: **estado actual → propuesta → decisión
> pendiente → estimación**.

---

## A1 · `GroupSite` sin permiso explícito

**Estado actual.** `apps/authentication/sites.py:55-65` — `GroupSite` no
declara `required_permission` ni un `test_func`; cualquier `is_staff` puede
crear, editar (incluyendo la matrix de permisos vía `GroupPermissionFormMixin`)
y eliminar grupos. Lo mismo aplica a `PermissionSite` y `RuleSite`.

**Propuesta.** Endurecer en dos capas:

1. A nivel de `BaseSite` (en `core/base.py`): añadir un atributo
   `required_permission_create` / `_update` / `_delete` que, si está
   definido, lo verifique en `dispatch()` antes de cualquier mutación.
2. En cada site sensible:

   ```python
   class GroupSite(BaseSite):
       required_permission_create = "auth.add_group"
       required_permission_update = "auth.change_group"
       required_permission_delete = "auth.delete_group"
   ```

3. Para casos que necesiten lógica adicional (ej. "no permitir editar el
   propio grupo de superuser"), exponer un hook `def can_change(self, user, instance)`
   que retorne bool.

**Decisión pendiente.**

- ¿La política es "solo superusuarios mutan auth.\*" o "permisos granulares
  por usuario"?
- ¿Cómo asignamos los permisos `auth.change_group` etc. a los `is_staff` por
  defecto? ¿Migración de datos? ¿Signal `post_migrate`?

**Estimación.** 1 sprint (incluye tests de regresión por endpoint).

---

## A4 · Cache de `build_permission_matrix`

**Estado actual.** `apps/authentication/permissions.py:34-38` —
`build_permission_matrix` carga TODOS los `Permission` (típicamente 200-500
por proyecto Django con varias apps) y construye el árbol app→model→action
en cada render de:

- `UserSite` detail
- `GroupSite` detail
- `GroupSite` form (create + update)
- `UserPermissionView`

Esto se traduce en una query + ~500 iteraciones Python por pageload, en
**cada tenant schema**.

**Propuesta.** Cache por schema con invalidación en `post_migrate`.

```python
# apps/authentication/permissions.py
from django.core.cache import cache
from django.db import connection
from django.db.models.signals import post_migrate
from django.dispatch import receiver

CACHE_TTL = 60 * 60  # 1h, se invalida también por post_migrate

def build_permission_matrix(direct_perm_ids, group_perm_map=None):
    # ... lo de hoy, pero el árbol app→model→action (sin direct_perm_ids
    # ni group_perm_map) se cachea, y solo el "merge" con direct_perm_ids
    # se hace en cada llamada.
    skeleton = _cached_skeleton()
    return _attach_holder_state(skeleton, direct_perm_ids, group_perm_map or {})

def _cached_skeleton():
    schema = connection.schema_name  # django-tenants
    key = f"perm_matrix_skel:{schema}"
    skel = cache.get(key)
    if skel is None:
        skel = _build_skeleton()
        cache.set(key, skel, CACHE_TTL)
    return skel

@receiver(post_migrate)
def _invalidate_perm_matrix(sender, **kwargs):
    schema = connection.schema_name
    cache.delete(f"perm_matrix_skel:{schema}")
```

**Decisión pendiente.**

- ¿TTL razonable? El esqueleto solo cambia con migraciones, así que 1h+ es
  seguro. Pero `Permission.name` puede cambiar manualmente — convendría
  invalidar también con un signal `post_save` sobre `Permission`.
- ¿Cache backend? Hay Redis disponible. Confirmar que `core.cache.tenant_cache_key`
  ya cubre el aislamiento por schema.

**Estimación.** 0.5 sprint + benchmark antes/después.

---

## A6 · Deduplicación de mapas (JS + CSS)

**Estado actual.**

- `static/assets/js/field_surveys/map.js` (792 líneas) y
  `static/assets/js/territorial_ads/map.js` (796 líneas) son **95%
  idénticos**. Diferencias: IDs de elementos, strings de UI, un endpoint
  extra (popup) en territorial_ads.
- `static/assets/css/field_surveys/map.css` y
  `static/assets/css/territorial_ads/map.css` son idénticos salvo el prefijo
  de clase (`field-survey-map-*` vs `physical-ad-map-*`).

Cualquier bug-fix se aplica dos veces. Riesgo de divergencia silenciosa.

**Propuesta.**

1. Extraer `static/assets/js/maps/leaflet-map-shell.js` que exporte una
   factory:
   ```js
   window.LeafletMapShell.create({
     mapId: "field-survey-map",
     dataUrl: "...",
     createUrl: "...",
     popupUrl: null,                    // opcional
     onPinClick: function (item) { ... },
     pinIconBuilder: function (item) { ... },
     i18n: { count: "visitas", saveError: "...", ... },
     extraInit: function (map, layers) { ... }
   });
   ```
2. Cada mapa específico (`field_surveys/map.js`, `territorial_ads/map.js`)
   se reduce a ~80 líneas de configuración + handlers específicos.
3. Renombrar las clases CSS a un prefijo neutro `.cm-map-*` y dejar
   overrides mínimos por feature en cada hoja.

**Decisión pendiente.**

- ¿Mantenemos vanilla JS (estilo actual) o aprovechamos para introducir un
  bundler (esbuild/vite)? Si entra bundler, abre la puerta a TypeScript +
  testing — más valor pero scope mayor.
- ¿El popup enriquecido de `territorial_ads` (ver C6 de la auditoría) se
  conserva o se elimina?

**Estimación.** 1 sprint si vanilla, 2 si entra bundler.

---

## A10 · `apps.locations` en `TENANT_APPS`

**Estado actual.** `core/settings/base.py` declara `apps.locations` en
`TENANT_APPS`. Cada tenant nuevo arranca con tablas vacías de
`Province`/`Canton`/`Parish`/`Sector` y debe correr `seed_ecuador`
manualmente.

**Pregunta clave.** ¿Los datos geográficos de Ecuador son catálogo nacional
inmutable o cada tenant puede personalizarlos (ej. agregar sectores
internos del partido)?

**Opción A — catálogo compartido.**

- Mover `apps.locations` a `SHARED_APPS`.
- `seed_ecuador` corre en `migrate_schemas --shared`.
- Modelos del dominio (`Campaign.target_canton`, etc.) referencian al
  esquema `public`. Django-tenants soporta cross-schema FKs solo si los
  modelos viven en `SHARED_APPS`, así que esto **fuerza** que todo modelo
  de dominio que use `locations` siga viviendo en TENANT_APPS pero con FKs
  vía `to="public.Canton"`. Verificar que esto funciona en runtime con la
  versión actual de django-tenants.

**Opción B — cada tenant es dueño de sus locations.**

- Documentar explícitamente la decisión en `core/settings/base.py`.
- Convertir `seed_ecuador` en un comando que se ejecuta automáticamente al
  crear un tenant (signal post-create en `apps.tenancy`).
- Permitir que cada partido extienda con sectores propios sin afectar a
  otros.

**Decisión pendiente.** Producto/legal: ¿los partidos pueden tener
divisiones internas distintas a la oficial del CNE? Si sí → Opción B.

**Estimación.** Opción A: 1 sprint (migración + verificar FKs). Opción B:
0.5 sprint (signal + doc).

---

## A11 · `MapDataView` sin paginación / clustering server-side

**Estado actual.**

- `apps/field_surveys/views.py:156-204` (`FieldSurveyMapDataView`) y
  `apps/territorial_ads/views.py:59-97` (`PhysicalAdMapDataView`) cargan
  TODOS los puntos en memoria, los serializan en Python y los devuelven en
  un único JSON.
- Con un partido grande (decenas de miles de visitas), esto satura memoria
  Python, ancho de banda y el tiempo de render Leaflet client-side.

**Opciones.**

1. **Viewport-based loading.** El mapa envía bbox + zoom; el endpoint
   filtra por `latitude__range`/`longitude__range` y devuelve hasta N
   puntos. Cuando el usuario hace pan/zoom, refetch.
   Pro: simple, escala bien.
   Con: requiere lógica de invalidación de cache por bbox.

2. **Server-side clustering** (ej. supercluster en backend, o
   `django-geoposition` con grid). Devuelve clusters cuando hay >N puntos
   en una zona; expande a pines individuales con zoom alto.
   Pro: óptimo en payload.
   Con: mayor complejidad, depende de PostGIS o índices ad-hoc.

3. **Límite con aviso.** Devolver primeros 5 000 puntos y un flag
   `truncated: true` que el cliente muestra como "viendo 5 000 de N: filtra
   para ver más".
   Pro: 1 día de trabajo.
   Con: paliativo, no resuelve el caso de uso real.

**Recomendación.** Combinar (3) ahora (paliativo barato) + (1) en el
sprint siguiente.

**Decisión pendiente.** ¿Qué N estimado de puntos veremos en producción?
Define qué solución es necesaria.

**Estimación.** (3) 0.5 día. (1) 1 sprint. (2) 2 sprints + PostGIS.

---

## A13 · Tabs ARIA incompletos en `base_detail.html`

**Estado actual.** `templates/base/base_detail.html:87-101` — los `<a class="nav-link" data-bs-toggle="tab">`
no tienen `role="tab"`, `aria-selected`, ni `aria-controls`. Los
`<div class="tab-pane">` no tienen `role="tabpanel"`. Bootstrap 5 espera
estos atributos para keyboard nav (flechas izquierda/derecha) y screen
readers no anuncian qué pestaña está activa.

**Propuesta.**

```html
<ul class="nav nav-tabs" role="tablist">
  <li class="nav-item" role="presentation">
    <a class="nav-link active"
       id="tab-data-trigger"
       data-bs-toggle="tab"
       href="#tab-data"
       role="tab"
       aria-controls="tab-data"
       aria-selected="true">Información</a>
  </li>
  ...
</ul>
<div class="tab-content">
  <div class="tab-pane fade show active"
       id="tab-data"
       role="tabpanel"
       aria-labelledby="tab-data-trigger"
       tabindex="0">...</div>
</div>
```

Aplicar el mismo patrón a:

- `apps/authentication/templates/.../user_detail.html` (tab Permisos)
- `apps/authentication/templates/.../group_detail.html` (tabs Permisos +
  Usuarios)
- Cualquier `detail_extra_tabs` futuro.

**Decisión pendiente.** ¿Bootstrap 5.3 hace este wiring automáticamente o
hay que coordinar JS para sync `aria-selected`? Verificar con el bundle
actual de Maxton.

**Estimación.** 0.5 día + smoke test con NVDA/VoiceOver.

---

## A14 · Internacionalización (`{% trans %}`) inexistente

**Estado actual.** Cero ocurrencias de `{% load i18n %}` o `{% trans %}` en
plantillas globales. Toda la UI está hardcoded en español. `core/widgets.py:85-93`
tiene strings en español dentro del `format_html` del LeafletMapWidget.

Para un proyecto multi-tenant que potencialmente atenderá tenants
quechua-hablantes (la región amazónica de Morona Santiago tiene
poblaciones shuar y achuar), esto es deuda real.

**Propuesta.** Plan de migración por fases:

1. **Fase 1 (configuración).** Añadir `LANGUAGES`, `LOCALE_PATHS`,
   `MIDDLEWARE += ['django.middleware.locale.LocaleMiddleware']`. Confirmar
   que `core/settings/base.py` ya tiene `USE_I18N = True`.
2. **Fase 2 (templates globales).** Reemplazar strings en
   `templates/base/`, `templates/widgets/`, `templates/registration/`,
   `templates/errors/` con `{% trans %}` y `{% blocktrans %}`. Generar
   `locale/es/LC_MESSAGES/django.po`.
3. **Fase 3 (apps).** Cada feature owner reemplaza strings de su app
   gradualmente. Forms con `gettext_lazy` para labels.
4. **Fase 4 (Python views).** `messages.success("...")` → `messages.success(_("..."))`.

**Decisión pendiente.**

- ¿Cuándo? Hacerlo con producto en greenfield es barato; hacerlo después de
  6 meses con cientos de strings es costoso.
- ¿Idiomas objetivo? Si solo es español → marcar todas las strings con
  `gettext_lazy` igualmente como hábito, y dejar la traducción para
  después.

**Estimación.** Fase 1: 2 horas. Fase 2: 2-3 sprints. Fase 3: distribuido.

---

## A15 · Páginas de error extienden `base/base.html`

**Estado actual.** `templates/errors/{403,404,500}.html` extienden
`base/base.html`, lo que dispara sidebar + header + command palette + todos
los context processors (`brand`, `tenant_features`, etc.).

**Riesgo.** Si el 500 viene de un fallo en el context processor (ej.
`tenant_features` no puede leer la BD pública porque la BD está caída),
renderizar `errors/500.html` con `base.html` ejecuta el mismo context
processor y entra en recursión → 500 dentro del 500 → respuesta vacía o
stack trace al usuario.

`templates/errors/500.html:14` también usa `<a href="javascript:location.reload()">`
que viola CSP estricta y no funciona con JS desactivado.

**Propuesta.**

1. Crear `templates/errors/_blank.html` minimalista (sin sidebar, sin
   command palette, con CSS inline básico para que no dependa del bundle).
2. `errors/{403,404,500}.html` lo extienden.
3. Reemplazar `<a href="javascript:...">` por `<button onclick="...">` y
   `<a href="/">` (ir a home).
4. Para el 500 específicamente, usar el handler `core.views.handler500`
   con `render_to_string` directo para evitar context processors:

   ```python
   # core/views.py
   from django.shortcuts import render

   def handler500(request, *args, **kwargs):
       return render(request, "errors/500.html", status=500, context={})
   ```

   Y en `core/urls.py`:
   ```python
   handler500 = "core.views.handler500"
   ```

**Decisión pendiente.** ¿La página de error debe mostrar branding del
tenant? Si sí, hay que cargar branding sin pasar por `tenant_features`
(con try/except defensivo).

**Estimación.** 1 día.

---

## Tracking

| ID | Owner | Sprint objetivo | PR |
|----|-------|-----------------|-----|
| A1 | TBD   | TBD             | -   |
| A4 | TBD   | TBD             | -   |
| A6 | TBD   | TBD             | -   |
| A10| TBD   | TBD             | -   |
| A11| TBD   | TBD             | -   |
| A13| TBD   | TBD             | -   |
| A14| TBD   | TBD             | -   |
| A15| TBD   | TBD             | -   |

> Fuentes: auditoría completa documentada en la conversación de Claude
> Code de 2026-05-07. Ver historial git para los fixes ya aplicados (C1-C5,
> A3, A5, A8, A12, plus ~30 fixes seguros UX/A11y/clean code).
