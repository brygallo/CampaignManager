(function (window, document) {
  "use strict";

  const INIT_FLAG = "imageInputInitialized";

  function formatBytes(bytes) {
    if (!Number.isFinite(bytes) || bytes <= 0) return "";
    const units = ["B", "KB", "MB", "GB"];
    let i = 0;
    let size = bytes;
    while (size >= 1024 && i < units.length - 1) {
      size /= 1024;
      i += 1;
    }
    return size.toFixed(size >= 10 || i === 0 ? 0 : 1) + " " + units[i];
  }

  function initImageInput(card) {
    if (card.dataset[INIT_FLAG] === "true") return;
    card.dataset[INIT_FLAG] = "true";

    const input = card.querySelector("[data-file-input]");
    const dropzone = card.querySelector("[data-dropzone]");
    const emptyState = card.querySelector("[data-empty-state]");
    const previewWrap = card.querySelector("[data-new-preview]");
    const previewImg = card.querySelector("[data-new-image]");
    const previewName = card.querySelector("[data-new-name]");
    const previewSize = card.querySelector("[data-new-size]");
    const clearNewBtn = card.querySelector("[data-clear-new]");
    const currentPane = card.querySelector("[data-current]");
    const clearCheckbox = card.querySelector("[data-clear-checkbox]");
    const clearToggle = card.querySelector("[data-clear-toggle]");

    if (!input || !dropzone) return;

    let previewObjectUrl = null;

    function releasePreview() {
      if (previewObjectUrl) {
        URL.revokeObjectURL(previewObjectUrl);
        previewObjectUrl = null;
      }
    }

    function showPreview(file) {
      releasePreview();
      previewObjectUrl = URL.createObjectURL(file);
      if (previewImg) previewImg.src = previewObjectUrl;
      if (previewName) previewName.textContent = file.name;
      if (previewSize) previewSize.textContent = formatBytes(file.size);
      if (emptyState) emptyState.classList.add("d-none");
      if (previewWrap) previewWrap.classList.remove("d-none");
      // Picking a new file overrides any pending removal.
      if (clearCheckbox && clearCheckbox.checked) {
        clearCheckbox.checked = false;
        syncClearToggle();
      }
    }

    function clearPreview() {
      releasePreview();
      if (previewImg) previewImg.removeAttribute("src");
      if (previewName) previewName.textContent = "";
      if (previewSize) previewSize.textContent = "";
      if (previewWrap) previewWrap.classList.add("d-none");
      if (emptyState) emptyState.classList.remove("d-none");
      try { input.value = ""; } catch (_) { /* IE quirks */ }
    }

    function syncClearToggle() {
      if (!clearCheckbox || !clearToggle) return;
      const on = clearCheckbox.checked;
      clearToggle.classList.toggle("is-active", on);
      if (currentPane) currentPane.classList.toggle("is-pending-removal", on);
    }

    input.addEventListener("change", function () {
      const file = input.files && input.files[0];
      if (file && file.type && file.type.startsWith("image/")) {
        showPreview(file);
      } else {
        clearPreview();
      }
    });

    if (clearNewBtn) {
      clearNewBtn.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        clearPreview();
      });
    }

    if (clearCheckbox) {
      clearCheckbox.addEventListener("change", syncClearToggle);
      syncClearToggle();
    }

    // Drag and drop. The native <input> already lives inside the label, but
    // we handle the dragover state explicitly for visual feedback and to
    // accept drops on the broader card area.
    ["dragenter", "dragover"].forEach(function (evt) {
      dropzone.addEventListener(evt, function (event) {
        event.preventDefault();
        event.stopPropagation();
        dropzone.classList.add("is-dragover");
      });
    });
    ["dragleave", "dragend", "drop"].forEach(function (evt) {
      dropzone.addEventListener(evt, function (event) {
        event.preventDefault();
        event.stopPropagation();
        dropzone.classList.remove("is-dragover");
      });
    });
    dropzone.addEventListener("drop", function (event) {
      const files = event.dataTransfer && event.dataTransfer.files;
      if (!files || !files.length) return;
      try {
        // Some browsers (Safari) require a DataTransfer dance to set files.
        const dt = new DataTransfer();
        dt.items.add(files[0]);
        input.files = dt.files;
      } catch (err) {
        // Fall back to a synthetic preview without changing the input value;
        // the form won't carry the file, so warn instead of silently failing.
        console.warn("imageinput: unable to assign dropped file", err);
        return;
      }
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });
  }

  // ---------- Lightbox ----------
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

  // Single delegated click handler — works for content injected later.
  document.addEventListener("click", function (event) {
    const trigger = event.target.closest("[data-image-lightbox]");
    if (!trigger) return;
    const src = trigger.getAttribute("data-image-src") || trigger.getAttribute("href");
    if (!src) return;
    event.preventDefault();
    openLightbox(src, trigger.getAttribute("data-image-name") || "");
  });

  function initImageInputs(scope) {
    const root = scope || document;
    const cards = root.querySelectorAll
      ? root.querySelectorAll("[data-image-input]")
      : [];
    cards.forEach(initImageInput);
    if (root !== document && root.matches && root.matches("[data-image-input]")) {
      initImageInput(root);
    }
  }

  window.initImageInputs = initImageInputs;

  // Hook into the project's form-widget bootstrap so AJAX-loaded forms
  // (map create modal, workflows modal, …) get initialized too.
  const previousInit = window.initFormWidgets;
  window.initFormWidgets = function (selector) {
    if (typeof previousInit === "function") {
      previousInit(selector);
    }
    let scope = document;
    if (selector) {
      scope = selector.jquery ? selector.get(0) : selector;
    }
    initImageInputs(scope || document);
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { initImageInputs(); });
  } else {
    initImageInputs();
  }
})(window, document);
