# 04 · Filtros de Lista – Plan de Implementación

> Adoptar el patrón visual de filtros del template Metronic v8 demo55
> (`apps/subscriptions/list.html`) sobre la infraestructura existente
> (`gmcm-django-superadmin` → `FilterMixin` + `SessionView` + `FilterService`).
>
> **Referencia visual**: `metronic_html_v8.2.0_demo55/demo55/dist/apps/subscriptions/list.html`
> líneas 4404–4501.
> **Branch sugerido**: `feature/list-filters-dropdown`
> **Estado base**: `main` con `templates/base/base_list.html` actual (search + state cards + clear-btn).

---

## 1. Resumen del patrón demo55

Toolbar del card-header con tres bloques:

```
┌ card-header pt-6 ────────────────────────────────────────────────────────┐
│  🔍 [Buscar...]                              [▽ Filter] [Export] [+ New] │
└──────────────────────────────────────────────────────────────────────────┘
                                                  │
                                                  ▼
                                  ┌───── menu menu-sub w-300px ─────┐
                                  │  Filter Options                 │
                                  │  ─────────────────────────────  │
                                  │  Estado:    [select2 ▽]         │
                                  │  Mes:       [select2 ▽]         │
                                  │  Tipo:      [select2 ▽]         │
                                  │  Producto:  [select2 ▽]         │
                                  │              [Reset] [Apply]    │
                                  └─────────────────────────────────┘
```

Atributos clave (literales de Metronic):
- Botón: `class="btn btn-light-primary me-3" data-kt-menu-trigger="click" data-kt-menu-placement="bottom-end"`
- Dropdown: `class="menu menu-sub menu-sub-dropdown w-300px w-md-325px" data-kt-menu="true"`
- Selects: `class="form-select form-select-solid fw-bold" data-kt-select2="true" data-allow-clear="true" data-hide-search="true"`
- Botones internos: `data-kt-menu-dismiss="true"` (cierran el menú al click)

---

## 2. Objetivo

Sustituir el bloque de búsqueda + el botón "Limpiar filtros" del actual
`templates/base/base_list.html` por un toolbar al estilo demo55, **sin perder**
la funcionalidad ya operativa:

| Funcionalidad existente | Estado tras el cambio |
|---|---|
| `?search=...` (free text + comas) | Conservar — input + botón en `card-title` |
| Badges de `site.current_filters` | Conservar — fila bajo el header (con eliminar individual) |
| Botón "Limpiar filtros" → `site:session` POST vacío | Conservar como "Reset" del dropdown + un botón secundario fuera si hay filtros activos |
| Cards de `state_filter_items` (workflow) | Conservar — independientes del filter-dropdown |
| `WorkflowStateFilterMixin` (querystring `?state=`) | Conservar tal cual |

Adicionalmente:
- Cada `ModelSite.filter_fields` se renderiza como un `<select>` precargado con sus *choices* (FK / CharField con `choices` / Boolean).
- Múltiples filtros aplicables en un solo click ("Apply").
- Persistencia en `request.session["filters"]` (vía `SessionView` que ya existe).
- Eliminación individual de un filtro desde su badge.

---

## 3. Mapeo backend ↔ UI

`FilterMixin.get_context_data` ya entrega:

```python
context["site"] = {
    "all_records": int,
    "filter_fields": [{"name", "label", "app_name", "model_model"}, ...],
    "current_filters": [{"field", "field_label", "lookup", "lookup_label",
                         "search", "search_label"}, ...],
}
```

Lo que **falta** en el contexto para renderizar el dropdown sin AJAX:
- Las *choices* de cada `filter_field` (FK queryset, choices estáticas, boolean).
- El *lookup* por defecto a usar para cada tipo (sin obligar al usuario a elegirlo).
- El valor actualmente seleccionado para pre-rellenar el `<select>`.

### 3.1 Lookup por defecto (sin pasos extra de UI)

