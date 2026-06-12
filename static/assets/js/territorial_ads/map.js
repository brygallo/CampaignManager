(function (window, document) {
  "use strict";

  // Legacy / seeded icon names from the DB mapped to Lucide equivalents.
  // Stored values come from seed_territorial_ads_catalog (document, tag,
  // picture, tablet, flag, element-12) plus historical aliases.
  var ICON_ALIASES = {
    "billboard":  "flag",
    "sticker":    "tag",
    "document":   "file-text",
    "picture":    "image",
    "tablet":     "tablet",
    "element-12": "shapes",
    "flag":       "flag",
    "tag":        "tag"
  };

  function safeIconName(icon) {
    var raw = (icon || "").toLowerCase();
    if (ICON_ALIASES[raw]) {
      return ICON_ALIASES[raw];
    }
    return /^[a-z0-9-]+$/i.test(icon || "") ? icon : "shapes";
  }

  function pinIcon(color, icon, markerKind) {
    var iconName = safeIconName(icon);
    var safeColor = /^#[0-9a-f]{3,8}$/i.test(color || "") ? color : "#3388ff";
    var extraClass = markerKind === "refusal" ? " map-type-pin--refusal" : "";
    return window.L.divIcon({
      className: "map-type-pin" + extraClass,
      html:
        '<span class="map-type-pin__inner" style="background:' + safeColor + ';color:#fff">' +
          '<i data-lucide="' + iconName + '" style="color:#fff"></i>' +
        '</span>',
      iconSize: [38, 38],
      iconAnchor: [19, 19],
      popupAnchor: [0, -18]
    });
  }

  function buildCreateUrl(base, latlng, mapState) {
    var params = new URLSearchParams();
    params.set("offered_latitude", latlng.lat.toFixed(6));
    params.set("offered_longitude", latlng.lng.toFixed(6));
    if (mapState && mapState.zoom !== undefined && mapState.zoom !== null) {
      params.set("map_zoom", String(mapState.zoom));
    }
    if (mapState && mapState.layer) {
      params.set("map_layer", mapState.layer);
    }
    return base + (base.indexOf("?") === -1 ? "?" : "&") + params.toString();
  }

  function setHtml(node, html) {
    node.innerHTML = html;
    if (window.cmFormsets) {
      window.cmFormsets.init(node);
    }
  }

  function updateCount(counterEl, count) {
    if (!counterEl) {
      return;
    }
    var numberEl = counterEl.querySelector("[data-pin-count-number]");
    var labelEl = counterEl.querySelector("[data-pin-count-label]");
    var label = count === 1 ? "ubicación" : "ubicaciones";
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

  function buildClusterIcon(cluster) {
    var n = cluster.getChildCount();
    var size = n < 10 ? 36 : n < 50 ? 44 : 52;
    return window.L.divIcon({
      html: '<span class="map-cluster-bubble">' + n + '</span>',
      className: "map-cluster",
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

  function openUpdateModal(modalEl, detailModalEl, updateUrl, label, onSaved, opts) {
    if (!modalEl || !window.bootstrap || !updateUrl) return;
    opts = opts || {};
    var bodySelector = opts.bodySelector || "[data-update-modal-body]";
    var submitSelector = opts.submitSelector || "[data-update-submit]";
    var titleSelector = opts.titleSelector || "[data-update-modal-title]";
    var formSelector = opts.formSelector || "[data-map-update-form]";
    var bodyEl = modalEl.querySelector(bodySelector);
    var submitButton = modalEl.querySelector(submitSelector);
    var titleEl = modalEl.querySelector(titleSelector);
    if (titleEl && label) titleEl.textContent = "Editar " + label;
    setHtml(bodyEl, loadingHtml("Cargando formulario..."));

    if (detailModalEl) {
      var detail = window.bootstrap.Modal.getInstance(detailModalEl);
      if (detail) detail.hide();
    }
    var modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();

    function bindForm() {
      var form = modalEl.querySelector(formSelector);
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
              window.console.error("territorial-ads map update failed", error);
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
            window.console.error("territorial-ads map delete rejected", result);
          }
        })
        .catch(function (error) {
          if (window.console && window.console.error) {
            window.console.error("territorial-ads map delete failed", error);
          }
        })
        .finally(function () {
          freshBtn.disabled = false;
        });
    });
  }

  function openModal(modalEl, ad) {
    if (!modalEl || !window.bootstrap) {
      window.location.href = ad.url;
      return;
    }
    var titleEl = modalEl.querySelector("[data-modal-title]");
    var bodyEl = modalEl.querySelector("[data-modal-body]");
    var detailLink = modalEl.querySelector("[data-detail-link]");
    if (titleEl) {
      titleEl.textContent = ad.label || "Publicidad";
    }
    modalEl.dataset.currentLabel = ad.label || "";
    modalEl.dataset.currentDetailUrl = ad.url || "";
    modalEl.dataset.markerKind = "ad";
    if (detailLink) {
      detailLink.href = ad.url;
      detailLink.style.display = "";
    }
    applyActionLink(modalEl, "[data-edit-link]", ad.update_url);
    applyActionLink(modalEl, "[data-delete-link]", ad.delete_url);
    setHtml(
      bodyEl,
      '<div class="text-center text-muted py-10">' +
        '<div class="spinner-border" role="status"></div>' +
        '<div class="mt-3">Cargando…</div>' +
      '</div>'
    );

    var modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();

    fetch(ad.url, {
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
          '<div class="alert alert-danger">No se pudo cargar la información del aviso.</div>'
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
    if (window.CostTypeAmountToggle && window.CostTypeAmountToggle.init) {
      window.CostTypeAmountToggle.init(scope);
    }
  }

  function openRefusalPopup(modalEl, ad) {
    if (!modalEl || !window.bootstrap) {
      return;
    }
    var titleEl = modalEl.querySelector("[data-modal-title]");
    var bodyEl = modalEl.querySelector("[data-modal-body]");
    var detailLink = modalEl.querySelector("[data-detail-link]");
    if (titleEl) {
      titleEl.textContent = ad.label || "Rechazo";
    }
    modalEl.dataset.currentLabel = ad.label || "";
    modalEl.dataset.currentDetailUrl = ad.url || "";
    modalEl.dataset.markerKind = "refusal";
    if (detailLink) {
      detailLink.style.display = "none";
    }
    applyActionLink(modalEl, "[data-edit-link]", ad.update_url);
    applyActionLink(modalEl, "[data-delete-link]", ad.delete_url);
    setHtml(bodyEl, loadingHtml("Cargando..."));

    var modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();

    fetch(ad.url, {
      headers: { "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin"
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        setHtml(bodyEl, data.html || "");
        initDynamicContent(bodyEl);
      })
      .catch(function () {
        setHtml(
          bodyEl,
          '<div class="alert alert-danger">No se pudo cargar la información del rechazo.</div>'
        );
      });
  }

  function openRefusalCreateModal(modalEl, createUrl, latlng, mapState, onSaved) {
    if (!modalEl || !window.bootstrap || !createUrl) {
      return;
    }

    var bodyEl = modalEl.querySelector("[data-refusal-modal-body]");
    var submitButton = modalEl.querySelector("[data-refusal-submit]");
    var url = buildCreateUrl(createUrl, latlng, mapState);
    setHtml(bodyEl, loadingHtml("Cargando formulario..."));

    var modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    modal.show();

    function bindForm() {
      var form = modalEl.querySelector("[data-map-refusal-form]");
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
            setHtml(bodyEl, result.data.html || "");
            bindForm();
          })
          .catch(function (error) {
            if (window.console && window.console.error) {
              window.console.error("territorial-ads refusal create failed", error);
            }
            setHtml(bodyEl, '<div class="alert alert-danger">No se pudo guardar el rechazo.</div>');
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

  function openCreateModal(modalEl, createUrl, latlng, mapState, onSaved) {
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
        fetch(form.action, {
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
            setHtml(bodyEl, result.data.html || "");
            bindForm();
          })
          .catch(function () {
            setHtml(bodyEl, '<div class="alert alert-danger">No se pudo guardar el aviso.</div>');
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
    var el = document.getElementById("physical-ad-map");
    if (!el || !window.L) {
      return;
    }

    var shell = el.closest(".physical-ad-map-shell");
    var panel = document.getElementById("physical-ad-map-panel");
    var panelTriggers = document.querySelectorAll("[data-panel-toggle]");
    var modalEl = document.getElementById("physical-ad-modal");
    var createModalEl = document.getElementById("physical-ad-create-modal");
    var updateModalEl = document.getElementById("physical-ad-update-modal");
    var deleteModalEl = document.getElementById("physical-ad-delete-modal");
    var refusalUpdateModalEl = document.getElementById("physical-ad-refusal-update-modal");
    var refusalModalEl = document.getElementById("physical-ad-refusal-modal");
    var choiceModalEl = document.getElementById("physical-ad-choice-modal");

    if (modalEl) {
      var editLinkEl = modalEl.querySelector("[data-edit-link]");
      var deleteLinkEl = modalEl.querySelector("[data-delete-link]");
      if (editLinkEl) {
        editLinkEl.addEventListener("click", function (event) {
          event.preventDefault();
          var url = editLinkEl.dataset.actionUrl;
          if (!url) return;
          var targetModal = modalEl.dataset.markerKind === "refusal"
            ? refusalUpdateModalEl
            : updateModalEl;
          var formSelector = modalEl.dataset.markerKind === "refusal"
            ? "[data-map-refusal-update-form]"
            : "[data-map-update-form]";
          var bodySelector = modalEl.dataset.markerKind === "refusal"
            ? "[data-refusal-update-modal-body]"
            : "[data-update-modal-body]";
          var submitSelector = modalEl.dataset.markerKind === "refusal"
            ? "[data-refusal-update-submit]"
            : "[data-update-submit]";
          var titleSelector = modalEl.dataset.markerKind === "refusal"
            ? "[data-refusal-update-modal-title]"
            : "[data-update-modal-title]";
          openUpdateModal(
            targetModal,
            modalEl,
            url,
            modalEl.dataset.currentLabel || "",
            function () { load(); },
            { bodySelector: bodySelector, submitSelector: submitSelector, titleSelector: titleSelector, formSelector: formSelector }
          );
        });
      }
      if (deleteLinkEl) {
        deleteLinkEl.addEventListener("click", function (event) {
          event.preventDefault();
          var url = deleteLinkEl.dataset.actionUrl;
          if (!url) return;
          openDeleteModal(deleteModalEl, modalEl, url, modalEl.dataset.currentLabel || "", function () {
            load();
          });
        });
      }

      modalEl.addEventListener("workflow:transitioned", function (event) {
        event.preventDefault();
        var detailUrl = modalEl.dataset.currentDetailUrl;
        var bodyEl = modalEl.querySelector("[data-modal-body]");
        if (!detailUrl || !bodyEl) {
          load();
          return;
        }
        setHtml(bodyEl, loadingHtml("Actualizando..."));
        var isRefusal = modalEl.dataset.markerKind === "refusal";
        fetch(detailUrl, {
          headers: { "X-Requested-With": "XMLHttpRequest" },
          credentials: "same-origin"
        })
          .then(function (r) { return isRefusal ? r.json() : r.text(); })
          .then(function (payload) {
            if (isRefusal) {
              setHtml(bodyEl, (payload && payload.html) || "");
              initDynamicContent(bodyEl);
            } else {
              var detailHtml = detailHtmlFromPage(payload);
              if (!detailHtml) throw new Error("Empty detail content");
              setHtml(bodyEl, detailHtml);
              initDynamicContent(bodyEl);
            }
            load();
          })
          .catch(function () {
            setHtml(bodyEl, '<div class="alert alert-danger">No se pudo actualizar el detalle.</div>');
          });
      });
    }
    var counterEl = document.getElementById("physical-ad-map-count");
    var filterCounterEl = document.getElementById("physical-ad-filter-count");
    var filterTriggerEls = document.querySelectorAll(".physical-ad-map-filter-trigger");
    var resetButton = document.getElementById("physical-ad-map-reset");
    var myLocationButton = document.getElementById("physical-ad-my-location");
    var locationStatusEl = document.querySelector("[data-location-status]");
    var createUrl = el.dataset.createUrl || "";
    var refusalCreateUrl = el.dataset.refusalCreateUrl || "";
    var createGateMeters = 50;
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

    if (pinsLayer && typeof pinsLayer.on === "function") {
      var reRenderPinIcons = function () {
        if (window.cmRenderIcons) window.cmRenderIcons();
      };
      pinsLayer.on("animationend", reRenderPinIcons);
      pinsLayer.on("spiderfied", reRenderPinIcons);
      pinsLayer.on("unspiderfied", reRenderPinIcons);
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
    map.on("movestart zoomstart", function () { userOwnsView = true; });

    var filters = document.getElementById("physical-ad-map-filters");
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

    var truncationEl = document.getElementById("physical-ad-map-truncated");

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
      updateCount(counterEl, 0);
      updateFilterCount(filterCounterEl, filterTriggerEls, filters);
      fetch(buildUrl(), { headers: { "X-Requested-With": "XMLHttpRequest" } })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          var bounds = [];
          var ads = data.ads || [];
          updateCount(counterEl, ads.length);
          showTruncation(data);
          ads.forEach(function (ad) {
            var marker = window.L.marker([ad.lat, ad.lng], {
              icon: pinIcon(ad.color, ad.type_icon, ad.marker_kind),
              bubblingMouseEvents: false
            })
              .bindTooltip(ad.label, { direction: "top", offset: [0, -34] })
              .addTo(pinsLayer);
            marker.on("click", function () {
              if (ad.marker_kind === "refusal") {
                openRefusalPopup(modalEl, ad);
              } else {
                openModal(modalEl, ad);
              }
            });
            bounds.push([ad.lat, ad.lng]);
          });
          if (bounds.length && !userOwnsView) {
            map.fitBounds(bounds, { padding: [30, 30], maxZoom: 16 });
          }
          userOwnsView = true;
          if (window.cmRenderIcons) window.cmRenderIcons();
        })
        .catch(function () {
          updateCount(counterEl, 0);
          if (window.console && window.console.error) {
            window.console.error("Physical ad map data load failed");
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
      var message = "Acerca el mapa hasta " + createGateMeters + " m o menos para abrir este menu.";
      if (roundedMeters !== null && roundedMeters > createGateMeters) {
        message = "Acerca el mapa: ahora esta en aprox. " + roundedMeters + " m. Debe estar en " + createGateMeters + " m o menos.";
      }
      showLocationStatus(locationStatusEl, message, "danger", 3500);
    }

    function openChoiceModal(latlng) {
      var mapState = { zoom: map.getZoom(), layer: activeBasemap };
      if (!choiceModalEl || !window.bootstrap) {
        if (createUrl) {
          openCreateModal(createModalEl, createUrl, latlng, mapState, load);
        }
        return;
      }
      var modal = window.bootstrap.Modal.getOrCreateInstance(choiceModalEl);
      var buttons = choiceModalEl.querySelectorAll("[data-choice]");
      function pickHandler(event) {
        var choice = event.currentTarget.getAttribute("data-choice");
        modal.hide();
        window.setTimeout(function () {
          if (choice === "ad" && createUrl) {
            openCreateModal(createModalEl, createUrl, latlng, mapState, load);
          } else if (choice === "refusal" && refusalCreateUrl) {
            openRefusalCreateModal(refusalModalEl, refusalCreateUrl, latlng, mapState, load);
          }
        }, 200);
      }
      Array.prototype.forEach.call(buttons, function (btn) {
        btn.replaceWith(btn.cloneNode(true));
      });
      var fresh = choiceModalEl.querySelectorAll("[data-choice]");
      Array.prototype.forEach.call(fresh, function (btn) {
        btn.addEventListener("click", pickHandler);
      });
      modal.show();
    }

    map.on("click", function (event) {
      if (!createUrl && !refusalCreateUrl) {
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
      openChoiceModal(event.latlng);
    });

    window.addEventListener("resize", function () { map.invalidateSize(); });

    load();
    window.setTimeout(function () { map.invalidateSize(); }, 150);
  });
})(window, document);
