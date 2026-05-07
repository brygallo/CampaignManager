(function (window, document) {
  "use strict";

  // ---------- Lightbox ----------
  // KTImageInput from the Metronic theme handles the upload UI itself; this
  // file only adds the lightbox preview (data-image-lightbox triggers) and
  // the Django ClearableFileInput compatibility shim. Initialization of the
  // image-input component is handled by KTComponents.init() at page load and
  // by initFormWidgets() (forms/widgets.js) for AJAX-loaded forms.
  let lightboxState = { initialized: false };

  function ensureLightbox() {
    if (lightboxState.initialized) return lightboxState;
    const modalEl = document.getElementById("image-lightbox-modal");
    if (!modalEl || !window.bootstrap || !window.bootstrap.Modal) return null;
    lightboxState = {
      initialized: true,
      modal: new window.bootstrap.Modal(modalEl, { backdrop: true }),
      el: modalEl,
      img: modalEl.querySelector("#image-lightbox-image"),
      title: modalEl.querySelector("#image-lightbox-title"),
      subtitle: modalEl.querySelector("#image-lightbox-subtitle"),
      openLink: modalEl.querySelector("#image-lightbox-open"),
    };
    modalEl.addEventListener("hidden.bs.modal", function () {
      if (lightboxState.img) lightboxState.img.removeAttribute("src");
    });
    return lightboxState;
  }

  function openLightbox(src, name) {
    const state = ensureLightbox();
    if (!state) {
      window.open(src, "_blank", "noopener");
      return;
    }
    if (state.img) state.img.src = src;
    if (state.title) state.title.textContent = name || "Vista previa";
    if (state.subtitle) state.subtitle.textContent = name || "";
    if (state.openLink) state.openLink.setAttribute("href", src);
    state.modal.show();
  }

  document.addEventListener("click", function (event) {
    const trigger = event.target.closest("[data-image-lightbox]");
    if (!trigger) return;
    const src = trigger.getAttribute("data-image-src") || trigger.getAttribute("href");
    if (!src) return;
    event.preventDefault();
    openLightbox(src, trigger.getAttribute("data-image-name") || "");
  });

  // ---------- Django ClearableFileInput compatibility ----------
  // KTImageInput writes "0" into the hidden input on cancel and doesn't reset
  // it on change. Django's CheckboxInput.value_from_datadict treats any
  // non-empty string other than "false" as truthy on <name>-clear — including
  // "0" — and would clear the file. Selecting a new file while the hidden is
  // "1" (after a remove click) would also raise FILE_INPUT_CONTRADICTION.
  // Both cases need the hidden to be empty; only the genuine remove path
  // must keep "1".
  function resetClearHidden(root) {
    if (!root) return;
    const hidden = root.querySelector('input[type="hidden"][name$="-clear"]');
    if (hidden) hidden.value = "";
  }

  // Cancel and change run KTImageInput's own handlers in target phase; our
  // bubble-phase listeners fire afterwards and overwrite the stale value.
  document.addEventListener("click", function (event) {
    const cancelBtn = event.target.closest('[data-kt-image-input-action="cancel"]');
    if (!cancelBtn) return;
    resetClearHidden(cancelBtn.closest("[data-kt-image-input]"));
  });

  document.addEventListener("change", function (event) {
    const target = event.target;
    if (!target || target.tagName !== "INPUT" || target.type !== "file") return;
    resetClearHidden(target.closest("[data-kt-image-input]"));
  });
})(window, document);
