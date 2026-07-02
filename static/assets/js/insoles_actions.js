/**
 * Insoles action driver (CampaignManager-native).
 *
 * Reserved for COMPLEX object actions (signing, calculations, multi/related
 * forms) backed by the `InstanceBase*` views in apps/insoles. Simple actions
 * keep using workflow transitions (`a.transition` + workflows.js).
 *
 * Contract (matches apps/insoles/views.py InstanceBaseFormView):
 *   GET  data-url            -> { template, create_url, title, confirm_button, max_width }
 *   POST create_url (FormData) -> { message }            (success)
 *                              -> { error, errors }       (HTTP 400, field errors)
 *
 * Usage: a button/link with class "insoles-action" and data-url="<GET url>".
 * Optionally data-title overrides the modal title. Adapted to this repo's
 * stack: Bootstrap 5 modal, toastr, window.initFormWidgets, lucide.
 *
 * NOTE: no consumer yet — verify in the browser when wiring the first one.
 */
(function () {
  if (window.__cmInsolesActionsBound) return;
  window.__cmInsolesActionsBound = true;

  var MODAL_ID = "insoles-instance-forms";
  // The button that opened the modal — used to refresh in place when the
  // action runs from inside the map's detail modal (no full page reload).
  var lastTrigger = null;

  function modalEl() {
    return document.getElementById(MODAL_ID);
  }

  function toast(type, message) {
    if (typeof window.toastr !== "undefined") {
      (window.toastr[type] || window.toastr.info)(message);
    } else if (window.Swal) {
      window.Swal.fire({ text: message, icon: type, timer: 2500, showConfirmButton: false });
    }
  }

  function clearFieldErrors(modal) {
    modal.querySelectorAll(".is-invalid").forEach(function (field) {
      field.classList.remove("is-invalid");
    });
    modal.querySelectorAll(".invalid-feedback[data-insoles-error]").forEach(function (box) {
      box.remove();
    });
    var alert = modal.querySelector("[data-insoles-error-summary]");
    if (alert) alert.remove();
  }

  function errorText(value) {
    if (!value) return "";
    if (!Array.isArray(value)) value = [value];
    return value.map(function (error) {
      if (typeof error === "string") return error;
      if (error && typeof error.message === "string") return error.message;
      return String(error || "");
    }).filter(Boolean).join(" · ");
  }

  function showErrorSummary(modal, messages) {
    messages = (messages || []).filter(Boolean);
    if (!messages.length) return;
    var body = modal.querySelector(".modal-body");
    if (!body) return;
    var alert = document.createElement("div");
    alert.className = "alert alert-danger d-flex align-items-start p-4 mb-5";
    alert.setAttribute("data-insoles-error-summary", "true");
    alert.setAttribute("role", "alert");
    alert.innerHTML = '<i data-lucide="shield-x" class="fs-2 text-danger me-3"></i><div></div>';
    var content = alert.querySelector("div");
    messages.forEach(function (message) {
      var line = document.createElement("div");
      line.textContent = message;
      content.appendChild(line);
    });
    body.prepend(alert);
    if (window.lucide && window.lucide.createIcons) window.lucide.createIcons();
  }

  function showFieldErrors(modal, errors) {
    clearFieldErrors(modal);
    var summary = [];
    Object.keys(errors || {}).forEach(function (name) {
      var text = errorText(errors[name]);
      if (!text) return;
      if (name === "__all__") {
        summary.push(text);
        return;
      }
      var input = modal.querySelector("#id_" + name) ||
        modal.querySelector('[name="' + name + '"]');
      if (!input) {
        summary.push(text);
        return;
      }
      input.classList.add("is-invalid");
      var row = input.closest(".fv-row") || input.parentElement;
      if (!row || row.classList.contains("d-none")) {
        summary.push(text);
        return;
      }
      var box = row && row.querySelector(".invalid-feedback");
      if (!box && row) {
        box = document.createElement("div");
        box.className = "invalid-feedback d-block";
        box.setAttribute("data-insoles-error", "true");
        box.setAttribute("role", "alert");
        row.appendChild(box);
      }
      if (box) {
        box.classList.add("d-block");
        box.textContent = text; // textContent: no HTML injection
      }
    });
    showErrorSummary(modal, summary);
  }

  function buildModal(data) {
    var modal = modalEl();
    if (!modal) {
      toast("error", "No se encontró el contenedor del formulario.");
      return;
    }
    var form = modal.querySelector("form");
    form.action = data.create_url;
    var body = modal.querySelector(".modal-body");
    // data.template is server-rendered form HTML (render_to_string), trusted —
    // same model as workflows.js formModal.
    body.innerHTML = data.template || "";
    var label = modal.querySelector("[data-insoles-title]");
    if (label) label.textContent = data.title || "Formulario";
    var confirmBtn = modal.querySelector("[data-insoles-confirm]");
    if (confirmBtn) confirmBtn.textContent = data.confirm_button || "Guardar";
    var dialog = modal.querySelector(".modal-dialog");
    if (dialog && data.max_width) dialog.style.maxWidth = data.max_width;
    if (window.initFormWidgets) window.initFormWidgets(modal);
    if (window.lucide && window.lucide.createIcons) window.lucide.createIcons();
    bootstrap.Modal.getOrCreateInstance(modal).show();
  }

  // Open: GET the form and render it in the shared modal.
  document.addEventListener("click", function (event) {
    var trigger = event.target.closest(".insoles-action");
    if (!trigger) return;
    event.preventDefault();
    lastTrigger = trigger;
    var url = trigger.dataset.url;
    if (!url) return;
    fetch(url, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (res) {
        if (!res.ok) throw new Error(res.d.error || "No se pudo abrir el formulario.");
        if (trigger.dataset.title) res.d.title = trigger.dataset.title;
        buildModal(res.d);
      })
      .catch(function (err) { toast("error", err.message); });
  });

  // Submit: POST the form, then toast + reload (or a page-provided hook).
  document.addEventListener("submit", function (event) {
    var modal = modalEl();
    if (!modal || !modal.contains(event.target)) return;
    event.preventDefault();
    var form = event.target;
    clearFieldErrors(modal);
    var fd = new FormData(form);
    fetch(form.action, {
      method: "POST",
      body: fd,
      headers: { "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (res) {
        if (res.ok && res.d.message) {
          bootstrap.Modal.getOrCreateInstance(modal).hide();
          toast("success", res.d.message);
          if (typeof window.insolesPostSubmitHook === "function" &&
              window.insolesPostSubmitHook(res.d, form)) {
            return;
          }
          // If the action was launched from inside the map's detail modal,
          // refresh that modal in place (no full reload) — same contract as
          // workflows.js, so the user stays exactly where they were.
          var inMapModal = lastTrigger && lastTrigger.closest("[data-modal-body]");
          if (inMapModal) {
            var ev = new CustomEvent("workflow:transitioned", {
              bubbles: true, cancelable: true, detail: { response: res.d },
            });
            if (!lastTrigger.dispatchEvent(ev)) return; // map handled it
          }
          setTimeout(function () { window.location.reload(); }, 800);
          return;
        }
        if (res.d.errors) showFieldErrors(modal, res.d.errors);
        toast("error", res.d.error || "Revisa los campos marcados.");
      })
      .catch(function (err) { toast("error", err.message); });
  });
})();
