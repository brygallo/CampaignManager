/* delete_modal.js — wires the global #cm-delete-modal to any trigger that
   carries `data-cm-delete-url` + `data-cm-delete-label`.

   The modal contains a real <form>, so confirming submits POST to the
   same /eliminar/ endpoint that already powers the full-page confirm —
   no custom AJAX, no behavior change in tracing/audit logs.

   To opt in, render a button or anchor like:
     <button type="button"
             class="btn btn-icon btn-sm btn-light-danger"
             data-bs-toggle="modal"
             data-bs-target="#cm-delete-modal"
             data-cm-delete-url="{{ row.urls.delete }}"
             data-cm-delete-label="{{ row.values.0|striptags }}">
       <i data-lucide="trash-2" class="fs-4"></i>
     </button>
*/
(function () {
  "use strict";

  function init() {
    var modal = document.getElementById("cm-delete-modal");
    if (!modal) return;

    var labelTarget = modal.querySelector("[data-cm-delete-label-target]");
    var form = modal.querySelector("[data-cm-delete-form]");
    var confirmBtn = modal.querySelector("[data-cm-delete-confirm]");

    modal.addEventListener("show.bs.modal", function (event) {
      var trigger = event.relatedTarget;
      if (!trigger) return;
      var url = trigger.getAttribute("data-cm-delete-url");
      var label = trigger.getAttribute("data-cm-delete-label") || "—";
      if (!url) return;
      if (form) form.setAttribute("action", url);
      if (labelTarget) labelTarget.textContent = label.trim() || "—";
      if (confirmBtn) {
        confirmBtn.disabled = false;
        confirmBtn.removeAttribute("data-kt-indicator");
      }
    });

    // Show submit indicator and disable double-submits.
    if (form && confirmBtn) {
      form.addEventListener("submit", function () {
        confirmBtn.disabled = true;
        confirmBtn.setAttribute("data-kt-indicator", "on");
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
