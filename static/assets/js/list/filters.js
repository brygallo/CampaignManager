/* List filters dropdown — Metronic demo55 pattern.
 *
 * Posts the dropdown form to superadmin's session view, which persists
 * params under request.session["filters"] keyed by (app, model). Reload
 * triggers FilterMixin to re-read and apply them.
 */
(function () {
  "use strict";

  function getCsrf() {
    var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  function postSession(url, formData) {
    formData.append("csrfmiddlewaretoken", getCsrf());
    return fetch(url, {
      method: "POST",
      body: formData,
      credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest" },
    }).then(function () {
      window.location.href = window.location.pathname;
    });
  }

  function resolveSessionUrl() {
    var form = document.querySelector('[data-kt-list-filter="form"]');
    if (form && form.dataset.ktListFilterUrl) return form.dataset.ktListFilterUrl;
    var holder = document.querySelector("[data-kt-filter-session-url]");
    return holder ? holder.dataset.ktFilterSessionUrl : null;
  }

  // SessionView (superadmin) expects DateField values in DD/MM/YYYY.
  function pad2(n) { return n < 10 ? "0" + n : "" + n; }
  function toDDMMYYYY(date) {
    if (!date) return "";
    return pad2(date.getDate()) + "/" + pad2(date.getMonth() + 1) + "/" + date.getFullYear();
  }
  // Server stores YYYY-MM-DD in session; read it back into flatpickr.
  function parseISO(value) {
    if (!value) return null;
    var m = String(value).match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (m) return new Date(parseInt(m[1], 10), parseInt(m[2], 10) - 1, parseInt(m[3], 10));
    var m2 = String(value).match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
    if (m2) return new Date(parseInt(m2[3], 10), parseInt(m2[2], 10) - 1, parseInt(m2[1], 10));
    return null;
  }
  function normalizeForSession(val) {
    if (!val) return val;
    var m = String(val).match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (m) return m[3] + "/" + m[2] + "/" + m[1];
    return val;
  }

  function initDateRange(input) {
    if (!window.jQuery || !window.jQuery.fn || !window.jQuery.fn.flatpickr) return null;
    var fromHidden = document.querySelector(
      '[data-kt-list-filter-daterange-from="' + input.id + '"]'
    );
    var toHidden = document.querySelector(
      '[data-kt-list-filter-daterange-to="' + input.id + '"]'
    );
    var defaultDates = [];
    var fromDate = parseISO(input.dataset.defaultFrom);
    var toDate = parseISO(input.dataset.defaultTo);
    if (fromDate) defaultDates.push(fromDate);
    if (toDate) defaultDates.push(toDate);

    var fp = jQuery(input).flatpickr({
      altInput: true,
      altFormat: "d/m/Y",
      dateFormat: "Y-m-d",
      mode: "range",
      defaultDate: defaultDates.length ? defaultDates : null,
      onChange: function (selectedDates) {
        if (fromHidden) fromHidden.value = toDDMMYYYY(selectedDates[0]);
        if (toHidden) toHidden.value = toDDMMYYYY(selectedDates[1]);
      },
    });

    // Sync defaults into hidden inputs for the first submit (no onChange yet).
    if (fromDate && fromHidden) fromHidden.value = toDDMMYYYY(fromDate);
    if (toDate && toHidden) toHidden.value = toDDMMYYYY(toDate);

    var clearBtn = document.querySelector(
      '[data-kt-list-filter-daterange-clear="' + input.id + '"]'
    );
    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        fp.clear();
        if (fromHidden) fromHidden.value = "";
        if (toHidden) toHidden.value = "";
      });
    }
    return fp;
  }

  function bindForm(form) {
    var datepickers = [];
    form.querySelectorAll("[data-kt-list-filter-daterange]").forEach(function (input) {
      var fp = initDateRange(input);
      if (fp) datepickers.push({ input: input, fp: fp });
    });

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var url = form.dataset.ktListFilterUrl;
      if (!url) return;
      var fd = new FormData();
      var raw = new FormData(form);
      raw.forEach(function (value, key) {
        if (key === "csrfmiddlewaretoken") return;
        if (value !== null && String(value).trim() !== "") {
          fd.append(key, normalizeForSession(value));
        }
      });
      postSession(url, fd);
    });

    form.addEventListener("reset", function () {
      window.setTimeout(function () {
        if (window.jQuery) {
          form.querySelectorAll('select[data-kt-select2="true"]').forEach(function (sel) {
            jQuery(sel).val(null).trigger("change");
          });
        }
        datepickers.forEach(function (entry) {
          entry.fp.clear();
          var fromHidden = form.querySelector(
            '[data-kt-list-filter-daterange-from="' + entry.input.id + '"]'
          );
          var toHidden = form.querySelector(
            '[data-kt-list-filter-daterange-to="' + entry.input.id + '"]'
          );
          if (fromHidden) fromHidden.value = "";
          if (toHidden) toHidden.value = "";
        });
      }, 0);
    });
  }

  function bindClearAll() {
    document.querySelectorAll("[data-kt-filter-clear]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var url = resolveSessionUrl();
        if (!url) return;
        postSession(url, new FormData());
      });
    });
  }

  function bindRemoveIndividual() {
    document.querySelectorAll("[data-kt-filter-remove]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var url = resolveSessionUrl();
        if (!url) return;
        var removed = btn.closest("[data-kt-filter-badge]");
        if (!removed) return;
        var fd = new FormData();
        document.querySelectorAll("[data-kt-filter-badge]").forEach(function (badge) {
          if (badge === removed) return;
          var key = badge.dataset.field + "__" + badge.dataset.lookup;
          var val = badge.dataset.search;
          if (val && String(val).trim() !== "") fd.append(key, normalizeForSession(val));
        });
        postSession(url, fd);
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var form = document.querySelector('[data-kt-list-filter="form"]');
    if (form) bindForm(form);
    bindClearAll();
    bindRemoveIndividual();
  });
})();