| Tipo de campo | Lookup default | Notas |
|---|---|---|
| `ForeignKey` / `OneToOneField` | `exact` | Value = `pk` |
| `CharField` con `choices` | `exact` | Value = la opción |
| `BooleanField` | `exact` | `1` / `0` |
| `CharField` libre | `icontains` | Input texto, no select |
| `IntegerField` | `exact` | Input número |
| `DateField` | `gte` + `lte` (rango) | Dos inputs (ver §6) |

Esta tabla se centraliza en un *helper* `default_lookup_for_type` en `core/list_mixins.py`.

### 3.2 Decisión: extender `FilterMixin` desde CampaignManager

No tocamos `gmcm-django-superadmin` (es paquete externo). Creamos un mixin
adicional **`DropdownFilterMixin`** en `core/list_mixins.py` que:

1. Hereda implícitamente del `FilterMixin` ya aplicado por `superadmin.site`.
2. En `get_context_data` añade `site["filter_options"]`: lista enriquecida con
   `choices`, `default_lookup`, `current_value`, `field_type`.

Se aplica vía la lista `list_mixins` que cada `ModelSite` declara — patrón ya
usado por `WorkflowStateFilterMixin` (ver `core/list_mixins.py:15`).

---

## 4. Fases

| Fase | Objetivo | Estimación | Depende de |
|---|---|---|---|
| **F1** | Helper backend: `DropdownFilterMixin` + helper de lookups | 0.5 día | — |
| **F2** | Plantilla: dropdown demo55 en `base_list.html` | 0.5 día | F1 |
| **F3** | JS: submit del dropdown → `site:session` + remoción individual | 0.5 día | F2 |
| **F4** | Aplicar a un site real (`campaigns`) y QA | 0.5 día | F3 |
| **F5** | Pulido: rangos de fecha, inputs libres, vacío, accesibilidad | 0.5 día | F4 |

> **Total**: 2.5 días. Ruta crítica F1 → F2 → F3 → F4.

---

## 5. Fase 1 — Backend (`core/list_mixins.py`)

### 5.1 Archivos

| Acción | Ruta | Notas |
|---|---|---|
| Modificar | `core/list_mixins.py` | Añadir `DropdownFilterMixin` y `default_lookup_for_type` |
| Modificar (opcional) | un `sites.py` por app | Agregar `DropdownFilterMixin` al `list_mixins` cuando el sitio defina `filter_fields` |

### 5.2 API del mixin

```python
# core/list_mixins.py
from superadmin.services import FieldService, FilterService

DEFAULT_LOOKUP = {
    "ForeignKey": "exact",
    "OneToOneField": "exact",
    "ManyToManyField": "exact",
    "BooleanField": "exact",
    "CharField": "icontains",
    "TextField": "icontains",
    "IntegerField": "exact",
    "DateField": "gte",       # par con "lte" para rango
    "DateTimeField": "gte",
}


def default_lookup_for_type(field_type: str) -> str:
    return DEFAULT_LOOKUP.get(field_type, "exact")


class DropdownFilterMixin:
    """Enriquece site.filter_fields con choices y lookup por defecto.

    Aplicar en un ModelSite que ya use FilterMixin del paquete superadmin:

        @register(MyModel)
        class MySite(ModelSite):
            filter_fields = ("estado:Estado", "candidato")
            list_mixins = (DropdownFilterMixin, ...)
    """

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        model = self.site.model
        params = FilterService.get_params(model, self.request.session)

        options = []
        for field_def in self.site.filter_fields:
            name = field_def.split(":")[0]
            field_type = FieldService.get_field_type(model, name)
            default_lookup = default_lookup_for_type(field_type)
            choices = FilterService.get_choices(model, name)
            if hasattr(choices, "model"):
                choices_list = [(o.pk, str(o)) for o in choices]
            else:
                choices_list = list(choices) if choices else []

            current = params.get(f"{name}__{default_lookup}")
            options.append({
                "name": name,
                "label": FieldService.get_field_label(model, field_def),
                "field_type": field_type,
                "default_lookup": default_lookup,
                "choices": choices_list,        # [(value, label), ...]
                "current_value": current,
                "is_select": bool(choices_list) or field_type == "BooleanField",
                "is_date": field_type in ("DateField", "DateTimeField"),
            })

        site_ctx = context.get("site", {})
        site_ctx["filter_options"] = options
        site_ctx["filter_session_url"] = reverse(
            "site:session", args=[model._meta.app_label, model._meta.model_name]
        )
        context["site"] = site_ctx
        return context
```

