/**
 * Formset bootstrap — pattern duplicated from gad/sim.
 *
 * Discovers ``.inline-group[data-prefix]`` containers (rendered by
 * templates/forms/formset.html) and wires jquery.formset so rows can be
 * added/removed dynamically. When the template provides a
 * ``<template data-formset-empty-form>`` (Django ``empty_form``), it is used
 * as the row template; otherwise the plugin clones the last row.
 *
 * Re-run ``window.cmFormsets.init(scope)`` after injecting form HTML via
 * AJAX (e.g. map modals).
 */
(function () {
  "use strict";

  function renderFormset(group) {
    var $ = window.jQuery;
    var prefix = group.dataset.prefix;
    if (!prefix || group.dataset.formsetInitialized === "true") return;
    var $rows = $(".inline." + prefix, group);
    if (!$rows.length) return;
    group.dataset.formsetInitialized = "true";

    var templateEl = group.querySelector("template[data-formset-empty-form]");
    $rows.formset({
      prefix: prefix,
      formTemplate: templateEl ? $(templateEl.innerHTML.trim()) : null,
      addText: '<i data-lucide="plus" class="fs-4 me-1"></i>Agregar fila',
      addCssClass: "btn btn-sm btn-light-primary add-row mt-2",
      deleteCssClass: "btn btn-icon btn-sm btn-light-danger delete-row ms-2",
      deleteText: '<i data-lucide="x" class="fs-4"></i>',
      added: function () {
        if (window.cmRenderIcons) window.cmRenderIcons();
      }
    });
    if (window.cmRenderIcons) window.cmRenderIcons();
  }

  function init(scope) {
    if (!window.jQuery || !window.jQuery.fn || !window.jQuery.fn.formset) return;
    var root = scope || document;
    var groups = root.querySelectorAll(".inline-group[data-prefix]");
    Array.prototype.forEach.call(groups, renderFormset);
  }

  document.addEventListener("DOMContentLoaded", function () {
    init(document);
  });

  window.cmFormsets = { init: init };
})();
