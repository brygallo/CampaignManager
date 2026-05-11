/**
 * Sheet modal — bottom-sheet con snap points (peek / full).
 *
 * Cualquier modal con la clase `.cm-sheet-modal` adopta el comportamiento:
 *   - Mobile: se abre en estado "peek" (~40dvh).
 *   - Click en el handle (`[data-sheet-toggle]`) o swipe-up desde él:
 *     toggle entre peek y full (~95dvh).
 *   - Drag en tiempo real: el sheet sigue al dedo durante el gesto y
 *     hace snap al soltar (por distancia o velocidad).
 *   - Auto-full cuando un input/textarea recibe foco (fallback para
 *     navegadores sin soporte de `:has()`).
 *   - Desktop: modal Bootstrap normal, este script no hace nada.
 */
(function () {
  "use strict";

  var FULL_CLASS = "is-full";
  var DRAG_CLASS = "is-dragging";
  var MOBILE_QUERY = "(max-width: 767.98px)";
  var DRAG_VAR = "--cm-sheet-drag";

  // Umbrales de gesto.
  var TAP_THRESHOLD_PX = 8;        // Movimiento mínimo para considerar drag.
  var EXPAND_THRESHOLD_PX = 24;    // Swipe up para expandir desde peek.
  var COLLAPSE_THRESHOLD_PX = 60;  // Swipe down para volver a peek desde full.
  var DISMISS_THRESHOLD_PX = 80;   // Swipe down para cerrar desde peek.
  var FAST_FLICK_PX_PER_MS = 0.6;  // Velocidad para snap por flick.

  function isMobile() {
    return window.matchMedia && window.matchMedia(MOBILE_QUERY).matches;
  }

  function vibrate(ms) {
    if (navigator.vibrate) {
      try { navigator.vibrate(ms); } catch (_) { /* noop */ }
    }
  }

  function setDrag(modal, px) {
    modal.style.setProperty(DRAG_VAR, px + "px");
  }

  function clearDrag(modal) {
    modal.style.removeProperty(DRAG_VAR);
  }

  function toggleFull(modal) {
    if (!modal) return;
    modal.classList.toggle(FULL_CLASS);
    vibrate(8);
  }

  function setFull(modal, full) {
    if (!modal) return;
    var was = modal.classList.contains(FULL_CLASS);
    if (full) modal.classList.add(FULL_CLASS);
    else modal.classList.remove(FULL_CLASS);
    if (was !== full) vibrate(8);
  }

  function closeModal(modal) {
    if (window.bootstrap && window.bootstrap.Modal) {
      var instance = window.bootstrap.Modal.getInstance(modal);
      if (instance) instance.hide();
    }
  }

  // Drag en tiempo real: el sheet sigue al dedo, y al soltar hace snap
  // por distancia o por velocidad (flick).
  function attachDrag(modal, handle) {
    var startY = null;
    var startTime = 0;
    var dragging = false;
    var pointerId = null;

    function getY(ev) {
      if (ev.clientY != null) return ev.clientY;
      if (ev.touches && ev.touches[0]) return ev.touches[0].clientY;
      if (ev.changedTouches && ev.changedTouches[0]) return ev.changedTouches[0].clientY;
      return null;
    }

    function onPointerDown(ev) {
      if (!isMobile()) return;
      startY = getY(ev);
      if (startY == null) return;
      startTime = ev.timeStamp || Date.now();
      dragging = true;
      pointerId = ev.pointerId != null ? ev.pointerId : null;
      if (handle.setPointerCapture && pointerId != null) {
        try { handle.setPointerCapture(pointerId); } catch (_) { /* noop */ }
      }
      modal.classList.add(DRAG_CLASS);
    }

    function onPointerMove(ev) {
      if (!dragging || startY == null) return;
      var y = getY(ev);
      if (y == null) return;
      var delta = y - startY;
      var isFull = modal.classList.contains(FULL_CLASS);
      // Resistencia: si arrastra hacia arriba estando en full, comprimir.
      if (isFull && delta < 0) delta = delta * 0.25;
      // Resistencia hacia arriba en peek (poco recorrido visual hasta el
      // umbral de expand) — el contenido subirá al snap full al soltar.
      if (!isFull && delta < 0) delta = Math.max(delta, -120);
      setDrag(modal, delta);
    }

    function onPointerUp(ev) {
      if (!dragging || startY == null) {
        dragging = false;
        modal.classList.remove(DRAG_CLASS);
        clearDrag(modal);
        return;
      }
      var endY = getY(ev);
      var delta = endY != null ? endY - startY : 0;
      var dt = Math.max(1, (ev.timeStamp || Date.now()) - startTime);
      var velocity = delta / dt; // px/ms; positivo = hacia abajo.
      var isFull = modal.classList.contains(FULL_CLASS);
      var fastFlick = Math.abs(velocity) >= FAST_FLICK_PX_PER_MS;

      // Limpiamos drag visual ANTES de aplicar la clase final, para que la
      // transición de altura corra suave desde el estado actual al snap.
      clearDrag(modal);
      modal.classList.remove(DRAG_CLASS);

      if (Math.abs(delta) < TAP_THRESHOLD_PX) {
        // Tap: toggle peek/full.
        toggleFull(modal);
      } else if (fastFlick && velocity < 0) {
        // Flick rápido hacia arriba → expandir.
        setFull(modal, true);
      } else if (fastFlick && velocity > 0) {
        // Flick rápido hacia abajo.
        if (isFull) setFull(modal, false);
        else closeModal(modal);
      } else if (delta < -EXPAND_THRESHOLD_PX) {
        setFull(modal, true);
      } else if (delta > COLLAPSE_THRESHOLD_PX && isFull) {
        setFull(modal, false);
      } else if (delta > DISMISS_THRESHOLD_PX && !isFull) {
        closeModal(modal);
      }
      // Si nada se cumplió, vuelve al estado previo (drag se canceló).

      dragging = false;
      startY = null;
      pointerId = null;
    }

    function onPointerCancel() {
      dragging = false;
      startY = null;
      pointerId = null;
      modal.classList.remove(DRAG_CLASS);
      clearDrag(modal);
    }

    handle.addEventListener("pointerdown", onPointerDown);
    handle.addEventListener("pointermove", onPointerMove);
    handle.addEventListener("pointerup", onPointerUp);
    handle.addEventListener("pointercancel", onPointerCancel);

    // Click vía teclado (Enter/Space): pointerup ya gestionó pointer.
    handle.addEventListener("click", function (ev) {
      if (ev.detail === 0) {
        toggleFull(modal);
      }
    });
  }

  // Fallback para navegadores sin :has(): cuando un input/textarea/select
  // dentro del sheet recibe foco, expandir a full para evitar que el
  // teclado virtual lo tape.
  function attachKeyboardAutoFull(modal) {
    var supportsHas = false;
    try { supportsHas = CSS && CSS.supports && CSS.supports("selector(:has(*))"); } catch (_) {}
    if (supportsHas) return; // CSS ya lo cubre.

    function isField(el) {
      if (!el || !el.tagName) return false;
      var tag = el.tagName;
      return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
    }

    modal.addEventListener("focusin", function (ev) {
      if (!isMobile()) return;
      if (isField(ev.target)) modal.classList.add(FULL_CLASS);
    });
  }

  function init(modal) {
    if (modal.dataset.cmSheetInit === "1") return;
    modal.dataset.cmSheetInit = "1";

    var handle = modal.querySelector("[data-sheet-toggle]");
    if (handle) attachDrag(modal, handle);

    attachKeyboardAutoFull(modal);

    modal.addEventListener("show.bs.modal", function () {
      // Cada apertura empieza en peek y sin offset de drag.
      modal.classList.remove(FULL_CLASS);
      modal.classList.remove(DRAG_CLASS);
      clearDrag(modal);
    });
    modal.addEventListener("hidden.bs.modal", function () {
      modal.classList.remove(FULL_CLASS);
      modal.classList.remove(DRAG_CLASS);
      clearDrag(modal);
    });
  }

  function bootstrap() {
    var modals = document.querySelectorAll(".cm-sheet-modal");
    for (var i = 0; i < modals.length; i++) init(modals[i]);
  }

  // ===== Public helpers =================================================
  // Exposed so map JS (and any consumer that re-renders modal bodies via
  // AJAX) can manage skeletons + focus consistently without each module
  // re-implementing the dance.

  function focusFirstInput(modal) {
    if (!modal) return;
    var body = modal.querySelector(".modal-body");
    if (!body) return;
    var SEL = "input:not([type=hidden]):not([disabled]), select:not([disabled]), textarea:not([disabled])";
    var field = body.querySelector(SEL);
    if (!field) return;
    // Defer to the next frame so Bootstrap's own focus management (which
    // runs on `shown.bs.modal`) doesn't fight us.
    requestAnimationFrame(function () {
      try { field.focus({ preventScroll: false }); } catch (_) { field.focus(); }
    });
  }

  // Renderiza un skeleton en el body del modal antes de un fetch.
  // El parámetro `shape` permite elegir un layout pre-definido — el más
  // común es "form" (label + input × 3 + botón).
  function showSkeleton(modal, shape) {
    if (!modal) return;
    var body = modal.querySelector(".modal-body");
    if (!body) return;
    body.setAttribute("data-cm-loading", "");
    body.classList.add("cm-skeleton-host");

    var frag = document.createDocumentFragment();
    var blocks = [];
    if (shape === "detail") {
      blocks = ["title", "block", "label", "input", "label", "input"];
    } else if (shape === "compact") {
      blocks = ["label", "input", "label", "input"];
    } else {
      // default: form
      blocks = ["label", "input", "label", "input", "label", "input", "block"];
    }
    for (var i = 0; i < blocks.length; i++) {
      var s = document.createElement("div");
      s.className = "cm-skeleton cm-skeleton--" + blocks[i];
      frag.appendChild(s);
    }
    body.replaceChildren(frag);
  }

  // Reemplaza el contenido del body por nodos DOM ya construidos por el
  // caller (parsed con DOMParser u otro método seguro). Evita pasar
  // strings sin sanear: el caller controla la fuente.
  function replaceBody(modal, nodes) {
    if (!modal) return;
    var body = modal.querySelector(".modal-body");
    if (!body) return;
    body.removeAttribute("data-cm-loading");
    body.classList.remove("cm-skeleton-host");
    if (nodes == null) {
      body.replaceChildren();
      return;
    }
    if (nodes.nodeType) {
      body.replaceChildren(nodes);
      return;
    }
    if (typeof nodes.length === "number") {
      var frag = document.createDocumentFragment();
      for (var i = 0; i < nodes.length; i++) {
        if (nodes[i] && nodes[i].nodeType) frag.appendChild(nodes[i]);
      }
      body.replaceChildren(frag);
    }
  }

  window.cmSheetModal = window.cmSheetModal || {};
  window.cmSheetModal.focusFirstInput = focusFirstInput;
  window.cmSheetModal.showSkeleton = showSkeleton;
  window.cmSheetModal.replaceBody = replaceBody;
  window.cmSheetModal.init = init;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bootstrap);
  } else {
    bootstrap();
  }
})();