### 5.3 Tests F1 (`tests/core/test_dropdown_filter_mixin.py`)

- Modelo dummy con FK + CharField(choices) + BooleanField + DateField.
- `get_context_data` retorna `filter_options` con longitud == filter_fields.
- Cada item trae `choices` no vacío para FK/choices/Boolean; `[]` para texto libre.
- `default_lookup` correcto por tipo.
- `current_value` se lee desde `session["filters"]` con la clave compuesta `name__lookup`.

---

## 6. Fase 2 — Plantilla `templates/base/base_list.html`

### 6.1 Sustituir el `card-header`

Reemplazar (actuales líneas 68–90) por:

```html
<div class="card">
  <div class="card-header border-0 pt-6">

    {# --- search (queda como está hoy, en card-title) --- #}
    <div class="card-title">
      <form id="list-search-form" method="get" class="table-search">
        {% if request.GET.paginate_by %}
          <input type="hidden" name="paginate_by" value="{{ request.GET.paginate_by }}">
        {% endif %}
        <div class="d-flex align-items-center position-relative my-1">
          <i class="ki-outline ki-magnifier fs-3 position-absolute ms-5 z-index-1"></i>
          <input id="id_table_search" type="text"
                 class="form-control form-control-solid w-250px ps-12"
                 name="search" value="{{ request.GET.search|default:'' }}"
                 placeholder="Buscar en esta lista">
        </div>
      </form>
    </div>

    {# --- card-toolbar: Filter dropdown + acciones extra ya existentes --- #}
    <div class="card-toolbar">
      <div class="d-flex justify-content-end align-items-center gap-2"
           data-kt-list-toolbar="base">

        {% if site.filter_options %}
          {% include "base/_filter_dropdown.html" %}
        {% endif %}

        {% block list_toolbar_extra %}{% endblock %}
      </div>
    </div>
  </div>

  {# --- badges de filtros activos (ya existe; añadir botón quitar individual) --- #}
  {% if site.current_filters %}
    <div class="card-body pt-0 pb-3 border-bottom">
      <div class="d-flex flex-wrap align-items-center gap-2">
        <span class="text-muted fw-semibold fs-7 me-1">Filtros activos:</span>
        {% for filter in site.current_filters %}
          <span class="badge badge-light-primary fw-semibold d-inline-flex align-items-center gap-2 py-2 px-3"
                data-kt-filter-badge="true"
                data-field="{{ filter.field }}" data-lookup="{{ filter.lookup }}">
            <span class="text-muted">{{ filter.field_label }}</span>
            <span class="text-gray-500">{{ filter.lookup_label|default:'=' }}</span>
            <strong>{{ filter.search_label|default:filter.search }}</strong>
            <button type="button"
                    class="btn btn-icon btn-xs btn-active-light-danger ms-1 p-0"
                    data-kt-filter-remove="true"
                    title="Quitar este filtro">
              <i class="ki-outline ki-cross fs-7"></i>
            </button>
          </span>
        {% endfor %}
        <button type="button" id="clear-filters-btn"
                class="btn btn-sm btn-light btn-active-light-danger ms-2"
                data-kt-filter-clear="true">
          <i class="ki-outline ki-eraser fs-3"></i>Limpiar todo
        </button>
      </div>
    </div>
  {% endif %}

  {# resto del card-body con state_filter_items + tabla queda igual #}
```

### 6.2 Nuevo include `templates/base/_filter_dropdown.html`

