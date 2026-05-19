(function (window, document) {
  "use strict";

  var ICON_ALIASES = {
    "billboard": "flag",
    "sticker":   "tag",
    "like":      "thumbs-up",
    "dislike":   "thumbs-down",
    "question-2":"help-circle",
    "home-2":    "home",
    "geolocation":"map-pin",
    "cross":     "x"
  };

  // Visual config per support state. Drives icon, color, semantic class.
  // The fallback ("") is used when a survey has not been classified yet.
  var SUPPORT_STATES = {
    "APOYA":      { icon: "thumbs-up",   color: "#50cd89", cls: "is-apoya",      label: "Apoya" },
    "INDECISO":   { icon: "help-circle", color: "#ffc700", cls: "is-indeciso",   label: "Indeciso" },
    "NO_APOYA":   { icon: "thumbs-down", color: "#f1416c", cls: "is-noapoya",    label: "No apoya" },
    "NO_ATENDIO": { icon: "home",        color: "#7e8299", cls: "is-noatendio",  label: "No atendió" },
    "":           { icon: "map-pin",     color: "#3e97ff", cls: "is-pending",    label: "Sin clasificar" }
  };

  var ADVERTISING_BADGES = {
    "ACEPTA":  { icon: "check", cls: "fs-pin__badge--accept", label: "Acepta publicidad" },
    "RECHAZA": { icon: "x",     cls: "fs-pin__badge--reject", label: "Rechaza publicidad" }
  };

  function safeIconName(icon) {
    var raw = (icon || "").toLowerCase();
    if (ICON_ALIASES[raw]) {
      return ICON_ALIASES[raw];
    }
    return /^[a-z0-9-]+$/i.test(icon || "") ? icon : "circle";
  }

  function safeColor(color, fallback) {
    return /^#[0-9a-f]{3,8}$/i.test(color || "") ? color : (fallback || "#3388ff");
  }

  function visitPin(item) {
    var state = SUPPORT_STATES[item.support_code || ""] || SUPPORT_STATES[""];
    var color = safeColor(item.color, state.color);
    var iconName = safeIconName(state.icon);

    var badgeHtml = "";
    var badge = ADVERTISING_BADGES[item.advertising_code || ""];
    if (badge) {
      badgeHtml =
        '<span class="fs-pin__badge ' + badge.cls + '" title="' + badge.label + '">' +
          '<i data-lucide="' + badge.icon + '"></i>' +
        '</span>';
    }

    return window.L.divIcon({
      className: "fs-pin fs-pin--visit " + state.cls,
      html:
        '<span class="fs-pin__shape" style="background:' + color + '">' +
          '<i data-lucide="' + iconName + '"></i>' +
        '</span>' +
        '<span class="fs-pin__tail" style="border-top-color:' + color + '"></span>' +
        badgeHtml,
      iconSize: [40, 50],
      iconAnchor: [20, 48],
      popupAnchor: [0, -46]
    });
  }

  // Competitor pins always use the same icon: kind matters more than the
  // specific advertising type (banner vs. sticker vs. lona) for at-a-glance
  // map reading.
  var COMPETITOR_ICON = "flag";

  function competitorPin(item) {
    var color = safeColor(item.color, "#d9214e");
    return window.L.divIcon({
      className: "fs-pin fs-pin--competitor",
      html:
        '<span class="fs-pin__diamond" style="border-color:' + color + '">' +
          '<span class="fs-pin__diamond-icon" style="color:' + color + '">' +
            '<i data-lucide="' + COMPETITOR_ICON + '"></i>' +
          '</span>' +
        '</span>',
      iconSize: [44, 44],
      iconAnchor: [22, 22],
      popupAnchor: [0, -22]
    });
  }

  function buildCreateUrl(base, latlng, mapState) {
    var params = new URLSearchParams();
    params.set("latitude", latlng.lat.toFixed(6));
    params.set("longitude", latlng.lng.toFixed(6));
    if (mapState && mapState.zoom !== undefined && mapState.zoom !== null) {
      params.set("map_zoom", String(mapState.zoom));
    }
    if (mapState && mapState.layer) {
      params.set("map_layer", mapState.layer);
    }
    return base + (base.indexOf("?") === -1 ? "?" : "&") + params.toString();
  }

  function setHtml(node, html) {
    // Content originates from our own Django template with autoescape on, so
    // user-supplied fields are HTML-escaped before reaching the browser.
    node.innerHTML = html;
  }

  function updateCount(counterEl, count) {
    if (!counterEl) {
      return;
    }
    var numberEl = counterEl.querySelector("[data-pin-count-number]");
    var labelEl = counterEl.querySelector("[data-pin-count-label]");
    var label = count === 1 ? "visita" : "visitas";
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

  // Order matters: drives the visual sequence of donut segments.
  var CLUSTER_SEGMENTS = ["APOYA", "INDECISO", "NO_APOYA", "NO_ATENDIO", ""];

  function buildClusterIcon(cluster) {
    var leaves = cluster.getAllChildMarkers();
    var counts = { "APOYA": 0, "INDECISO": 0, "NO_APOYA": 0, "NO_ATENDIO": 0, "": 0 };
    leaves.forEach(function (marker) {
      var code = marker.options.fsSupportCode;
      if (code === undefined || counts[code] === undefined) {
        counts[""] += 1;
      } else {
        counts[code] += 1;
      }
    });

    var total = leaves.length;
    var size = total < 10 ? 40 : total < 50 ? 48 : 56;

    var stops = [];
    var degSoFar = 0;
    CLUSTER_SEGMENTS.forEach(function (code) {
      var count = counts[code];
      if (!count) {
        return;
      }
      var degSpan = (count / total) * 360;
      var color = SUPPORT_STATES[code].color;
      stops.push(color + " " + degSoFar.toFixed(2) + "deg " + (degSoFar + degSpan).toFixed(2) + "deg");
      degSoFar += degSpan;
    });

    var background = stops.length
      ? "conic-gradient(" + stops.join(", ") + ")"
      : SUPPORT_STATES[""].color;

    return window.L.divIcon({
      html:
        '<span class="fs-cluster" style="background:' + background + '">' +
          '<span class="fs-cluster__inner">' + total + '</span>' +
        '</span>',
      className: "fs-cluster-wrap",
      iconSize: [size, size]
    });
  }

  // Competitor cluster: solid red bubble with a flag, kept visually distinct
  // from the visit donut so the two layers don't get confused at low zoom.
  function buildCompetitorClusterIcon(cluster) {
    var total = cluster.getChildCount();
    var size = total < 10 ? 40 : total < 50 ? 48 : 56;
    return window.L.divIcon({
      html:
        '<span class="fs-cluster fs-cluster--competitor">' +
          '<span class="fs-cluster__inner fs-cluster__inner--competitor">' +
            '<i data-lucide="flag"></i>' +
            '<span class="fs-cluster__count">' + total + '</span>' +
          '</span>' +
        '</span>',
      className: "fs-cluster-wrap",
      iconSize: [size, size]
    });
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

  // Opens the inline update modal: fetches the form via AJAX, submits via
  // AJAX, then triggers an onSaved callback so the caller can refresh markers.
  function openUpdateModal(modalEl, detailModalEl, updateUrl, label, onSaved) {
    if (!modalEl || !window.bootstrap || !updateUrl) return;
    var bodyEl = modalEl.querySelector("[data-update-modal-body]");
    var submitButton = modalEl.querySelector("[data-update-submit]");
    var titleEl = modalEl.querySelector("[data-update-modal-title]");
    if (titleEl && label) titleEl.textContent = "Editar " + label;
    setHtml(bodyEl, loadingHtml("Cargando formulario..."));

    if (detailModalEl) {
      var detail = window.bootstrap.Modal.getInstance(detailModalEl);
      if (detail) detail.hide();
    }
    var modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();

    function bindForm() {
      var form = modalEl.querySelector("[data-map-update-form]");
      if (!form) return;
      initDynamicForm(form);
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        if (submitButton) submitButton.disabled = true;
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
              modal.hide();
              if (onSaved) onSaved(result.data);
              return;
            }
            setHtml(bodyEl, result.data.html || "");
            bindForm();
          })
          .catch(function (error) {
            if (window.console && window.console.error) {
              window.console.error("field-surveys map update failed", error);
            }
            setHtml(bodyEl, '<div class="alert alert-danger">No se pudo guardar los cambios.</div>');
          })
          .finally(function () {
            if (submitButton) submitButton.disabled = false;
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

  function openDeleteModal(modalEl, detailModalEl, deleteUrl, label, onDeleted) {
    if (!modalEl || !window.bootstrap || !deleteUrl) return;
    var labelEl = modalEl.querySelector("[data-delete-label]");
    var confirmBtn = modalEl.querySelector("[data-delete-confirm]");
    if (labelEl) labelEl.textContent = label || "";
    if (detailModalEl) {
      var detail = window.bootstrap.Modal.getInstance(detailModalEl);
      if (detail) detail.hide();
    }
    var modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();

    if (!confirmBtn) return;
    var freshBtn = confirmBtn.cloneNode(true);
    confirmBtn.parentNode.replaceChild(freshBtn, confirmBtn);
    freshBtn.addEventListener("click", function () {
      freshBtn.disabled = true;
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
            if (onDeleted) onDeleted(result.data);
            return;
          }
          if (window.console && window.console.error) {
            window.console.error("field-surveys map delete rejected", result);
          }
        })
        .catch(function (error) {
          if (window.console && window.console.error) {
            window.console.error("field-surveys map delete failed", error);
          }
        })
        .finally(function () {
          freshBtn.disabled = false;
        });
    });
  }

  function openDetailModal(modalEl, item, fallbackTitle) {
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
      titleEl.textContent = item.label || fallbackTitle || "Detalle";
    }
    modalEl.dataset.currentLabel = item.label || fallbackTitle || "";
    modalEl.dataset.currentDetailUrl = item.url || "";
    if (detailLink) {
      detailLink.href = item.url;
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
          '<div class="alert alert-danger">No se pudo cargar la información del registro.</div>'
        );
      });
  }

  function loadingHtml(text) {
    return (
      '<div class="text-center text-muted py-10">' +
        '<div class="spinner-border" role="status"></div>' +
        '<div class="mt-3">' + text + '</div>' +
      '</div>'
    );
  }

  function initDynamicForm(scope) {
    if (window.initFormWidgets) {
      window.initFormWidgets(scope);
    } else if (window.initLeafletMaps) {
      window.initLeafletMaps(scope);
    }
  }

  function openCreateModal(modalEl, createUrl, latlng, mapState, onSaved, saveErrorText) {
    if (!modalEl || !window.bootstrap || !createUrl) {
      window.location.href = buildCreateUrl(createUrl, latlng, mapState);
      return;
    }

    var bodyEl = modalEl.querySelector("[data-create-modal-body]");
    var submitButton = modalEl.querySelector("[data-create-submit]");
    var url = buildCreateUrl(createUrl, latlng, mapState);
    setHtml(bodyEl, loadingHtml("Cargando formulario..."));

    var modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();

    function bindForm() {
      var form = modalEl.querySelector("[data-map-create-form]");
      if (!form) {
        return;
      }
      initDynamicForm(form);
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        if (submitButton) {
          submitButton.disabled = true;
        }
        fetch(url, {
          method: "POST",
          body: new FormData(form),
          headers: {
            "X-Requested-With": "XMLHttpRequest",
            "X-Map-Create": "1"
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
              if (onSaved) {
                onSaved(result.data);
              }
              return;
            }
            // result.data.html is server-rendered with Django autoescape.
            setHtml(bodyEl, result.data.html || "");
            bindForm();
          })
          .catch(function (error) {
            if (window.console && window.console.error) {
              window.console.error("field-surveys map create failed", error);
            }
            setHtml(
              bodyEl,
              '<div class="alert alert-danger">' +
                (saveErrorText || "No se pudo guardar el levantamiento.") +
              '</div>'
            );
          })
          .finally(function () {
            if (submitButton) {
              submitButton.disabled = false;
            }
          });
      });
    }

    fetch(url, {
      headers: {
        "X-Requested-With": "XMLHttpRequest",
        "X-Map-Create": "1"
      },
      credentials: "same-origin"
    })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        // data.html is server-rendered with Django autoescape.
        setHtml(bodyEl, data.html || "");
        bindForm();
        if (window.cmSheetModal && window.cmSheetModal.focusFirstInput) {
          window.cmSheetModal.focusFirstInput(modalEl);
        }
      })
      .catch(function () {
        setHtml(bodyEl, '<div class="alert alert-danger">No se pudo cargar el formulario.</div>');
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var el = document.getElementById("field-survey-map");
    if (!el || !window.L) {
      return;
    }

    var shell = el.closest(".field-survey-map-shell");
    var panel = document.getElementById("field-survey-map-panel");
    var panelTriggers = document.querySelectorAll("[data-panel-toggle]");
    var detailModalEl = document.getElementById("field-survey-detail-modal");
    var createModalEl = document.getElementById("field-survey-create-modal");
    var updateModalEl = document.getElementById("field-survey-update-modal");
    var deleteModalEl = document.getElementById("field-survey-delete-modal");
    var chooseModalEl = document.getElementById("field-survey-choose-modal");

    // Wire the detail modal's Edit/Delete buttons once on init. The URL and
    // label live on the modal's dataset (set in openDetailModal).
    if (detailModalEl) {
      var editLinkEl = detailModalEl.querySelector("[data-edit-link]");
      var deleteLinkEl = detailModalEl.querySelector("[data-delete-link]");
      if (editLinkEl) {
        editLinkEl.addEventListener("click", function (event) {
          event.preventDefault();
          var url = editLinkEl.dataset.actionUrl;
          if (!url) return;
          openUpdateModal(updateModalEl, detailModalEl, url, detailModalEl.dataset.currentLabel || "", function () {
            load();
          });
        });
      }
      if (deleteLinkEl) {
        deleteLinkEl.addEventListener("click", function (event) {
          event.preventDefault();
          var url = deleteLinkEl.dataset.actionUrl;
          if (!url) return;
          openDeleteModal(deleteModalEl, detailModalEl, url, detailModalEl.dataset.currentLabel || "", function () {
            load();
          });
        });
      }

      // Workflow transitions (workflows.js) used to reload the whole page.
      // While our detail modal is open we re-fetch the body instead so the
      // user stays in place and sees the new state.
      detailModalEl.addEventListener("workflow:transitioned", function (event) {
        event.preventDefault();
        var detailUrl = detailModalEl.dataset.currentDetailUrl;
        var bodyEl = detailModalEl.querySelector("[data-modal-body]");
        if (!detailUrl || !bodyEl) {
          load();
          return;
        }
        setHtml(bodyEl, loadingHtml("Actualizando..."));
        fetch(detailUrl, {
          headers: { "X-Requested-With": "XMLHttpRequest" },
          credentials: "same-origin"
        })
          .then(function (r) { return r.text(); })
          .then(function (html) {
            var detailHtml = detailHtmlFromPage(html);
            if (!detailHtml) throw new Error("Empty detail content");
            setHtml(bodyEl, detailHtml);
            initDynamicContent(bodyEl);
            load();
          })
          .catch(function () {
            setHtml(bodyEl, '<div class="alert alert-danger">No se pudo actualizar el detalle.</div>');
          });
      });
    }
    var counterEl = document.getElementById("field-survey-map-count");
    var filterCounterEl = document.getElementById("field-survey-filter-count");
    var filterTriggerEls = document.querySelectorAll(".field-survey-map-filter-trigger");
    var resetButton = document.getElementById("field-survey-map-reset");
    var myLocationButton = document.getElementById("field-survey-my-location");
    var locationStatusEl = document.querySelector("[data-location-status]");
    var legendEl = document.getElementById("field-survey-map-legend");
    var legendToggleEl = document.getElementById("field-survey-map-legend-toggle");
    var createUrl = el.dataset.createUrl || "";
    var createCompetitorUrl = el.dataset.createCompetitorUrl || "";
    var createGateMeters = 100;
    var locationTargetMeters = 50;
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

    var pinsLayer = window.L.markerClusterGroup
      ? window.L.markerClusterGroup({
          showCoverageOnHover: false,
          spiderfyOnMaxZoom: true,
          disableClusteringAtZoom: 15,
          maxClusterRadius: 22,
          iconCreateFunction: buildClusterIcon
        })
      : window.L.layerGroup();
    pinsLayer.addTo(map);
    var competitorLayer = window.L.markerClusterGroup
      ? window.L.markerClusterGroup({
          showCoverageOnHover: false,
          spiderfyOnMaxZoom: true,
          disableClusteringAtZoom: 15,
          maxClusterRadius: 22,
          iconCreateFunction: buildCompetitorClusterIcon
        })
      : window.L.layerGroup();
    competitorLayer.addTo(map);

    // When clusters expand/collapse, Leaflet rebuilds marker DOM from the
    // divIcon HTML string, which still contains raw <i data-lucide> nodes.
    // Re-run Lucide so they materialise back into SVGs.
    function reRenderPinIcons() {
      if (window.cmRenderIcons) window.cmRenderIcons();
    }
    [pinsLayer, competitorLayer].forEach(function (layer) {
      if (layer && typeof layer.on === "function") {
        layer.on("animationend", reRenderPinIcons);
        layer.on("spiderfied", reRenderPinIcons);
        layer.on("unspiderfied", reRenderPinIcons);
      }
    });
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
    map.on("movestart zoomstart", function () { userOwnsView = true; });

    var filters = document.getElementById("field-survey-map-filters");
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

    var truncationEl = document.getElementById("field-survey-map-truncated");

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

    function load() {
      pinsLayer.clearLayers();
      competitorLayer.clearLayers();
      updateCount(counterEl, 0);
      updateFilterCount(filterCounterEl, filterTriggerEls, filters);
      fetch(buildUrl(), { headers: { "X-Requested-With": "XMLHttpRequest" } })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          var bounds = [];
          var visits = data.visits || [];
          var competitorAds = data.competitor_ads || [];
          updateCount(counterEl, visits.length);
          showTruncation(data);

          visits.forEach(function (item) {
            var state = SUPPORT_STATES[item.support_code || ""] || SUPPORT_STATES[""];
            var tooltipParts = [item.label, state.label];
            if (item.advertising_label) {
              tooltipParts.push(item.advertising_label);
            }
            var marker = window.L.marker([item.lat, item.lng], {
              icon: visitPin(item),
              bubblingMouseEvents: false,
              fsSupportCode: item.support_code || ""
            })
              .bindTooltip(tooltipParts.join(" · "), { direction: "top", offset: [0, -44] })
              .addTo(pinsLayer);
            marker.on("click", function () {
              openDetailModal(detailModalEl, item, "Levantamiento");
            });
            bounds.push([item.lat, item.lng]);
          });

          competitorAds.forEach(function (item) {
            var marker = window.L.marker([item.lat, item.lng], {
              icon: competitorPin(item),
              bubblingMouseEvents: false
            })
              .bindTooltip(item.label + " · " + item.type_label, { direction: "top", offset: [0, -22] })
              .addTo(competitorLayer);
            marker.on("click", function () {
              openDetailModal(detailModalEl, item, "Detección de competencia");
            });
            bounds.push([item.lat, item.lng]);
          });

          if (bounds.length && !userOwnsView) {
            map.fitBounds(bounds, { padding: [30, 30], maxZoom: 16 });
          }
          userOwnsView = true;
          // Pin HTML contains <i data-lucide="..."> placeholders — render
          // them now that Leaflet has placed the markers in the DOM.
          if (window.cmRenderIcons) window.cmRenderIcons();
        })
        .catch(function () {
          updateCount(counterEl, 0);
          if (window.console && window.console.error) {
            window.console.error("Field survey map data load failed");
          }
        });
    }

    if (filters) {
      Array.prototype.forEach.call(filters.elements, function (input) {
        input.addEventListener("change", load);
      });
    }
    if (resetButton && filters) {
      resetButton.addEventListener("click", function () {
        filters.reset();
        Array.prototype.forEach.call(filters.elements, function (input) {
          if (input.name) {
            input.dispatchEvent(new Event("change", { bubbles: true }));
          }
        });
        load();
      });
    }
    if (myLocationButton) {
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
        setLocationButton(myLocationButton, "Mi ubicación", false);
        showLocationStatus(locationStatusEl, "Ubicación encontrada.", "success", 3000);
      };

      var renderLocationError = function (error) {
        var message = geolocationErrorMessage(error);
        setLocationButton(myLocationButton, message, false);
        showLocationStatus(locationStatusEl, message, "danger", 7000);
      };

      myLocationButton.addEventListener("click", function () {
        setLocationButton(myLocationButton, "Ubicando...", true);
        showLocationStatus(locationStatusEl, "Buscando tu ubicación...", "info");

        // Pasamos por el gate: muestra pre-aviso si está en "prompt",
        // panel de instrucciones si está "denied", aviso de HTTPS si aplica.
        // Si ya está concedido, va directo al fetch sin abrir modal.
        if (window.GeolocationGate) {
          window.GeolocationGate.require({
            mode: "soft",
            reason: "Para mostrar tu posición actual en el mapa.",
            onGranted: renderUserLocation,
            onDenied: renderLocationError,
            onSkipped: function () {
              setLocationButton(myLocationButton, "Mi ubicación", false);
              showLocationStatus(locationStatusEl, "Sin ubicación.", "info", 3000);
            }
          });
          return;
        }

        // Fallback si el gate no está disponible.
        if (!window.isSecureContext || !navigator.geolocation) {
          setLocationButton(myLocationButton, "Ubicación no disponible", false);
          showLocationStatus(
            locationStatusEl,
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

    function showCreateZoomGateMessage() {
      var distanceMeters = getCreateGateDistanceMeters();
      var roundedMeters = roundMetersForUi(distanceMeters);
      var message = "Acerca el mapa hasta 100 m o menos para abrir este menu.";
      if (roundedMeters !== null && roundedMeters > createGateMeters) {
        message = "Acerca el mapa: ahora esta en aprox. " + roundedMeters + " m. Debe estar en 100 m o menos.";
      }
      showLocationStatus(locationStatusEl, message, "danger", 3500);
    }

    var CREATE_PRESETS = {
      visit: {
        title: "Nueva visita",
        subtitle: "Completa los datos de la visita",
        icon: "home-2",
        bgClass: "bg-light-primary text-primary"
      },
      competitor: {
        title: "Nueva detección de competencia",
        subtitle: "Reporta publicidad de la oposición",
        icon: "flag",
        bgClass: "bg-light-danger text-danger"
      }
    };

    function applyCreatePreset(action) {
      var preset = CREATE_PRESETS[action] || CREATE_PRESETS.visit;
      if (!createModalEl) {
        return;
      }
      var titleEl = createModalEl.querySelector("[data-create-title]");
      var subtitleEl = createModalEl.querySelector("[data-create-subtitle]");
      var iconEl = createModalEl.querySelector("[data-create-icon]");
      var iconBg = createModalEl.querySelector("[data-create-icon-bg]");
      if (titleEl) titleEl.textContent = preset.title;
      if (subtitleEl) subtitleEl.textContent = preset.subtitle;
      if (iconEl) {
        var iconName = safeIconName(preset.icon);
        if (iconEl.tagName && iconEl.tagName.toLowerCase() === "svg") {
          var replacement = document.createElement("i");
          replacement.setAttribute("data-create-icon", "");
          replacement.setAttribute("data-lucide", iconName);
          replacement.setAttribute("class", "fs-2");
          replacement.setAttribute("aria-hidden", "true");
          iconEl.replaceWith(replacement);
        } else {
          iconEl.setAttribute("data-lucide", iconName);
          iconEl.setAttribute("class", "fs-2");
        }
        if (window.cmRenderIcons) window.cmRenderIcons();
      }
      if (iconBg) iconBg.className = "symbol-label " + preset.bgClass;
    }

    function chooseAndCreate(latlng) {
      var mapState = { zoom: map.getZoom(), layer: activeBasemap };

      if (!chooseModalEl || !window.bootstrap) {
        if (createUrl) {
          applyCreatePreset("visit");
          openCreateModal(createModalEl, createUrl, latlng, mapState, load);
        }
        return;
      }

      var coordsEl = chooseModalEl.querySelector("[data-choose-coords]");
      if (coordsEl) {
        coordsEl.textContent =
          "En " + latlng.lat.toFixed(6) + " / " + latlng.lng.toFixed(6);
      }

      var modal = window.bootstrap.Modal.getOrCreateInstance(chooseModalEl);

      function pick(event) {
        var action = event.currentTarget.getAttribute("data-choose-action");
        modal.hide();
        var targetUrl =
          action === "competitor" ? createCompetitorUrl : createUrl;
        if (!targetUrl) {
          return;
        }
        applyCreatePreset(action);
        openCreateModal(
          createModalEl,
          targetUrl,
          latlng,
          mapState,
          load,
          action === "competitor"
            ? "No se pudo guardar la detección de competencia."
            : "No se pudo guardar el levantamiento."
        );
      }

      // Re-bind on each open so we don't accumulate stale closures.
      Array.prototype.forEach.call(
        chooseModalEl.querySelectorAll("[data-choose-action]"),
        function (btn) {
          btn.replaceWith(btn.cloneNode(true));
        }
      );
      Array.prototype.forEach.call(
        chooseModalEl.querySelectorAll("[data-choose-action]"),
        function (btn) {
          btn.addEventListener("click", pick);
        }
      );

      modal.show();
    }

    if (legendEl && legendToggleEl) {
      var LEGEND_KEY = "fs:map:legendOpen";
      var initialOpen = false;
      try {
        initialOpen = window.localStorage.getItem(LEGEND_KEY) === "1";
      } catch (e) { /* localStorage unavailable */ }

      function applyLegendState(open) {
        legendEl.classList.toggle("is-open", open);
        legendToggleEl.classList.toggle("is-active", open);
        legendToggleEl.setAttribute("aria-expanded", open ? "true" : "false");
        legendEl.setAttribute("aria-hidden", open ? "false" : "true");
      }
      applyLegendState(initialOpen);

      legendToggleEl.addEventListener("click", function () {
        var next = !legendEl.classList.contains("is-open");
        applyLegendState(next);
        try { window.localStorage.setItem(LEGEND_KEY, next ? "1" : "0"); } catch (e) {}
      });

      var legendCloseEl = legendEl.querySelector("[data-legend-close]");
      if (legendCloseEl) {
        legendCloseEl.addEventListener("click", function () {
          applyLegendState(false);
          try { window.localStorage.setItem(LEGEND_KEY, "0"); } catch (e) {}
        });
      }
    }

    map.on("click", function (event) {
      if (!createUrl && !createCompetitorUrl) {
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
        showCreateZoomGateMessage();
        return;
      }
      chooseAndCreate(event.latlng);
    });

    window.addEventListener("resize", function () { map.invalidateSize(); });

    load();
    window.setTimeout(function () { map.invalidateSize(); }, 150);
  });
})(window, document);
