/**
 * Sheet modal — bottom-sheet con snap points (peek / full).
 *
 * Cualquier modal con la clase `.cm-sheet-modal` adopta el comportamiento:
 *   - Mobile: se abre en estado "peek" (~55dvh).
 *   - Click en el handle (`[data-sheet-toggle]`) o swipe-up desde él:
 *     toggle entre peek y full (~95dvh).
 *   - Desktop: modal Bootstrap normal, este script no hace nada.
 *
 * Se engancha en el evento `show.bs.modal` de Bootstrap. No reemplaza el
 * comportamiento de Bootstrap, solo añade clases CSS y listeners.
 */
(function () {
  "use strict";

  var FULL_CLASS = "is-full";
  var MOBILE_QUERY = "(max-width: 767.98px)";

  function isMobile() {
    return window.matchMedia && window.matchMedia(MOBILE_QUERY).matches;
  }

  function toggleFull(modal) {
    if (!modal) return;
    modal.classList.toggle(FULL_CLASS);
  }

  function setPeek(modal) {
    if (modal) modal.classList.remove(FULL_CLASS);
  }

  // Drag por gesto: si el usuario arrastra el handle hacia arriba > 24px
  // expandimos a full; hacia abajo > 60px desde full volvemos a peek;
  // hacia abajo > 80px desde peek cerramos el modal.
  function attachDrag(modal, handle) {
    var startY = null;
    var dragging = false;

    function onPointerDown(ev) {
      if (!isMobile()) return;
      startY = ev.clientY != null ? ev.clientY : (ev.touches && ev.touches[0].clientY);
      dragging = true;
      handle.setPointerCapture && ev.pointerId != null && handle.setPointerCapture(ev.pointerId);
    }

    function onPointerUp(ev) {
      if (!dragging || startY == null) { dragging = false; return; }
      var endY = ev.clientY != null ? ev.clientY : (ev.changedTouches && ev.changedTouches[0].clientY);
      var delta = endY - startY;
      var isFull = modal.classList.contains(FULL_CLASS);

      if (Math.abs(delta) < 8) {
        // Movimiento mínimo → tratar como click.
        toggleFull(modal);
      } else if (delta < -24) {
        // Swipe up → expandir.
        modal.classList.add(FULL_CLASS);
      } else if (delta > 60 && isFull) {
        // Swipe down desde full → volver a peek.
        modal.classList.remove(FULL_CLASS);
      } else if (delta > 80 && !isFull) {
        // Swipe down desde peek → cerrar.
        if (window.bootstrap && window.bootstrap.Modal) {
          var instance = window.bootstrap.Modal.getInstance(modal);
          if (instance) instance.hide();
        }
      }
      dragging = false;
      startY = null;
    }

    handle.addEventListener("pointerdown", onPointerDown);
    handle.addEventListener("pointerup", onPointerUp);
    handle.addEventListener("pointercancel", function () { dragging = false; startY = null; });

    // Click directo (también dispara onPointerUp con delta ~0; mantenemos
    // por accesibilidad / teclado).
    handle.addEventListener("click", function (ev) {
      // Si pointerup ya hizo el toggle, evitamos doble-toggle.
      if (ev.detail === 0) {
        // Click via teclado (Enter/Space). Toggle.
        toggleFull(modal);
      }
    });
  }

  function init(modal) {
    if (modal.dataset.cmSheetInit === "1") return;
    modal.dataset.cmSheetInit = "1";

    var handle = modal.querySelector("[data-sheet-toggle]");
    if (handle) {
      attachDrag(modal, handle);
    }

    modal.addEventListener("show.bs.modal", function () {
      // Cada apertura empieza en peek (a menos que el page lo haya pre-fijado).
      setPeek(modal);
    });
    modal.addEventListener("hidden.bs.modal", function () {
      setPeek(modal);
    });
  }

  function bootstrap() {
    var modals = document.querySelectorAll(".cm-sheet-modal");
    for (var i = 0; i < modals.length; i++) init(modals[i]);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootstrap);
  } else {
    bootstrap();
  }
})();