```html
{# Dropdown de filtros estilo Metronic demo55. #}
{# Espera site.filter_options (DropdownFilterMixin) y site.filter_session_url. #}

<button type="button"
        class="btn btn-light-primary"
        data-kt-menu-trigger="click"
        data-kt-menu-placement="bottom-end">
  <i class="ki-outline ki-filter fs-2"></i>Filtros
  {% if site.current_filters %}
    <span class="badge badge-circle badge-light-primary ms-2">{{ site.current_filters|length }}</span>
  {% endif %}
</button>

<div class="menu menu-sub menu-sub-dropdown w-300px w-md-325px"
     data-kt-menu="true"
     id="kt_list_filter_menu">

  <div class="px-7 py-5">
    <div class="fs-5 text-dark fw-bold">Opciones de filtro</div>
  </div>
  <div class="separator border-gray-200"></div>

  <form class="px-7 py-5" data-kt-list-filter="form"
        data-kt-list-filter-url="{{ site.filter_session_url }}">
    {% csrf_token %}

    {% for opt in site.filter_options %}
      <div class="mb-7">
        <label class="form-label fs-6 fw-semibold">{{ opt.label }}:</label>

        {% if opt.is_select %}
          <select class="form-select form-select-solid fw-bold"
                  name="{{ opt.name }}__{{ opt.default_lookup }}"
                  data-kt-select2="true"
                  data-placeholder="Seleccione una opción"
                  data-allow-clear="true"
                  data-hide-search="{{ opt.choices|length|yesno:'false,true' }}">
            <option></option>
            {% for value, label in opt.choices %}
              <option value="{{ value }}"
                      {% if opt.current_value|stringformat:"s" == value|stringformat:"s" %}selected{% endif %}>
                {{ label }}
              </option>
            {% endfor %}
          </select>

        {% elif opt.is_date %}
          <div class="d-flex gap-2">
            <input type="date" class="form-control form-control-solid"
                   name="{{ opt.name }}__gte"
                   value="{{ opt.current_value_gte|default:'' }}"
                   placeholder="Desde">
            <input type="date" class="form-control form-control-solid"
                   name="{{ opt.name }}__lte"
                   value="{{ opt.current_value_lte|default:'' }}"
                   placeholder="Hasta">
          </div>

        {% else %}
          <input type="text" class="form-control form-control-solid"
                 name="{{ opt.name }}__{{ opt.default_lookup }}"
                 value="{{ opt.current_value|default:'' }}"
                 placeholder="Buscar {{ opt.label|lower }}...">
        {% endif %}
      </div>
    {% endfor %}

    <div class="d-flex justify-content-end">
      <button type="reset"
              class="btn btn-light btn-active-light-primary fw-semibold me-2 px-6"
              data-kt-menu-dismiss="true"
              data-kt-list-filter="reset">
        Restablecer
      </button>
      <button type="submit"
              class="btn btn-primary fw-semibold px-6"
              data-kt-menu-dismiss="true"
              data-kt-list-filter="apply">
        Aplicar
      </button>
    </div>
  </form>
</div>
```

### 6.3 QA visual F2

- [ ] Botón "Filtros" abre/cierra dropdown sin recargar.
- [ ] Cada `filter_field` aparece como label + control.
- [ ] FKs y choices renderizan con select2 (gracias a `data-kt-select2="true"` y `static/assets/js/forms/select2.js` global).
- [ ] El badge contador en el botón refleja `|current_filters|`.
- [ ] El bloque de badges con "Limpiar todo" solo aparece cuando hay filtros activos.

---

## 7. Fase 3 — JavaScript

### 7.1 Archivo nuevo `static/assets/js/list/filters.js`

Responsabilidades:
1. Submit del form del dropdown → POST a `data-kt-list-filter-url` con todos
   los `name=value` no vacíos → recargar `window.location.pathname`.
2. Botón "Restablecer" → limpia el form y dispara el submit (POST vacío).
3. Botón "Limpiar todo" (badges row) → POST vacío + recargar.
4. Click en `[data-kt-filter-remove]` de un badge → POST con todos los filtros
   actuales **menos** el quitado (lee del DOM o del propio `data-field/data-lookup`).
5. Re-init de select2 después de un `reset` (los `data-allow-clear` se mantienen).

