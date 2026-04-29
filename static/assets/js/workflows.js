/**
 * Workflow transition handler.
 *
 * Listens for clicks on `a.transition` and `button.transition` and triggers
 * the appropriate UX flow based on data-* attributes:
 *
 *   - data-url           Endpoint of ChangeStateView (POST + GET supported).
 *   - data-transition    Name of the transition method on the model.
 *   - data-form          Dotted path to a Django form (presence enables modal mode).
 *   - data-input         "password" | "text" | "" (presence shows a single-field prompt modal).
 *   - data-title         Modal title.
 *   - data-text          Confirmation/help text.
 *   - data-placeholder   Placeholder for prompt input.
 *   - data-max_size      Max file size in MB (informational).
 *
 * Flow:
 *   1. data-form present → GET data-url?transition=NAME, render returned HTML in a modal,
 *      submit posts the modal form (with FormData, including files).
 *   2. data-input present → show a prompt modal asking for a single value (text or password),
 *      submit posts {transition, value} as FormData.
 *   3. Otherwise → confirm dialog, on accept POST {transition} as FormData.
 *
 * On success: reload the page (the surrounding views always re-render after a transition).
 * On error: show a Lobibox notification with the message returned by the server.
 *
 * Depends on: jQuery, Bootstrap 5 modal, Lobibox (already loaded via base/js.html).
 */
