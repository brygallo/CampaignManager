/**
 * Dev/QA test-data prefill.
 *
 * Loaded only when the ``DEV_PREFILL`` env var is on (see ``base_form.html``).
 * Fills every CRUD form field with plausible dummy data so records can be
 * created quickly during testing. The location is NEVER touched: latitude,
 * longitude and the Leaflet map widget are always picked by hand, so their
 * fields are excluded from the fill.
 *
 * Works generically across every form because it is driven by the markup,
 * not by per-model config: any button with class ``js-dev-prefill`` fills its
 * target form. The target is, in order of preference, the form named by the
 * button's ``data-prefill-form`` attribute (id or CSS selector), the form the
 * button lives in, the form referenced by the button's ``form`` attribute, or
 * ``#main-form`` as a last resort. This covers the shared CRUD page
 * (``base/base_form.html``) and the AJAX map modals alike.
 */
(function (window, document, $) {
  "use strict";

  var BUTTON_SELECTOR = ".js-dev-prefill, #dev-prefill-btn";

  // Field names matching these are location-related and must stay empty so the
  // user chooses the point on the map. Matched case-insensitively against the
  // control's ``name`` attribute.
  var LOCATION_NAME_RE = /(^|_)(lat|latitude|lng|long|longitude|location|coord|coordinate|geom|point)(_|$)/i;

  /** Collect the names of fields wired to a Leaflet map widget, so we skip them. */
  function collectMapFieldNames(form) {
    var names = {};
    var widgets = form.querySelectorAll("[data-leaflet-map]");
    [].slice.call(widgets).forEach(function (widget) {
      ["latField", "lngField"].forEach(function (key) {
        var name = widget.dataset[key];
        if (name) {
          names[name] = true;
        }
      });
    });
    return names;
  }

  function isLocationField(field, mapFieldNames) {
    var name = field.getAttribute("name") || "";
    return mapFieldNames[name] === true || LOCATION_NAME_RE.test(name);
  }

  /** A short deterministic-ish suffix so repeated fills don't collide. */
  function suffix(index) {
    return String(index + 1);
  }

  function fireEvents(field) {
    field.dispatchEvent(new Event("input", { bubbles: true }));
    field.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function todayISO() {
    var now = new Date();
    var pad = function (n) { return String(n).padStart(2, "0"); };
    return now.getFullYear() + "-" + pad(now.getMonth() + 1) + "-" + pad(now.getDate());
  }

  function nowISO() {
    return todayISO() + "T" + "09:00";
  }

  function fillTextLike(field, index) {
    var type = (field.getAttribute("type") || "text").toLowerCase();
    var name = (field.getAttribute("name") || "campo").toLowerCase();

    switch (type) {
      case "email":
        field.value = "prueba" + suffix(index) + "@example.com";
        break;
      case "url":
        field.value = "https://example.com/prueba-" + suffix(index);
        break;
      case "tel":
        field.value = "099" + String(1000000 + index).slice(0, 7);
        break;
      case "number":
      case "range": {
        var min = field.getAttribute("min");
        var step = field.getAttribute("step");
        var hasDecimals = step && step.indexOf(".") !== -1;
        var base = min !== null && min !== "" ? Number(min) : 1;
        field.value = hasDecimals ? (base + 1).toFixed(2) : String(base + index + 1);
        break;
      }
      case "date":
        field.value = todayISO();
        break;
      case "datetime-local":
        field.value = nowISO();
        break;
      case "time":
        field.value = "09:00";
        break;
      case "month":
        field.value = todayISO().slice(0, 7);
        break;
      case "color":
        field.value = "#3388ff";
        break;
      case "password":
        field.value = "Prueba1234!";
        break;
      default:
        // Heuristic on the field name for friendlier values.
        if (/mail/.test(name)) {
          field.value = "prueba" + suffix(index) + "@example.com";
        } else if (/(phone|tel|celular|telefono|movil)/.test(name)) {
          field.value = "099" + String(1000000 + index).slice(0, 7);
        } else if (/(cedula|dni|ruc|identificacion)/.test(name)) {
          field.value = String(1700000000 + index).slice(0, 10);
        } else if (/(code|codigo)/.test(name)) {
          field.value = "PRB-" + suffix(index);
        } else {
          field.value = "Prueba " + suffix(index);
        }
    }
    fireEvents(field);
  }

  function fillTextarea(field, index) {
    field.value = "Texto de prueba " + suffix(index) + ". Generado automáticamente para QA.";
    fireEvents(field);
  }

  function fillCheckbox(field) {
    if (!field.checked) {
      field.checked = true;
      fireEvents(field);
    }
  }

  /** Pick the first selectable, non-placeholder option. */
  function fillSelect(field) {
    var isSelect2 = field.classList.contains("django-select2");
    // Remote (AJAX) select2 has no preloaded options; leave it for the user.
    if (field.classList.contains("django-select2-heavy")) {
      return;
    }

    var chosen = null;
    [].slice.call(field.options).forEach(function (opt) {
      if (chosen || opt.disabled) return;
      if (opt.value === "" || opt.value === "0") return; // placeholder / "----"
      chosen = opt;
    });
    if (!chosen) return;

    if (field.multiple) {
      chosen.selected = true;
    } else {
      field.value = chosen.value;
    }

    // select2 needs a jQuery-triggered change to repaint its rendered value.
    if (isSelect2 && $ && $.fn && $.fn.select2 && field.classList.contains("select2-hidden-accessible")) {
      $(field).val(field.multiple ? [chosen.value] : chosen.value).trigger("change");
    } else {
      fireEvents(field);
    }
  }

  function shouldSkip(field) {
    var type = (field.getAttribute("type") || "").toLowerCase();
    if (field.disabled || field.readOnly) return true;
    if (field.name === "csrfmiddlewaretoken") return true;
    // Never touch a formset row's DELETE checkbox (would delete the row).
    if (/-DELETE$/.test(field.name || "")) return true;
    if (["hidden", "file", "submit", "button", "image", "reset"].indexOf(type) !== -1) return true;
    // Radios: only set the first of each group (handled separately below).
    return false;
  }

  /**
   * Make sure every inline formset has at least one editable row to fill.
   *
   * Rows live inside ``#main-form`` so the generic field loop below already
   * fills them; the only gap is a formset rendered with zero rows (``extra=0``
   * and no saved instances). For those we click the jquery.formset "Agregar
   * fila" button once, which inserts a fresh row from the inert ``<template>``.
   */
  function ensureFormsetRows(form) {
    var groups = form.querySelectorAll(".inline-group[data-prefix]");
    [].slice.call(groups).forEach(function (group) {
      var prefix = group.dataset.prefix;
      if (!prefix) return;
      var rows = group.querySelectorAll("tr.inline." + prefix);
      if (rows.length > 0) return; // Already has at least one row.
      var addBtn = group.querySelector(".add-row");
      if (addBtn) {
        addBtn.click(); // jquery.formset inserts the row synchronously.
      }
    });
  }

  function fillForm(form) {
    ensureFormsetRows(form);
    var mapFieldNames = collectMapFieldNames(form);
    var radiosSeen = {};
    var index = 0;

    var controls = form.querySelectorAll("input, select, textarea");
    [].slice.call(controls).forEach(function (field) {
      if (shouldSkip(field)) return;
      if (isLocationField(field, mapFieldNames)) return;

      var tag = field.tagName.toLowerCase();
      var type = (field.getAttribute("type") || "text").toLowerCase();

      // Only fill empty fields so a partially filled form is respected.
      if (tag === "select") {
        if (field.value && field.value !== "" && field.value !== "0") return;
        fillSelect(field);
      } else if (tag === "textarea") {
        if (field.value) return;
        fillTextarea(field, index++);
      } else if (type === "checkbox") {
        fillCheckbox(field);
      } else if (type === "radio") {
        var name = field.getAttribute("name");
        if (radiosSeen[name]) return;
        radiosSeen[name] = true;
        if (!form.querySelector('input[name="' + name + '"]:checked')) {
          field.checked = true;
          fireEvents(field);
        }
      } else {
        if (field.value) return;
        fillTextLike(field, index++);
      }
    });
  }

  /** Resolve which form a prefill button should fill. */
  function resolveForm(button) {
    var sel = button.getAttribute("data-prefill-form");
    if (sel) {
      var byId = document.getElementById(sel);
      if (byId) return byId;
      try {
        var byQuery = document.querySelector(sel);
        if (byQuery) return byQuery;
      } catch (e) { /* invalid selector → fall through */ }
    }
    var closest = button.closest("form");
    if (closest) return closest;
    if (button.form) return button.form; // button references a form via form="…"
    return document.getElementById("main-form");
  }

  function init() {
    // Event delegation so it also works for buttons inside modals whose
    // markup is present from the start but bound after this script runs.
    document.addEventListener("click", function (event) {
      var button = event.target.closest(BUTTON_SELECTOR);
      if (!button) return;
      event.preventDefault();
      var form = resolveForm(button);
      if (!form) return;
      fillForm(form);
      if (window.cmRenderIcons) {
        window.cmRenderIcons();
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(window, document, window.jQuery);