```js
// static/assets/js/list/filters.js
(() => {
  const csrf = () => {
    const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  };

  const postSession = async (url, formData) => {
    formData.append("csrfmiddlewaretoken", csrf());
    await fetch(url, {
      method: "POST",
      body: formData,
      credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest" },
    });
    window.location.href = window.location.pathname;
  };

  const form = document.querySelector('[data-kt-list-filter="form"]');
  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const url = form.dataset.ktListFilterUrl;
      const fd = new FormData();
      // Solo enviar valores no vacíos (evita basura en sesión)
      for (const [k, v] of new FormData(form).entries()) {
        if (k === "csrfmiddlewaretoken") continue;
        if (v && String(v).trim() !== "") fd.append(k, v);
      }
      await postSession(url, fd);
    });

    form.addEventListener("reset", () => {
      // Re-init select2 tras limpiar
      setTimeout(() => {
        form.querySelectorAll('select[data-kt-select2="true"]').forEach((sel) => {
          if (window.jQuery) jQuery(sel).val(null).trigger("change");
        });
      }, 0);
    });
  }

  // "Limpiar todo" + badges individuales comparten el mismo endpoint
  document.querySelectorAll("[data-kt-filter-clear]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const url = form ? form.dataset.ktListFilterUrl : btn.dataset.url;
      if (!url) return;
      await postSession(url, new FormData());
    });
  });

  document.querySelectorAll("[data-kt-filter-remove]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const url = form ? form.dataset.ktListFilterUrl : null;
      if (!url) return;
      const removed = btn.closest("[data-kt-filter-badge]");
      const removedKey = `${removed.dataset.field}__${removed.dataset.lookup}`;
      const fd = new FormData();
      // Conservar el resto de filtros activos
      document.querySelectorAll("[data-kt-filter-badge]").forEach((b) => {
        if (b === removed) return;
        const k = `${b.dataset.field}__${b.dataset.lookup}`;
        const val = b.querySelector("strong")?.textContent?.trim() || "";
        if (val) fd.append(k, val);
      });
      await postSession(url, fd);
    });
  });
})();
```

> ⚠️ Nota sobre la eliminación individual: `current_filters` provee el `search`
> crudo (id en caso de FK), pero el badge muestra `search_label`. Para que la
> reposición sea fiel hay que escribir el `search` (no el label) en un atributo
> del badge. Añadir en F2: `data-search="{{ filter.search }}"` y leerlo en el JS
> en lugar de `b.querySelector("strong").textContent`.

### 7.2 Carga del JS

Incluir el archivo en `templates/base/base_list.html`:

```django
{% block extra_js %}
  {{ block.super }}
  <script src="{% static 'assets/js/list/filters.js' %}"></script>
  ... (DataTable + clear handler legacy se elimina, reemplazado por arriba)
{% endblock %}
```

### 7.3 QA F3

- [ ] Aplicar 2 filtros → recargar → ambos persisten en badges + dropdown.
- [ ] Quitar uno desde su badge → el otro persiste.
- [ ] "Restablecer" dentro del dropdown limpia visualmente y aplica POST vacío.
- [ ] "Limpiar todo" funciona desde la fila de badges.
- [ ] Sin recarga doble (un solo POST + un solo redirect por acción).

---

## 8. Fase 4 — Aplicar a `campaigns` y QA real

### 8.1 Activar el mixin

En el `sites.py` de `apps/campaigns` (o donde `@register` los modelos
relevantes):

```python
from core.list_mixins import DropdownFilterMixin, WorkflowStateFilterMixin

@register(Campaign)
class CampaignSite(ModelSite):
    fields = (...)
    filter_fields = ("state:Estado", "election:Elección", "movement:Movimiento")
    list_mixins = (WorkflowStateFilterMixin, DropdownFilterMixin)
```

### 8.2 QA E2E

- [ ] `/campaigns/` carga con dropdown y state-cards coexistiendo.
- [ ] Filtrar por movimiento → URL no cambia, sesión se actualiza, lista se recorta.
- [ ] Combinar `?state=2` (de state-cards) + filtros de sesión → aplica AND.
- [ ] `?search=...` no rompe los filtros de sesión.
- [ ] Logout → re-login → los filtros se mantienen (siguen en sesión hasta que el usuario los limpie).

---

## 9. Fase 5 — Pulido y casos especiales

### 9.1 Rangos de fecha

