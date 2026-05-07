(function (window, document) {
  "use strict";

  var ICON_ALIASES = {
    "billboard": "flag",
    "sticker": "tag"
  };

  function safeIconName(icon) {
    var raw = (icon || "").toLowerCase();
    if (ICON_ALIASES[raw]) {
      return ICON_ALIASES[raw];
    }
    return /^[a-z0-9-]+$/i.test(icon || "") ? icon : "element-12";
  }

  function pinIcon(color, icon) {
    var iconName = safeIconName(icon);
    var safeColor = /^#[0-9a-f]{3,8}$/i.test(color || "") ? color : "#3388ff";
    return window.L.divIcon({
      className: "map-type-pin",
      html:
        '<span class="map-type-pin__inner" style="background:' + safeColor + ';color:#fff">' +
          '<i class="ki-solid ki-' + iconName + '" style="color:#fff"></i>' +
        '</span>',
      iconSize: [38, 38],
      iconAnchor: [19, 19],
      popupAnchor: [0, -18]
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
    if (detailLink) {
      detailLink.href = item.url;
    }
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
            // result.data.html is server-rendered with Django autoescape.
            setHtml(bodyEl, result.data.html || "");
            bindForm();
          })
          .catch(function () {
            setHtml(bodyEl, '<div class="alert alert-danger">No se pudo guardar el levantamiento.</div>');
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
    var chooseModalEl = document.getElementById("field-survey-choose-modal");
    var counterEl = document.getElementById("field-survey-map-count");
    var filterCounterEl = document.getElementById("field-survey-filter-count");
    var filterTriggerEls = document.querySelectorAll(".field-survey-map-filter-trigger");
    var resetButton = document.getElementById("field-survey-map-reset");
    var myLocationButton = document.getElementById("field-survey-my-location");
    var locationStatusEl = document.querySelector("[data-location-status]");
    var createUrl = el.dataset.createUrl || "";
    var createCompetitorUrl = el.dataset.createCompetitorUrl || "";

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
    var competitorLayer = window.L.layerGroup().addTo(map);
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

          visits.forEach(function (item) {
            var marker = window.L.marker([item.lat, item.lng], {
              icon: pinIcon(item.color, item.type_icon),
              bubblingMouseEvents: false
            })
              .bindTooltip(item.label, { direction: "top", offset: [0, -34] })
              .addTo(pinsLayer);
            marker.on("click", function () {
              openDetailModal(detailModalEl, item, "Levantamiento");
            });
            bounds.push([item.lat, item.lng]);
          });

          competitorAds.forEach(function (item) {
            var marker = window.L.marker([item.lat, item.lng], {
              icon: pinIcon(item.color, item.type_icon),
              bubblingMouseEvents: false
            })
              .bindTooltip(item.label + " · " + item.type_label, { direction: "top", offset: [0, -34] })
              .addTo(competitorLayer);
            marker.on("click", function () {
              openDetailModal(detailModalEl, item, "Detección de competencia");
            });
            bounds.push([item.lat, item.lng]);
          });

          if (bounds.length) {
            map.fitBounds(bounds, { padding: [30, 30], maxZoom: 16 });
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
      myLocationButton.addEventListener("click", function () {
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

        setLocationButton(myLocationButton, "Ubicando...", true);
        showLocationStatus(locationStatusEl, "Buscando tu ubicación...", "info");
        navigator.geolocation.getCurrentPosition(
          function (position) {
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

            map.setView([lat, lng], Math.max(map.getZoom(), 16));
            setLocationButton(myLocationButton, "Mi ubicación", false);
            showLocationStatus(locationStatusEl, "Ubicación encontrada.", "success", 3000);
          },
          function (error) {
            var message = geolocationErrorMessage(error);
            setLocationButton(myLocationButton, message, false);
            showLocationStatus(locationStatusEl, message, "danger", 7000);
          },
          {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 30000
          }
        );
      });
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
      if (iconEl) iconEl.className = "ki-outline ki-" + preset.icon + " fs-2";
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
        openCreateModal(createModalEl, targetUrl, latlng, mapState, load);
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
      chooseAndCreate(event.latlng);
    });

    window.addEventListener("resize", function () { map.invalidateSize(); });

    load();
    window.setTimeout(function () { map.invalidateSize(); }, 150);
  });
})(window, document);