(function ($) {
  "use strict";

  /* ----- helpers ----- */

  function getCsrfToken() {
    const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    if (m) return decodeURIComponent(m[1]);
    const el = document.querySelector("[name=csrfmiddlewaretoken]");
    return el ? el.value : "";
  }

  function notify(type, message) {
    if (window.Lobibox && Lobibox.notify) {
      Lobibox.notify(type, {
        position: "bottom right",
        msg: message,
        sound: false,
        delay: 3500,
        size: "mini",
      });
      return;
    }
    // Fallback if Lobibox is not loaded.
    alert(message);
  }

  function confirmDialog({ title, text }) {
    return new Promise((resolve) => {
      const $modal = $(`
        <div class="modal fade" tabindex="-1">
          <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content rounded-4">
              <div class="modal-header">
                <h5 class="modal-title">${title || "¿Confirmar acción?"}</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Cerrar"></button>
              </div>
              <div class="modal-body">${text || "¿Estás seguro de continuar?"}</div>
              <div class="modal-footer">
                <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancelar</button>
                <button type="button" class="btn btn-grd btn-grd-primary" data-action="ok">Confirmar</button>
              </div>
            </div>
          </div>
        </div>
      `).appendTo("body");
      const modal = new bootstrap.Modal($modal[0]);
      let confirmed = false;
      $modal.find('[data-action="ok"]').on("click", () => {
        confirmed = true;
        modal.hide();
      });
      $modal.on("hidden.bs.modal", () => {
        $modal.remove();
        resolve(confirmed);
      });
      modal.show();
    });
  }

  function promptDialog({ title, text, placeholder, inputType }) {
    return new Promise((resolve) => {
      const isPwd = (inputType || "text") === "password";
      const $modal = $(`
        <div class="modal fade" tabindex="-1">
          <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content rounded-4">
              <div class="modal-header">
                <h5 class="modal-title">${title || "Ingresa un valor"}</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Cerrar"></button>
              </div>
              <form>
                <div class="modal-body">
                  ${text ? `<p class="text-muted">${text}</p>` : ""}
                  <input type="${isPwd ? "password" : "text"}"
                         class="form-control"
                         name="value"
                         placeholder="${placeholder || ""}"
                         required>
                </div>
                <div class="modal-footer">
                  <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancelar</button>
                  <button type="submit" class="btn btn-grd btn-grd-primary">Confirmar</button>
                </div>
              </form>
            </div>
          </div>
        </div>
      `).appendTo("body");
      const modal = new bootstrap.Modal($modal[0]);
      let value = null;
      $modal.find("form").on("submit", function (e) {
        e.preventDefault();
        value = $modal.find('input[name="value"]').val();
        modal.hide();
      });
      $modal.on("shown.bs.modal", () => $modal.find('input[name="value"]').trigger("focus"));
      $modal.on("hidden.bs.modal", () => {
        $modal.remove();
        resolve(value);
      });
      modal.show();
    });
  }

  function formModal({ title, html, onSubmit }) {
    return new Promise((resolve) => {
      const $modal = $(`
        <div class="modal fade" tabindex="-1">
          <div class="modal-dialog modal-dialog-centered modal-lg">
            <div class="modal-content rounded-4">
              <div class="modal-header">
                <h5 class="modal-title">${title || "Confirmar transición"}</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Cerrar"></button>
              </div>
              <div class="modal-body"></div>
              <div class="modal-footer">
                <button type="button" class="btn btn-outline-secondary" data-bs-dismiss="modal">Cancelar</button>
                <button type="button" class="btn btn-grd btn-grd-primary" data-action="submit">Confirmar</button>
              </div>
            </div>
          </div>
        </div>
      `).appendTo("body");
      $modal.find(".modal-body").html(html);
      const modal = new bootstrap.Modal($modal[0]);
      let resolved = false;
      $modal.find('[data-action="submit"]').on("click", async () => {
        const $form = $modal.find("form").first();
        if (!$form.length) {
          modal.hide();
          return;
        }
        const formEl = $form[0];
        if (!formEl.checkValidity()) {
          formEl.reportValidity();
          return;
        }
        const fd = new FormData(formEl);
        resolved = true;
        modal.hide();
        const ok = await onSubmit(fd);
        resolve(ok);
      });
      $modal.on("hidden.bs.modal", () => {
        $modal.remove();
        if (!resolved) resolve(false);
      });
      modal.show();
    });
  }

  /* ----- HTTP ----- */

  async function fetchTransitionForm(url, transitionName) {
    const sep = url.indexOf("?") === -1 ? "?" : "&";
    const res = await fetch(`${url}${sep}transition=${encodeURIComponent(transitionName)}`, {
      method: "GET",
      headers: { "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.message || data.error || "No se pudo obtener el formulario.");
    }
    return data;
  }

  async function postTransition(url, formData) {
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "X-CSRFToken": getCsrfToken(),
        "X-Requested-With": "XMLHttpRequest",
      },
      body: formData,
      credentials: "same-origin",
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.error || data.message_error) {
      throw new Error(data.error || data.message_error || data.message || "No se pudo ejecutar la transición.");
    }
    return data;
  }

  /* ----- main click handler ----- */

  $(document).on("click", "a.transition, button.transition", async function (e) {
    e.preventDefault();
    const $btn = $(this);
    const url = $btn.data("url");
    const transitionName = $btn.data("transition");
    const formPath = $btn.data("form");
    const inputType = $btn.data("input");
    const title = $btn.data("title");
    const text = $btn.data("text");
    const placeholder = $btn.data("placeholder");

    if (!url || !transitionName) {
      notify("error", "Configuración inválida del botón de transición.");
      return;
    }

    try {
      // Mode 1: server-rendered form
      if (formPath) {
        const data = await fetchTransitionForm(url, transitionName);
        if (data.error || data.message_error) {
          notify("error", data.error || data.message_error);
          return;
        }
        if (!data.template) {
          notify("error", "El formulario de transición está vacío.");
          return;
        }
        await formModal({
          title: title || "Completa el formulario",
          html: data.template,
          onSubmit: async (fd) => {
            fd.append("transition", transitionName);
            try {
              const res = await postTransition(url, fd);
              notify("success", res.message || "Transición ejecutada.");
              setTimeout(() => window.location.reload(), 600);
              return true;
            } catch (err) {
              notify("error", err.message);
              return false;
            }
          },
        });
        return;
      }

      // Mode 2: single-field prompt
      if (inputType) {
        const value = await promptDialog({
          title: title || "Ingresa el valor",
          text,
          placeholder,
          inputType,
        });
        if (value === null) return; // cancelled
        const fd = new FormData();
        fd.append("transition", transitionName);
        fd.append("value", value);
        const res = await postTransition(url, fd);
        notify("success", res.message || "Transición ejecutada.");
        setTimeout(() => window.location.reload(), 600);
        return;
      }

      // Mode 3: simple confirmation
      const ok = await confirmDialog({
        title: title || "Confirmar transición",
        text: text || "¿Estás seguro de continuar?",
      });
      if (!ok) return;
      const fd = new FormData();
      fd.append("transition", transitionName);
      const res = await postTransition(url, fd);
      notify("success", res.message || "Transición ejecutada.");
      setTimeout(() => window.location.reload(), 600);
    } catch (err) {
      notify("error", err.message || String(err));
    }
  });
})(jQuery);