- En `DropdownFilterMixin`, expandir `current_value` en `current_value_gte` y
  `current_value_lte` leyendo `params[name__gte]` y `params[name__lte]`.
- UI: un único `<input>` con **flatpickr** `mode: "range"` (mismo widget que
  Metronic v8 demo55 usa en `apps/ecommerce/sales/listing.html`). Dos
  `<input type="hidden">` con `name="<campo>__gte"` y `__lte` reciben las
  fechas vía `onChange` en formato `DD/MM/YYYY` (formato que exige
  `SessionView.save_params` para `DateField`).
- `flatpickr` ya está bundleado en `static/assets/plugins/global/plugins.bundle.js`,
  no se agrega ningún asset nuevo.
- El badge sigue mostrando dos entradas (una por bound) con `lookup_label`
  "Mayor o igual que" / "Menor o igual que" que ya provee `FilterService`.

### 9.2 Inputs libres (sin choices)

- Dejar `<input type="text">` con `lookup=icontains`.
- Añadir un `data-bs-toggle="tooltip"` que aclare "Coincidencia parcial, no
  distingue mayúsculas".

### 9.3 Estado vacío del dropdown

Si `filter_options|length == 0`, no renderizar el botón "Filtros" (ya cubierto
por `{% if site.filter_options %}` en F2).

### 9.4 Accesibilidad

- `<label for="...">` ligado a cada `<select>` / `<input>` con `id` único:
  `id="filter_{{ opt.name }}"`.
- Botón "Filtros": `aria-haspopup="menu"`, `aria-expanded` lo maneja Metronic.
- Tab order: search → filtros → tabla.

### 9.5 Mobile

- En `<= md` el dropdown queda `w-100` (se evita overflow). Añadir clase
  `w-md-325px w-100` en lugar de `w-300px` fijo.

---

## 10. Resumen de archivos tocados

| Acción | Archivo | Fase |
|---|---|---|
| Modificar | `core/list_mixins.py` | F1 |
| Crear | `tests/core/test_dropdown_filter_mixin.py` | F1 |
| Modificar | `templates/base/base_list.html` | F2 |
| Crear | `templates/base/_filter_dropdown.html` | F2 |
| Crear | `static/assets/js/list/filters.js` | F3 |
| Modificar | `apps/campaigns/sites.py` (y cada otro `sites.py` con `filter_fields`) | F4 |
| Modificar | `core/list_mixins.py` (rango fechas + badges duales) | F5 |

---

## 11. Decisiones tomadas (y descartadas)

| Decisión | Tomada | Alternativa descartada |
|---|---|---|
| Dropdown estilo demo55 (no offcanvas como sim) | ✔ | Offcanvas right (sim) — más espacio pero peor en desktop wide |
| Choices renderizadas server-side | ✔ | AJAX por campo (sim) — añade latencia para listas pequeñas; reservar AJAX para FK con > 200 elementos en F-future |
| Lookup default automático por tipo | ✔ | Pedir al usuario el lookup (sim) — UX peor, casi nadie lo cambia |
| Persistencia en sesión (vía `SessionView`) | ✔ | Querystring puro — choca con `?search=`, perdemos al navegar paginación |
| Mixin nuevo en CM, no fork de `gmcm-django-superadmin` | ✔ | Fork — mucha deuda; mejor suprapasarlo desde CM |

---

## 12. Riesgos

1. **Select2 inicial**: el JS global en `static/assets/js/forms/select2.js`
   debe procesar `data-kt-select2="true"` después del render del dropdown.
   Verificar que se ejecuta al `DOMContentLoaded` y que un dropdown oculto al
   inicio sigue inicializándose. Si no, forzar init en F3 dentro del show del
   menú.
2. **Doble origen de filtros**: `?state=` (querystring) vs `session["filters"]`.
   Documentar en README de superadmin que conviven y se aplican AND.
3. **`current_value` para FK**: comparar como string para no fallar con `int` vs
   `str` (`{% if opt.current_value|stringformat:"s" == value|stringformat:"s" %}`).
4. **Badge "quitar individual" + `search_label`**: ya cubierto en §7.1 con
   `data-search` sobre el badge.
