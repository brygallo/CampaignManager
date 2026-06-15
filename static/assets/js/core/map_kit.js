/**
 * CmMapKit — shared frontend kit for the full-screen Leaflet map pages
 * (territorial_ads and field_surveys).
 *
 * Centralises the plumbing that used to be duplicated in both map.js files:
 * map bootstrapping (basemaps, zoom, panel, filters, geolocation, click
 * gating, data loading) plus the AJAX modal helpers (create/update/delete/
 * detail). Each app keeps a thin config module with its own pins, clusters
 * and data rendering.
 *
 * Everything degrades gracefully when optional globals are missing:
 * LeafletBasemaps, MapState, GeolocationGate, L.markerClusterGroup,
 * cmFormsets, cmSheetModal, bootstrap.
 */
(function (window, document) {
  "use strict";

  /* ------------------------------------------------------------------
   * Small shared helpers
   * ------------------------------------------------------------------ */

  function safeIconName(icon, aliases, fallback) {
    var raw = (icon || "").toLowerCase();
    if (aliases && aliases[raw]) {
      return aliases[raw];
    }
    return /^[a-z0-9-]+$/i.test(icon || "") ? icon : (fallback || "circle");
  }

  function safeColor(color, fallback) {
    return /^#[0-9a-f]{3,8}$/i.test(color || "") ? color : (fallback || "#3388ff");
  }

  function buildCreateUrl(base, latlng, mapState, paramNames) {
    var names = paramNames || {};
    var latName = names.lat || "latitude";
    var lngName = names.lng || "longitude";
    var params = new URLSearchParams();
    params.set(latName, latlng.lat.toFixed(6));
    params.set(lngName, latlng.lng.toFixed(6));
    if (mapState && mapState.zoom !== undefined && mapState.zoom !== null) {
      params.set("map_zoom", String(mapState.zoom));
    }
    if (mapState && mapState.layer) {
      params.set("map_layer", mapState.layer);
    }
    return base + (base.indexOf("?") === -1 ? "?" : "&") + params.toString();
  }

  function setHtml(node, html) {
    // Content originates from our own Django templates with autoescape on,
    // so user-supplied fields are HTML-escaped before reaching the browser.
    if (!node) {
      return;
    }
    node.innerHTML = html;
    if (window.cmFormsets) {
      window.cmFormsets.init(node);
    }
  }

  function updateCount(counterEl, count, labels) {
    if (!counterEl) {
      return;
    }
    labels = labels || {};
    var singular = labels.singular || "registro";
    var plural = labels.plural || "registros";
    var numberEl = counterEl.querySelector("[data-pin-count-number]");
    var labelEl = counterEl.querySelector("[data-pin-count-label]");
    var label = count === 1 ? singular : plural;
    if (numberEl && labelEl) {
      numberEl.textContent = String(count);
      labelEl.textContent = label;
      counterEl.setAttribute("aria-label", count + " " + label);
      counterEl.classList.toggle("is-empty", count === 0);
      return;
    }
    counterEl.textContent = count + " " + label;
  }

  function updateFilterCount(badgeEl, triggerEls, filters) {
    if (!filters) {
      return;
    }
    var count = 0;
    Array.prototype.forEach.call(filters.elements, function (input) {
      if (input.name && input.value) {
        count += 1;
      }
    });
    if (badgeEl) {
      badgeEl.textContent = count ? String(count) : "";
      if (count > 0) {
        badgeEl.removeAttribute("hidden");
      } else {
        badgeEl.setAttribute("hidden", "");
      }
    }
    if (triggerEls) {
      Array.prototype.forEach.call(triggerEls, function (btn) {
        btn.classList.toggle("has-active-filters", count > 0);
      });
    }
  }

  function setLocationButton(button, label, disabled) {
    if (!button) {
      return;
    }
    button.disabled = !!disabled;
    button.setAttribute("aria-label", label);
    button.setAttribute("title", label);
    button.classList.toggle("is-busy", !!disabled);
  }

  function showLocationStatus(statusEl, message, tone, autoHideMs) {
    if (!statusEl) {
      return;
    }
    statusEl.textContent = message;
    statusEl.dataset.tone = tone || "info";
    statusEl.removeAttribute("hidden");
    if (statusEl._hideTimer) {
      window.clearTimeout(statusEl._hideTimer);
    }
    if (autoHideMs) {
      statusEl._hideTimer = window.setTimeout(function () {
        statusEl.setAttribute("hidden", "");
      }, autoHideMs);
    }
  }

  function roundMetersForUi(value) {
    if (!Number.isFinite(value)) {
      return null;
    }
    if (value <= 100) {
      return Math.max(10, Math.round(value / 10) * 10);
    }
    return Math.round(value / 50) * 50;
  }

  function distanceAcrossWidthAtZoom(map, latlng, zoom, widthPx) {
    var point = map.project(latlng, zoom);
    var shifted = window.L.point(point.x + widthPx, point.y);
    var shiftedLatLng = map.unproject(shifted, zoom);
    return latlng.distanceTo(shiftedLatLng);
  }

  function findZoomForTargetMeters(map, latlng, targetMeters, widthPx) {
    var minZoom = Number.isFinite(map.getMinZoom()) ? map.getMinZoom() : 0;
    var maxZoom = Number.isFinite(map.getMaxZoom()) ? map.getMaxZoom() : 20;
    var chosenZoom = maxZoom;
    var zoom;
    for (zoom = maxZoom; zoom >= minZoom; zoom -= 1) {
      if (distanceAcrossWidthAtZoom(map, latlng, zoom, widthPx) <= targetMeters) {
        chosenZoom = zoom;
      } else {
        break;
      }
    }
    return chosenZoom;
  }

  function geolocationErrorMessage(error) {
    if (!window.isSecureContext) {
      return "Para usar ubicación abre el sitio con HTTPS.";
    }
    if (!error) {
      return "No se pudo obtener tu ubicación.";
    }
    if (error.code === error.PERMISSION_DENIED) {
      return "Activa el permiso de ubicación en el navegador.";
    }
    if (error.code === error.POSITION_UNAVAILABLE) {
      return "Tu celular no entregó una ubicación.";
    }
    if (error.code === error.TIMEOUT) {
      return "La ubicación tardó demasiado. Intenta de nuevo.";
    }
    return "No se pudo obtener tu ubicación.";
  }

  function getLayerMaxZoom(layer, fallback) {
    if (!layer || !layer.options || layer.options.maxZoom === undefined) {
      return fallback;
    }
    var maxZoom = parseInt(layer.options.maxZoom, 10);
    return Number.isFinite(maxZoom) ? maxZoom : fallback;
  }

  function setupPanel(shell, panel, triggers, map) {
    if (!shell || !panel) {
      return { open: function () {}, close: function () {}, toggle: function () {} };
    }

    function setState(next) {
      shell.setAttribute("data-panel-state", next);
      var expanded = next === "expanded";
      panel.setAttribute("aria-hidden", expanded ? "false" : "true");
      Array.prototype.forEach.call(triggers, function (btn) {
        if (btn.hasAttribute("aria-controls")) {
          btn.setAttribute("aria-expanded", expanded ? "true" : "false");
        }
      });
      if (map) {
        window.setTimeout(function () { map.invalidateSize(); }, 320);
      }
    }

    function open() { setState("expanded"); }
    function close() { setState("collapsed"); }
    function toggle() {
      setState(shell.getAttribute("data-panel-state") === "expanded" ? "collapsed" : "expanded");
    }

    Array.prototype.forEach.call(triggers, function (btn) {
      btn.addEventListener("click", function (event) {
        event.preventDefault();
        toggle();
      });
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && shell.getAttribute("data-panel-state") === "expanded") {
        close();
      }
    });

    return { open: open, close: close, toggle: toggle };
  }

  function detailHtmlFromPage(html) {
    var doc = new window.DOMParser().parseFromString(html, "text/html");
    var container = doc.querySelector("#kt_app_content_container");
    if (!container) {
      return "";
    }

    var clone = container.cloneNode(true);
    var toolbar = clone.querySelector(".app-toolbar-wrapper");
    if (toolbar) {
      toolbar.remove();
    }
    return clone.innerHTML;
  }

  function initDynamicContent(scope) {
    if (window.initFormWidgets) {
      window.initFormWidgets(scope);
    } else if (window.initLeafletMaps) {
      window.initLeafletMaps(scope);
    }
    if (window.KTApp && window.KTApp.init) {
      window.KTApp.init();
    }
  }

  // Base widget init for AJAX-injected forms. `hook` lets each app run its
  // own extra setup (e.g. CostTypeAmountToggle, type→size filtering).
  function initDynamicForm(scope, hook) {
    if (window.initFormWidgets) {
      window.initFormWidgets(scope);
    } else if (window.initLeafletMaps) {
      window.initLeafletMaps(scope);
    }
    if (hook) {
      hook(scope);
    }
  }

  function applyActionLink(modalEl, selector, url) {
    var el = modalEl.querySelector(selector);
    if (!el) return;
    if (url) {
      el.href = url;
      el.dataset.actionUrl = url;
      el.classList.remove("d-none");
      el.classList.add("d-flex");
    } else {
      el.removeAttribute("href");
      delete el.dataset.actionUrl;
      el.classList.add("d-none");
      el.classList.remove("d-flex");
    }
  }

  function loadingHtml(text) {
    return (
      '<div class="text-center text-muted py-10" role="status" aria-live="polite">' +
        '<div class="spinner-border" aria-hidden="true"></div>' +
        '<div class="mt-3">' + text + '</div>' +
      '</div>'
    );
  }

  // Disabled state + inline spinner for submit/confirm buttons while a
  // request is in flight.
  function setSubmitBusy(button, busy) {
    if (!button) {
      return;
    }
    button.disabled = !!busy;
    var spinner = button.querySelector("[data-cm-busy-spinner]");
    if (busy) {
      if (!spinner) {
        spinner = document.createElement("span");
        spinner.className = "spinner-border spinner-border-sm ms-2";
        spinner.setAttribute("data-cm-busy-spinner", "");
        spinner.setAttribute("aria-hidden", "true");
        button.appendChild(spinner);
      }
    } else if (spinner && spinner.parentNode) {
      spinner.parentNode.removeChild(spinner);
    }
  }

  /* ------------------------------------------------------------------
   * Unsaved-changes guard for create/update modals
   * ------------------------------------------------------------------ */

  var UNSAVED_CONFIRM_TEXT = "Tienes cambios sin guardar. ¿Cerrar de todos modos?";

  function attachDirtyGuard(modalEl) {
    if (!modalEl || modalEl._cmGuardBound) {
      return;
    }
    modalEl._cmGuardBound = true;
    modalEl.addEventListener("hide.bs.modal", function (event) {
      if (modalEl._cmDirty && !modalEl._cmSaved) {
        if (window.confirm(UNSAVED_CONFIRM_TEXT)) {
          modalEl._cmDirty = false;
        } else {
          event.preventDefault();
        }
      }
    });
  }

  function resetDirtyState(modalEl) {
    if (modalEl) {
      modalEl._cmDirty = false;
      modalEl._cmSaved = false;
    }
  }

  function trackFormDirty(modalEl, form) {
    if (!modalEl || !form) {
      return;
    }
    function markDirty() { modalEl._cmDirty = true; }
    form.addEventListener("input", markDirty);
    form.addEventListener("change", markDirty);
  }

  /* ------------------------------------------------------------------
   * Modal openers (create / update / delete / detail / json)
   * ------------------------------------------------------------------ */

  /**
   * AJAX create modal.
   *
   * opts: modalEl, createUrl, latlng, mapState, onSaved,
   *       bodySelector ("[data-create-modal-body]"),
   *       submitSelector ("[data-create-submit]"),
   *       formSelector ("[data-map-create-form]"),
   *       paramNames ({lat:"latitude", lng:"longitude"}),
   *       headerName ("X-Map-Create", pass null to skip),
   *       postToFormAction (false → POST to the built GET url),
   *       initFormHook, saveErrorText, loadErrorText,
   *       allowRedirectFallback (true; AJAX-only endpoints pass false).
   */
  function openCreateModal(opts) {
    opts = opts || {};
    var modalEl = opts.modalEl;
    var createUrl = opts.createUrl;
    if (!createUrl) {
      return;
    }
    var url = buildCreateUrl(createUrl, opts.latlng, opts.mapState, opts.paramNames);
    if (!modalEl || !window.bootstrap) {
      if (opts.allowRedirectFallback !== false) {
        window.location.href = url;
      }
      return;
    }

    var bodySelector = opts.bodySelector || "[data-create-modal-body]";
    var submitSelector = opts.submitSelector || "[data-create-submit]";
    var formSelector = opts.formSelector || "[data-map-create-form]";
    var headerName = opts.headerName === undefined ? "X-Map-Create" : opts.headerName;
    var saveErrorText = opts.saveErrorText || "No se pudo guardar el registro.";
    var loadErrorText = opts.loadErrorText || "No se pudo cargar el formulario.";
    var onSaved = opts.onSaved;

    var bodyEl = modalEl.querySelector(bodySelector);
    var submitButton = modalEl.querySelector(submitSelector);
    setHtml(bodyEl, loadingHtml("Cargando formulario..."));
    attachDirtyGuard(modalEl);
    resetDirtyState(modalEl);

    var modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();

    function requestHeaders() {
      var headers = { "X-Requested-With": "XMLHttpRequest" };
      if (headerName) {
        headers[headerName] = "1";
      }
      return headers;
    }

    function bindForm() {
      var form = modalEl.querySelector(formSelector);
      if (!form) {
        return;
      }
      initDynamicForm(form, opts.initFormHook);
      trackFormDirty(modalEl, form);
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        setSubmitBusy(submitButton, true);
        var postUrl = opts.postToFormAction ? form.action : url;
        fetch(postUrl, {
          method: "POST",
          body: new FormData(form),
          headers: requestHeaders(),
          credentials: "same-origin"
        })
          .then(function (response) {
            return response.json().then(function (data) {
              return { ok: response.ok, data: data };
            });
          })
          .then(function (result) {
            if (result.ok && result.data.ok) {
              modalEl._cmSaved = true;
              modal.hide();
              if (onSaved) {
                onSaved(result.data);
              }
              return;
            }
            // result.data.html is server-rendered with Django autoescape.
            setHtml(bodyEl, result.data.html || "");
            bindForm();
            // The re-rendered form still carries the user's pending input.
            modalEl._cmDirty = true;
          })
          .catch(function (error) {
            if (window.console && window.console.error) {
              window.console.error("map create failed", error);
            }
            setHtml(bodyEl, '<div class="alert alert-danger">' + saveErrorText + '</div>');
          })
          .finally(function () {
            setSubmitBusy(submitButton, false);
          });
      });
    }

    fetch(url, {
      headers: requestHeaders(),
      credentials: "same-origin"
    })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        setHtml(bodyEl, data.html || "");
        bindForm();
        if (window.cmSheetModal && window.cmSheetModal.focusFirstInput) {
          window.cmSheetModal.focusFirstInput(modalEl);
        }
      })
      .catch(function () {
        setHtml(bodyEl, '<div class="alert alert-danger">' + loadErrorText + '</div>');
      });
  }

  /**
   * AJAX update modal: fetches the form, submits via AJAX, then triggers
   * onSaved so the caller can refresh markers.
   *
   * opts: modalEl, detailModalEl, updateUrl, label, onSaved,
   *       bodySelector, submitSelector, titleSelector, formSelector,
   *       initFormHook, saveErrorText.
   */
  function openUpdateModal(opts) {
    opts = opts || {};
    var modalEl = opts.modalEl;
    var updateUrl = opts.updateUrl;
    if (!modalEl || !window.bootstrap || !updateUrl) return;
    var bodySelector = opts.bodySelector || "[data-update-modal-body]";
    var submitSelector = opts.submitSelector || "[data-update-submit]";
    var titleSelector = opts.titleSelector || "[data-update-modal-title]";
    var formSelector = opts.formSelector || "[data-map-update-form]";
    var saveErrorText = opts.saveErrorText || "No se pudo guardar los cambios.";
    var onSaved = opts.onSaved;
    var bodyEl = modalEl.querySelector(bodySelector);
    var submitButton = modalEl.querySelector(submitSelector);
    var titleEl = modalEl.querySelector(titleSelector);
    if (titleEl && opts.label) titleEl.textContent = "Editar " + opts.label;
    setHtml(bodyEl, loadingHtml("Cargando formulario..."));
    attachDirtyGuard(modalEl);
    resetDirtyState(modalEl);

    if (opts.detailModalEl) {
      var detail = window.bootstrap.Modal.getInstance(opts.detailModalEl);
      if (detail) detail.hide();
    }
    var modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();

    function bindForm() {
      var form = modalEl.querySelector(formSelector);
      if (!form) return;
      initDynamicForm(form, opts.initFormHook);
      trackFormDirty(modalEl, form);
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        setSubmitBusy(submitButton, true);
        fetch(updateUrl, {
          method: "POST",
          body: new FormData(form),
          headers: {
            "X-Requested-With": "XMLHttpRequest",
            "X-Map-Update": "1"
          },
          credentials: "same-origin"
        })
          .then(function (response) {
            return response.json().then(function (data) {
              return { ok: response.ok, data: data };
            });
          })
          .then(function (result) {
            if (result.ok && result.data.ok) {
              modalEl._cmSaved = true;
              modal.hide();
              if (onSaved) onSaved(result.data);
              return;
            }
            setHtml(bodyEl, result.data.html || "");
            bindForm();
            modalEl._cmDirty = true;
          })
          .catch(function (error) {
            if (window.console && window.console.error) {
              window.console.error("map update failed", error);
            }
            setHtml(bodyEl, '<div class="alert alert-danger">' + saveErrorText + '</div>');
          })
          .finally(function () {
            setSubmitBusy(submitButton, false);
          });
      });
    }

    fetch(updateUrl, {
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        "X-Map-Update": "1"
      },
      credentials: "same-origin"
    })
      .then(function (response) {
        return response.json().then(function (data) { return { ok: response.ok, data: data }; });
      })
      .then(function (result) {
        if (!result.ok && result.data && result.data.error) {
          setHtml(bodyEl, '<div class="alert alert-warning">' + result.data.error + '</div>');
          return;
        }
        setHtml(bodyEl, result.data.html || "");
        bindForm();
        if (window.cmSheetModal && window.cmSheetModal.focusFirstInput) {
          window.cmSheetModal.focusFirstInput(modalEl);
        }
      })
      .catch(function () {
        setHtml(bodyEl, '<div class="alert alert-danger">No se pudo cargar el formulario.</div>');
      });
  }

  /**
   * Delete confirmation modal.
   *
   * opts: modalEl, detailModalEl, deleteUrl, label, onDeleted.
   */
  function openDeleteModal(opts) {
    opts = opts || {};
    var modalEl = opts.modalEl;
    var deleteUrl = opts.deleteUrl;
    if (!modalEl || !window.bootstrap || !deleteUrl) return;
    var labelEl = modalEl.querySelector("[data-delete-label]");
    var confirmBtn = modalEl.querySelector("[data-delete-confirm]");
    if (labelEl) labelEl.textContent = opts.label || "";
    if (opts.detailModalEl) {
      var detail = window.bootstrap.Modal.getInstance(opts.detailModalEl);
      if (detail) detail.hide();
    }
    var modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();

    if (!confirmBtn) return;
    var freshBtn = confirmBtn.cloneNode(true);
    confirmBtn.parentNode.replaceChild(freshBtn, confirmBtn);
    freshBtn.addEventListener("click", function () {
      setSubmitBusy(freshBtn, true);
      var csrf = (document.querySelector("[name=csrfmiddlewaretoken]") || {}).value
        || (document.cookie.match(/csrftoken=([^;]+)/) || [])[1]
        || "";
      fetch(deleteUrl, {
        method: "POST",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          "X-Map-Delete": "1",
          "X-CSRFToken": csrf
        },
        credentials: "same-origin"
      })
        .then(function (response) {
          return response.json().then(function (data) {
            return { ok: response.ok, data: data };
          });
        })
        .then(function (result) {
          if (result.ok && result.data.ok) {
            modal.hide();
            if (opts.onDeleted) opts.onDeleted(result.data);
            return;
          }
          if (window.console && window.console.error) {
            window.console.error("map delete rejected", result);
          }
        })
        .catch(function (error) {
          if (window.console && window.console.error) {
            window.console.error("map delete failed", error);
          }
        })
        .finally(function () {
          setSubmitBusy(freshBtn, false);
        });
    });
  }

  /**
   * Detail modal fed from a full page fetch (extracts
   * #kt_app_content_container from the response).
   *
   * opts: modalEl, item ({label, url, update_url, delete_url}),
   *       fallbackTitle, markerKind, errorText.
   */
  function openDetailModal(opts) {
    opts = opts || {};
    var modalEl = opts.modalEl;
    var item = opts.item || {};
    if (!modalEl || !window.bootstrap || !item.url) {
      if (item.url) {
        window.location.href = item.url;
      }
      return;
    }

    var titleEl = modalEl.querySelector("[data-modal-title]");
    var bodyEl = modalEl.querySelector("[data-modal-body]");
    var detailLink = modalEl.querySelector("[data-detail-link]");
    if (titleEl) {
      titleEl.textContent = item.label || opts.fallbackTitle || "Detalle";
    }
    modalEl.dataset.currentLabel = item.label || opts.fallbackTitle || "";
    modalEl.dataset.currentDetailUrl = item.url || "";
    if (opts.markerKind !== undefined) {
      modalEl.dataset.markerKind = opts.markerKind;
    }
    if (detailLink) {
      detailLink.href = item.url;
      detailLink.style.display = "";
    }
    applyActionLink(modalEl, "[data-edit-link]", item.update_url);
    applyActionLink(modalEl, "[data-delete-link]", item.delete_url);
    setHtml(bodyEl, loadingHtml("Cargando..."));

    var modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();

    fetch(item.url, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin"
    })
      .then(function (r) { return r.text(); })
      .then(function (html) {
        var detailHtml = detailHtmlFromPage(html);
        if (!detailHtml) {
          throw new Error("Empty detail content");
        }
        setHtml(bodyEl, detailHtml);
        initDynamicContent(bodyEl);
      })
      .catch(function () {
        setHtml(
          bodyEl,
          '<div class="alert alert-danger">' +
            (opts.errorText || "No se pudo cargar la información del registro.") +
          '</div>'
        );
      });
  }

  /**
   * Detail modal fed from a JSON {html, url} endpoint (refusal popups).
   * When the payload includes a non-empty `url`, [data-detail-link] points
   * to it and becomes visible; otherwise it stays hidden.
   *
   * opts: modalEl, item, fallbackTitle, markerKind, errorText.
   */
  function openJsonModal(opts) {
    opts = opts || {};
    var modalEl = opts.modalEl;
    var item = opts.item || {};
    if (!modalEl || !window.bootstrap) {
      return;
    }
    var titleEl = modalEl.querySelector("[data-modal-title]");
    var bodyEl = modalEl.querySelector("[data-modal-body]");
    var detailLink = modalEl.querySelector("[data-detail-link]");
    if (titleEl) {
      titleEl.textContent = item.label || opts.fallbackTitle || "Detalle";
    }
    modalEl.dataset.currentLabel = item.label || "";
    modalEl.dataset.currentDetailUrl = item.url || "";
    if (opts.markerKind !== undefined) {
      modalEl.dataset.markerKind = opts.markerKind;
    }
    if (detailLink) {
      // Hidden until the JSON payload confirms a detail page exists.
      detailLink.style.display = "none";
    }
    applyActionLink(modalEl, "[data-edit-link]", item.update_url);
    applyActionLink(modalEl, "[data-delete-link]", item.delete_url);
    setHtml(bodyEl, loadingHtml("Cargando..."));

    var modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();

    fetch(item.url, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin"
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        setHtml(bodyEl, data.html || "");
        initDynamicContent(bodyEl);
        if (detailLink && data.url) {
          detailLink.href = data.url;
          detailLink.style.display = "";
        }
      })
      .catch(function () {
        setHtml(
          bodyEl,
          '<div class="alert alert-danger">' +
            (opts.errorText || "No se pudo cargar la información.") +
          '</div>'
        );
      });
  }

  /* ------------------------------------------------------------------
   * Foldable legend (toggle + close, state persisted in localStorage)
   * ------------------------------------------------------------------ */

  function bindLegend(opts) {
    opts = opts || {};
    var legendEl = opts.legendEl;
    var toggleEl = opts.toggleEl;
    var storageKey = opts.storageKey || "cm:map:legendOpen";
    if (!legendEl || !toggleEl) {
      return;
    }

    var initialOpen = false;
    try {
      initialOpen = window.localStorage.getItem(storageKey) === "1";
    } catch (e) { /* localStorage unavailable */ }

    function applyLegendState(open) {
      legendEl.classList.toggle("is-open", open);
      toggleEl.classList.toggle("is-active", open);
      toggleEl.setAttribute("aria-expanded", open ? "true" : "false");
      legendEl.setAttribute("aria-hidden", open ? "false" : "true");
    }
    applyLegendState(initialOpen);

    toggleEl.addEventListener("click", function () {
      var next = !legendEl.classList.contains("is-open");
      applyLegendState(next);
      try { window.localStorage.setItem(storageKey, next ? "1" : "0"); } catch (e) {}
    });

    var legendCloseEl = legendEl.querySelector("[data-legend-close]");
    if (legendCloseEl) {
      legendCloseEl.addEventListener("click", function () {
        applyLegendState(false);
        try { window.localStorage.setItem(storageKey, "0"); } catch (e) {}
      });
    }
  }

  /* ------------------------------------------------------------------
   * createMapPage — the whole bootMap plumbing shared by both apps
   * ------------------------------------------------------------------ */

  /**
   * config:
   *   mapId, shellSelector, panelId, counterId, filterCounterId,
   *   filterTriggerSelector, resetId, myLocationId, filtersId, truncationId,
   *   countLabels {singular, plural}, createGateMeters, loadErrorLog,
   *   setup(ctx)            — create data layers / wire app modals,
   *   clickEnabled(ctx)     — whether map clicks should open the create flow,
   *   onMapClick(latlng, ctx),
   *   renderData(data, ctx) — render markers, returns {count, bounds}.
   *
   * ctx: {map, el, shell, load, panelApi, addClusterLayer, locationLayer,
   *       showStatus, getMapState, getActiveBasemap}.
   */
  function createMapPage(config) {
    var el = document.getElementById(config.mapId);
    if (!el || !window.L) {
      return null;
    }

    var shell = config.shellSelector ? el.closest(config.shellSelector) : null;
    var panel = config.panelId ? document.getElementById(config.panelId) : null;
    var panelTriggers = document.querySelectorAll("[data-panel-toggle]");
    var counterEl = config.counterId ? document.getElementById(config.counterId) : null;
    var filterCounterEl = config.filterCounterId
      ? document.getElementById(config.filterCounterId)
      : null;
    var filterTriggerEls = config.filterTriggerSelector
      ? document.querySelectorAll(config.filterTriggerSelector)
      : null;
    var resetButton = config.resetId ? document.getElementById(config.resetId) : null;
    var myLocationButton = config.myLocationId
      ? document.getElementById(config.myLocationId)
      : null;
    var locationStatusEl = document.querySelector("[data-location-status]");
    var truncationEl = config.truncationId
      ? document.getElementById(config.truncationId)
      : null;
    var emptyEl = (shell || document).querySelector("[data-map-empty]");
    var filters = config.filtersId ? document.getElementById(config.filtersId) : null;
    var countLabels = config.countLabels || { singular: "registro", plural: "registros" };
    var createGateMeters = config.createGateMeters || 50;
    var locationTargetMeters = config.locationTargetMeters || 50;
    var scaleReferenceWidthPx = 120;

    var tenantCenter = window.TENANT_MAP_CENTER || {};
    var defaultLat = parseFloat(el.dataset.defaultLat) || tenantCenter.lat || -2.3046;
    var defaultLng = parseFloat(el.dataset.defaultLng) || tenantCenter.lng || -78.1175;
    var defaultZoom = parseInt(el.dataset.defaultZoom || tenantCenter.zoom || "13", 10);
    var map = window.L.map(el, {
      zoomControl: false,
      attributionControl: false
    }).setView([defaultLat, defaultLng], defaultZoom);

    var basemapRefs = null;
    if (window.LeafletBasemaps && window.LeafletBasemaps.build) {
      var built = window.LeafletBasemaps.build(map, null, { skipNativeControl: true });
      basemapRefs = built && built.refs ? built.refs : null;
    } else {
      window.L.tileLayer(
        "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
        {
          maxZoom: 20,
          subdomains: "abcd",
          attribution:
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        }
      ).addTo(map);
    }

    // When clusters expand/collapse, Leaflet rebuilds marker DOM from the
    // divIcon HTML string, which still contains raw <i data-lucide> nodes.
    // Re-run Lucide so they materialise back into SVGs.
    function reRenderPinIcons() {
      if (window.cmRenderIcons) window.cmRenderIcons();
    }

    var dataLayers = [];

    function addClusterLayer(options) {
      options = options || {};
      var layer;
      if (window.L.markerClusterGroup) {
        var clusterOptions = {
          showCoverageOnHover: false,
          spiderfyOnMaxZoom: true,
          disableClusteringAtZoom: 15,
          maxClusterRadius: 22
        };
        if (options.iconCreateFunction) {
          clusterOptions.iconCreateFunction = options.iconCreateFunction;
        }
        layer = window.L.markerClusterGroup(clusterOptions);
      } else {
        layer = window.L.layerGroup();
      }
      layer.addTo(map);
      if (layer && typeof layer.on === "function") {
        layer.on("animationend", reRenderPinIcons);
        layer.on("spiderfied", reRenderPinIcons);
        layer.on("unspiderfied", reRenderPinIcons);
      }
      dataLayers.push(layer);
      return layer;
    }

    var locationLayer = window.L.layerGroup().addTo(map);

    window.L.control.attribution({ position: "bottomright", prefix: false }).addTo(map);
    window.L.control.scale({
      position: "bottomleft",
      metric: true,
      imperial: false,
      maxWidth: 120
    }).addTo(map);

    var zoomInBtn = document.querySelector("[data-zoom-in]");
    var zoomOutBtn = document.querySelector("[data-zoom-out]");
    if (zoomInBtn) {
      zoomInBtn.addEventListener("click", function () {
        zoomToRespectingBasemap(map.getZoom() + 1);
      });
    }
    if (zoomOutBtn) {
      zoomOutBtn.addEventListener("click", function () {
        zoomToRespectingBasemap(map.getZoom() - 1);
      });
    }

    var layerToggleBtn = document.querySelector("[data-layer-toggle]");
    var layerLabelEl = document.querySelector("[data-layer-label]");
    var layerThumbEl = document.querySelector("[data-layer-thumb]");
    var activeBasemap = "carto";
    var preferredBasemap = "carto";
    var satelliteMaxZoom = basemapRefs ? getLayerMaxZoom(basemapRefs.satellite, 19) : 19;
    var cartoMaxZoom = basemapRefs ? getLayerMaxZoom(basemapRefs.carto, 20) : 20;
    if (basemapRefs) {
      map.setMaxZoom(Math.max(cartoMaxZoom, satelliteMaxZoom));
    }

    function syncLayerControl() {
      var isSatellite = activeBasemap === "satellite";
      if (layerToggleBtn) {
        layerToggleBtn.setAttribute("aria-pressed", isSatellite ? "true" : "false");
      }
      if (layerLabelEl) {
        layerLabelEl.textContent = isSatellite ? "Mapa" : "Satélite";
      }
      if (layerThumbEl) {
        layerThumbEl.classList.toggle("is-satellite", !isSatellite);
      }
    }

    function setBasemap(next) {
      if (!basemapRefs || activeBasemap === next) {
        syncLayerControl();
        return;
      }
      if (activeBasemap === "satellite" && basemapRefs.satellite) {
        map.removeLayer(basemapRefs.satellite);
      } else if (activeBasemap === "carto" && basemapRefs.carto) {
        map.removeLayer(basemapRefs.carto);
      }
      if (next === "satellite") {
        basemapRefs.satellite.addTo(map);
      } else {
        basemapRefs.carto.addTo(map);
      }
      activeBasemap = next;
      syncLayerControl();
    }

    function applyPreferredBasemapForZoom() {
      if (!basemapRefs) {
        return;
      }
      if (preferredBasemap === "satellite" && map.getZoom() <= satelliteMaxZoom) {
        setBasemap("satellite");
      } else if (preferredBasemap === "satellite" && map.getZoom() > satelliteMaxZoom) {
        setBasemap("carto");
      }
    }

    function zoomToRespectingBasemap(targetZoom) {
      if (
        basemapRefs &&
        preferredBasemap === "satellite" &&
        targetZoom > satelliteMaxZoom
      ) {
        setBasemap("carto");
      }
      map.setZoom(targetZoom);
    }

    if (layerToggleBtn && basemapRefs && basemapRefs.carto && basemapRefs.satellite) {
      syncLayerControl();
      layerToggleBtn.addEventListener("click", function () {
        if (preferredBasemap === "satellite") {
          preferredBasemap = "carto";
          setBasemap("carto");
        } else {
          preferredBasemap = "satellite";
          if (map.getZoom() <= satelliteMaxZoom) {
            setBasemap("satellite");
          } else {
            setBasemap("carto");
          }
        }
      });
    }
    map.on("zoomend", applyPreferredBasemapForZoom);

    var mapState = window.MapState && window.MapState.attach
      ? window.MapState.attach(map, {
          defaultBasemap: "carto",
          getBasemap: function () { return preferredBasemap; },
          setBasemap: function (name) {
            if (name === "satellite" || name === "carto") {
              preferredBasemap = name;
              if (basemapRefs && basemapRefs.satellite && basemapRefs.carto) {
                if (name === "satellite" && map.getZoom() <= satelliteMaxZoom) {
                  setBasemap("satellite");
                } else {
                  setBasemap("carto");
                }
              }
            }
          }
        })
      : null;
    var mapStateRestored = mapState ? mapState.restore() : false;
    var userOwnsView = mapStateRestored;
    // Set before a filter-triggered load so the result recenters even after
    // the user has already panned/zoomed the map.
    var forceFitNextLoad = false;
    map.on("movestart zoomstart", function () { userOwnsView = true; });

    var panelApi = setupPanel(shell, panel, panelTriggers, map);

    function buildUrl() {
      var base = el.dataset.url || "";
      var params = new URLSearchParams();
      if (filters) {
        Array.prototype.forEach.call(filters.elements, function (input) {
          if (input.name && input.value) {
            params.append(input.name, input.value);
          }
        });
      }
      var qs = params.toString();
      return qs ? base + (base.indexOf("?") === -1 ? "?" : "&") + qs : base;
    }

    function showTruncation(data) {
      if (!truncationEl) return;
      if (data && data.truncated) {
        var shown = truncationEl.querySelector("[data-truncated-shown]");
        var total = truncationEl.querySelector("[data-truncated-total]");
        if (shown) shown.textContent = String(data.returned || 0);
        if (total) total.textContent = String(data.total || 0);
        truncationEl.classList.remove("d-none");
      } else {
        truncationEl.classList.add("d-none");
      }
    }

    // "Aplicar filtros" shortcut inside the truncation banner.
    if (truncationEl) {
      var openFiltersBtn = truncationEl.querySelector("[data-open-filters]");
      if (openFiltersBtn) {
        openFiltersBtn.addEventListener("click", function () {
          panelApi.open();
        });
      }
    }

    function filtersHaveValue() {
      if (!filters) {
        return false;
      }
      var any = false;
      Array.prototype.forEach.call(filters.elements, function (input) {
        if (input.name && input.value) {
          any = true;
        }
      });
      return any;
    }

    function showEmptyState(isEmpty) {
      if (!emptyEl) {
        return;
      }
      if (!isEmpty) {
        emptyEl.setAttribute("hidden", "");
        return;
      }
      var filtered = filtersHaveValue();
      var filteredText = emptyEl.querySelector("[data-map-empty-text-filtered]");
      var blankText = emptyEl.querySelector("[data-map-empty-text-blank]");
      if (filteredText) {
        if (filtered) {
          filteredText.removeAttribute("hidden");
        } else {
          filteredText.setAttribute("hidden", "");
        }
      }
      if (blankText) {
        if (filtered) {
          blankText.setAttribute("hidden", "");
        } else {
          blankText.removeAttribute("hidden");
        }
      }
      emptyEl.removeAttribute("hidden");
    }

    function resetFilters() {
      forceFitNextLoad = true;
      if (!filters) {
        load();
        return;
      }
      filters.reset();
      // select2 mirrors the underlying <select>; tell it to repaint.
      if (window.jQuery && window.jQuery.fn.select2) {
        Array.prototype.forEach.call(filters.elements, function (input) {
          if (input.name) {
            window.jQuery(input).trigger("change.select2");
          }
        });
      }
      load();
    }

    function showStatus(message, tone, autoHideMs) {
      showLocationStatus(locationStatusEl, message, tone, autoHideMs);
    }

    var ctx = {
      map: map,
      el: el,
      shell: shell,
      panelApi: panelApi,
      addClusterLayer: addClusterLayer,
      locationLayer: locationLayer,
      showStatus: showStatus,
      load: load,
      getActiveBasemap: function () { return activeBasemap; },
      getMapState: function () {
        return { zoom: map.getZoom(), layer: activeBasemap };
      }
    };

    var activeLoadController = null;

    function load() {
      if (activeLoadController) {
        activeLoadController.abort();
      }
      activeLoadController = window.AbortController
        ? new window.AbortController()
        : null;
      dataLayers.forEach(function (layer) {
        layer.clearLayers();
      });
      updateCount(counterEl, 0, countLabels);
      updateFilterCount(filterCounterEl, filterTriggerEls, filters);
      showEmptyState(false);
      var fetchOptions = {
        headers: { "X-Requested-With": "XMLHttpRequest" }
      };
      if (activeLoadController) {
        fetchOptions.signal = activeLoadController.signal;
      }
      fetch(buildUrl(), fetchOptions)
        .then(function (r) { return r.json(); })
        .then(function (data) {
          var result = config.renderData(data, ctx) || {};
          var count = result.count || 0;
          var bounds = result.bounds || [];
          updateCount(counterEl, count, countLabels);
          showTruncation(data);
          // A page can render more marker kinds than it counts (e.g. the
          // visit counter ignores competitor pins), so emptiness follows the
          // rendered bounds, not the headline count.
          showEmptyState(result.bounds ? bounds.length === 0 : count === 0);
          if (bounds.length && (!userOwnsView || forceFitNextLoad)) {
            map.fitBounds(bounds, { padding: [30, 30], maxZoom: 16 });
          }
          userOwnsView = true;
          forceFitNextLoad = false;
          // Pin HTML contains <i data-lucide="..."> placeholders — render
          // them now that Leaflet has placed the markers in the DOM.
          if (window.cmRenderIcons) window.cmRenderIcons();
        })
        .catch(function (error) {
          if (error && error.name === "AbortError") {
            return;
          }
          updateCount(counterEl, 0, countLabels);
          if (window.console && window.console.error) {
            window.console.error(config.loadErrorLog || "Map data load failed");
          }
        });
    }

    // Reload + recenter when a filter changes. select2 (used by the campaign/
    // state/kind selects) fires its ``change`` through jQuery, which native
    // ``addEventListener`` does NOT catch — so we bind both ways.
    function onFilterChange() {
      forceFitNextLoad = true;
      load();
    }
    if (filters) {
      Array.prototype.forEach.call(filters.elements, function (input) {
        input.addEventListener("change", onFilterChange);
        if (window.jQuery) {
          window.jQuery(input).on("change", onFilterChange);
        }
      });
    }
    if (resetButton && filters) {
      resetButton.addEventListener("click", resetFilters);
    }
    if (emptyEl) {
      var emptyClearBtn = emptyEl.querySelector("[data-map-empty-clear]");
      if (emptyClearBtn) {
        emptyClearBtn.addEventListener("click", resetFilters);
      }
    }

    if (myLocationButton) {
      var blockedLabel = "Ubicación desactivada — tócalo para reintentar";

      var markLocationBlocked = function () {
        myLocationButton.classList.add("is-blocked");
        myLocationButton.setAttribute("title", blockedLabel);
        myLocationButton.setAttribute("aria-label", blockedLabel);
      };

      var clearLocationBlocked = function () {
        myLocationButton.classList.remove("is-blocked");
      };

      var renderUserLocation = function (position) {
        var lat = position.coords.latitude;
        var lng = position.coords.longitude;
        var accuracy = position.coords.accuracy || 0;

        locationLayer.clearLayers();
        window.L.circle([lat, lng], {
          radius: accuracy,
          stroke: false,
          fillColor: "#3e97ff",
          fillOpacity: 0.12,
          bubblingMouseEvents: false
        }).addTo(locationLayer);
        window.L.circleMarker([lat, lng], {
          radius: 9,
          color: "#ffffff",
          fillColor: "#3e97ff",
          fillOpacity: 1,
          weight: 3,
          bubblingMouseEvents: false
        }).bindTooltip("Mi ubicación", {
          direction: "top",
          offset: [0, -10],
          permanent: false
        }).addTo(locationLayer);

        var targetLatLng = window.L.latLng(lat, lng);
        var locationZoom = findZoomForTargetMeters(
          map,
          targetLatLng,
          locationTargetMeters,
          scaleReferenceWidthPx
        );
        map.setView(targetLatLng, Math.max(map.getZoom(), locationZoom));
        clearLocationBlocked();
        setLocationButton(myLocationButton, "Mi ubicación", false);
        showStatus("Ubicación encontrada.", "success", 3000);
      };

      var renderLocationError = function (error) {
        var message = geolocationErrorMessage(error);
        setLocationButton(myLocationButton, message, false);
        if (error && error.code === error.PERMISSION_DENIED) {
          markLocationBlocked();
        }
        showStatus(message, "danger", 7000);
      };

      myLocationButton.addEventListener("click", function () {
        setLocationButton(myLocationButton, "Ubicando...", true);
        showStatus("Buscando tu ubicación...", "info");

        // Through the gate: pre-prompt when "prompt", instructions panel
        // when "denied", HTTPS notice when applicable. Already-granted goes
        // straight to the fetch without opening a modal.
        if (window.GeolocationGate) {
          window.GeolocationGate.require({
            mode: "soft",
            reason: "Para mostrar tu posición actual en el mapa.",
            onGranted: renderUserLocation,
            onDenied: function (error) {
              renderLocationError(error);
              markLocationBlocked();
            },
            onSkipped: function () {
              setLocationButton(myLocationButton, "Mi ubicación", false);
              markLocationBlocked();
              showStatus("Sin ubicación.", "info", 3000);
            }
          });
          return;
        }

        // Fallback when the gate is unavailable.
        if (!window.isSecureContext || !navigator.geolocation) {
          setLocationButton(myLocationButton, "Ubicación no disponible", false);
          showStatus(
            !window.isSecureContext
              ? "Para usar ubicación abre el sitio con HTTPS."
              : "Este navegador no soporta ubicación.",
            "danger",
            6000
          );
          return;
        }
        navigator.geolocation.getCurrentPosition(
          renderUserLocation,
          renderLocationError,
          { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000 }
        );
      });
    }

    function getCreateGateDistanceMeters() {
      var size = map.getSize();
      if (!size || size.x <= 0 || size.y <= 0) {
        return null;
      }
      var referenceWidth = Math.min(scaleReferenceWidthPx, size.x);
      var centerY = size.y / 2;
      var start = map.containerPointToLatLng([0, centerY]);
      var end = map.containerPointToLatLng([referenceWidth, centerY]);
      return map.distance(start, end);
    }

    function canOpenCreateFromMap() {
      var distanceMeters = getCreateGateDistanceMeters();
      return distanceMeters !== null && distanceMeters <= createGateMeters;
    }

    function zoomToCreateGate(latlng) {
      var targetZoom = findZoomForTargetMeters(
        map,
        latlng,
        createGateMeters,
        scaleReferenceWidthPx
      );
      // Center on the clicked point and zoom in so the next click clears the
      // gate. Never zoom out if the user is already closer than required.
      map.setView(latlng, Math.max(map.getZoom(), targetZoom));
      showStatus(
        "Acercando a " + createGateMeters + " m. Vuelve a tocar el punto para agregar.",
        "info",
        3500
      );
    }

    map.on("click", function (event) {
      if (config.clickEnabled && !config.clickEnabled(ctx)) {
        return;
      }
      if (
        shell &&
        shell.getAttribute("data-panel-state") === "expanded" &&
        window.matchMedia("(max-width: 767.98px)").matches
      ) {
        panelApi.close();
        return;
      }
      if (!canOpenCreateFromMap()) {
        zoomToCreateGate(event.latlng);
        return;
      }
      if (config.onMapClick) {
        config.onMapClick(event.latlng, ctx);
      }
    });

    window.addEventListener("resize", function () { map.invalidateSize(); });

    if (config.setup) {
      config.setup(ctx);
    }

    load();
    window.setTimeout(function () { map.invalidateSize(); }, 150);

    return ctx;
  }

  /* ------------------------------------------------------------------
   * Boot helper: DOMContentLoaded + Leaflet CDN retry loader
   * ------------------------------------------------------------------ */

  function boot(fn) {
    document.addEventListener("DOMContentLoaded", function () {
      if (window.L || !window.cmEnsureLeaflet) {
        fn();
        return;
      }
      // Leaflet (CDN) did not load: retry via the loader before giving up.
      window.cmEnsureLeaflet(function (leaflet) {
        if (leaflet) fn();
      });
    });
  }

  window.CmMapKit = {
    safeIconName: safeIconName,
    safeColor: safeColor,
    buildCreateUrl: buildCreateUrl,
    setHtml: setHtml,
    updateCount: updateCount,
    updateFilterCount: updateFilterCount,
    setLocationButton: setLocationButton,
    showLocationStatus: showLocationStatus,
    roundMetersForUi: roundMetersForUi,
    distanceAcrossWidthAtZoom: distanceAcrossWidthAtZoom,
    findZoomForTargetMeters: findZoomForTargetMeters,
    geolocationErrorMessage: geolocationErrorMessage,
    getLayerMaxZoom: getLayerMaxZoom,
    setupPanel: setupPanel,
    detailHtmlFromPage: detailHtmlFromPage,
    initDynamicContent: initDynamicContent,
    applyActionLink: applyActionLink,
    loadingHtml: loadingHtml,
    setSubmitBusy: setSubmitBusy,
    openCreateModal: openCreateModal,
    openUpdateModal: openUpdateModal,
    openDeleteModal: openDeleteModal,
    openDetailModal: openDetailModal,
    openJsonModal: openJsonModal,
    bindLegend: bindLegend,
    createMapPage: createMapPage,
    boot: boot
  };
})(window, document);
