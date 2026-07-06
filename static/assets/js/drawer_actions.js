/**
 * Drawer action driver (CampaignManager-native).
 *
 * Side-panel sibling of insoles_actions.js. Reuses the EXACT same backend
 * contract (apps/insoles InstanceBase* views) but renders the form in a
 * Metronic KTDrawer sliding from the right instead of a Bootstrap modal.
 * Any endpoint that works with `.insoles-action` also works with
 * `.drawer-action` — no backend changes required.
 *
 * Contract (matches apps/insoles/views.py InstanceBaseFormView):
 *   GET  data-url              -> { template, create_url, title, confirm_button }
 *   POST create_url (FormData) -> { message }        (success)
 *                              -> { error, errors }  (HTTP 400, field errors)
 *
 * Usage: a button/link with class "drawer-action" and data-url="<GET url>".
 * Optionally data-title overrides the drawer title. On success it toasts and
 * reloads, unless a page provides window.drawerPostSubmitHook(data, form) that
 * returns truthy to take over.
 */
(function () {
  if (window.__cmDrawerActionsBound) return;
  window.__cmDrawerActionsBound = true;

  var DRAWER_ID = "insoles-drawer";
  var lastTrigger = null;

  function drawerEl() {
    return document.getElementById(DRAWER_ID);
  }

  function toast(type, message) {
    if (typeof window.toastr !== "undefined") {
      (window.toastr[type] || window.toastr.info)(message);
    } else if (window.Swal) {
      window.Swal.fire({ text: message, icon: type, timer: 2500, showConfirmButton: false });
    }
  }

  function drawerInstance() {
    var el = drawerEl();
    if (!el || !window.KTDrawer) return null;
    var inst = window.KTDrawer.getInstance(el);
    if (!inst && typeof window.KTDrawer.createInstances === "function") {
      window.KTDrawer.createInstances();
      inst = window.KTDrawer.getInstance(el);
    }
    return inst;
  }

  function showDrawer() {
    var inst = drawerInstance();
    if (inst) inst.show();
    else if (drawerEl()) drawerEl().classList.add("drawer-on");
  }

  function hideDrawer() {
    var inst = drawerInstance();
    if (inst) inst.hide();
    else if (drawerEl()) drawerEl().classList.remove("drawer-on");
  }

  function clearFieldErrors(scope) {
    scope.querySelectorAll(".is-invalid").forEach(function (field) {
      field.classList.remove("is-invalid");
    });
    scope.querySelectorAll(".invalid-feedback[data-drawer-error]").forEach(function (box) {
      box.remove();
    });
    var alert = scope.querySelector("[data-drawer-error-summary]");
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

  function showErrorSummary(scope, messages) {
    messages = (messages || []).filter(Boolean);
    if (!messages.length) return;
    var body = scope.querySelector("[data-drawer-body]");
    if (!body) return;
    var alert = document.createElement("div");
    alert.className = "alert alert-danger d-flex align-items-start p-4 mb-5";
    alert.setAttribute("data-drawer-error-summary", "true");
    alert.setAttribute("role", "alert");
    alert.innerHTML = '<i data-lucide="shield-x" class="fs-2 text-danger me-3"></i><div></div>';
    var content = alert.querySelector("div");
    messages.forEach(function (message) {
      var line = document.createElement("div");
      line.textContent = message;
      content.appendChild(line);
    });
    body.prepend(alert);
    if (window.cmRenderIcons) window.cmRenderIcons();
  }

  function showFieldErrors(scope, errors) {
    clearFieldErrors(scope);
    var summary = [];
    Object.keys(errors || {}).forEach(function (name) {
      var text = errorText(errors[name]);
      if (!text) return;
      if (name === "__all__") {
        summary.push(text);
        return;
      }
      var input = scope.querySelector("#id_" + name) ||
        scope.querySelector('[name="' + name + '"]');
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
        box.setAttribute("data-drawer-error", "true");
        box.setAttribute("role", "alert");
        row.appendChild(box);
      }
      if (box) {
        box.classList.add("d-block");
        box.textContent = text;
      }
    });
    showErrorSummary(scope, summary);
  }

  function buildDrawer(data) {
    var drawer = drawerEl();
    if (!drawer) {
      toast("error", "No se encontró el panel lateral.");
      return;
    }
    var form = drawer.querySelector("form");
    form.action = data.create_url;
    var body = drawer.querySelector("[data-drawer-body]");
    // data.template is server-rendered form HTML (render_to_string), trusted —
    // same model as insoles_actions.js buildModal.
    body.innerHTML = data.template || "";
    var label = drawer.querySelector("[data-drawer-title]");
    if (label) label.textContent = data.title || "Formulario";
    var confirmBtn = drawer.querySelector("[data-drawer-confirm]");
    if (confirmBtn) confirmBtn.textContent = data.confirm_button || "Guardar";
    var submitBtn = drawer.querySelector('button[type="submit"]');
    if (submitBtn) submitBtn.classList.toggle("d-none", !!data.read_only);
    if (window.initFormWidgets) window.initFormWidgets(drawer);
    if (window.cmRenderIcons) window.cmRenderIcons();
    showDrawer();
    // Generic extension point (mirrors Bootstrap's "shown.bs.modal"): pages can
    // listen for "drawer:shown" to (re)wire behavior on the injected form, e.g.
    // survey builder field toggling in builder_form.js.
    drawer.dispatchEvent(new CustomEvent("drawer:shown", {
      bubbles: true,
      detail: { drawer: drawer, response: data },
    }));
  }

  // Open: GET the form and render it in the shared drawer.
  document.addEventListener("click", function (event) {
    var trigger = event.target.closest(".drawer-action");
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
        if (!res.ok) throw new Error(res.d.error || "No se pudo abrir el panel.");
        if (trigger.dataset.title) res.d.title = trigger.dataset.title;
        buildDrawer(res.d);
      })
      .catch(function (err) { toast("error", err.message); });
  });

  // Submit: POST the form, then toast + reload (or a page-provided hook).
  document.addEventListener("submit", function (event) {
    var drawer = drawerEl();
    if (!drawer || !drawer.contains(event.target)) return;
    event.preventDefault();
    var form = event.target;
    clearFieldErrors(drawer);
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
          hideDrawer();
          toast("success", res.d.message);
          if (typeof window.drawerPostSubmitHook === "function" &&
              window.drawerPostSubmitHook(res.d, form)) {
            return;
          }
          setTimeout(function () { window.location.reload(); }, 800);
          return;
        }
        if (res.d.errors) showFieldErrors(drawer, res.d.errors);
        toast("error", res.d.error || "Revisa los campos marcados.");
      })
      .catch(function (err) { toast("error", err.message); });
  });
})();
