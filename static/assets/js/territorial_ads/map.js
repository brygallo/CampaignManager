(function (window, document) {
  "use strict";

  function pinIcon(color) {
    return window.L.divIcon({
      className: "leaflet-detail-pin",
      html:
        '<svg width="30" height="42" viewBox="0 0 30 42" xmlns="http://www.w3.org/2000/svg">' +
          '<path d="M15 0 C6.72 0 0 6.72 0 15 c0 11 15 27 15 27 s15 -16 15 -27 C30 6.72 23.28 0 15 0 z" ' +
            'fill="' + color + '" stroke="#ffffff" stroke-width="2"/>' +
          '<circle cx="15" cy="15" r="5.5" fill="#ffffff"/>' +
        '</svg>',
      iconSize: [30, 42],
      iconAnchor: [15, 42],
      popupAnchor: [0, -38]
    });
  }

  function buildCreateUrl(base, latlng) {
    var params = new URLSearchParams();
    params.set("offered_latitude", latlng.lat.toFixed(6));
    params.set("offered_longitude", latlng.lng.toFixed(6));
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
    counterEl.textContent = count === 1 ? "1 pin" : count + " pines";
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
    var labelEl = button.querySelector(".physical-ad-map-fab__label");
    if (labelEl) {
      labelEl.textContent = label;
    }
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
        // Re-measure once the slide/fade transition has settled.
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

  function openModal(modalEl, ad) {
    if (!modalEl || !window.bootstrap) {
      window.location.href = ad.url;
      return;
    }
    var titleEl = modalEl.querySelector("[data-modal-title]");
    var bodyEl = modalEl.querySelector("[data-modal-body]");
    var detailLink = modalEl.querySelector("[data-detail-link]");
    titleEl.textContent = ad.label || "Publicidad";
    detailLink.href = ad.url;
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

  function openCreateModal(modalEl, createUrl, latlng, onSaved) {
    if (!modalEl || !window.bootstrap || !createUrl) {
      window.location.href = buildCreateUrl(createUrl, latlng);
      return;
    }

    var bodyEl = modalEl.querySelector("[data-create-modal-body]");
    var submitButton = modalEl.querySelector("[data-create-submit]");
    var url = buildCreateUrl(createUrl, latlng);
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
    var counterEl = document.getElementById("physical-ad-map-count");
    var filterCounterEl = document.getElementById("physical-ad-filter-count");
    var filterTriggerEls = document.querySelectorAll(".physical-ad-map-filter-trigger");
    var resetButton = document.getElementById("physical-ad-map-reset");
    var myLocationButton = document.getElementById("physical-ad-my-location");
    var createUrl = el.dataset.createUrl || "";

    // Default view: Macas, Morona Santiago.
    var defaultLat = parseFloat(el.dataset.defaultLat) || -2.3046;
    var defaultLng = parseFloat(el.dataset.defaultLng) || -78.1175;
    var defaultZoom = parseInt(el.dataset.defaultZoom || "13", 10);
    var isMobileViewport = window.matchMedia("(max-width: 767.98px)");
    var map = window.L.map(el, { zoomControl: false }).setView([defaultLat, defaultLng], defaultZoom);
    var pinsLayer = window.L.layerGroup().addTo(map);
    var locationLayer = window.L.layerGroup().addTo(map);
    window.L.control.zoom({ position: isMobileViewport.matches ? "bottomright" : "bottomleft" }).addTo(map);

    if (window.LeafletBasemaps && window.LeafletBasemaps.build) {
      window.LeafletBasemaps.build(map, { "Pines": pinsLayer });
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
          ads.forEach(function (ad) {
            var marker = window.L.marker([ad.lat, ad.lng], {
              icon: pinIcon(ad.color),
              bubblingMouseEvents: false
            })
              .bindTooltip(ad.label, { direction: "top", offset: [0, -34] })
              .addTo(pinsLayer);
            marker.on("click", function () {
              openModal(modalEl, ad);
            });
            bounds.push([ad.lat, ad.lng]);
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
        // ``form.reset()`` does not fire change events; emit one so select2 + load react.
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
        if (!navigator.geolocation) {
          setLocationButton(myLocationButton, "No disponible", false);
          return;
        }

        setLocationButton(myLocationButton, "Ubicando...", true);
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
          },
          function () {
            setLocationButton(myLocationButton, "Permiso denegado", false);
            window.setTimeout(function () {
              setLocationButton(myLocationButton, "Mi ubicación", false);
            }, 2500);
          },
          {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 30000
          }
        );
      });
    }

    map.on("click", function (event) {
      if (!createUrl) {
        return;
      }
      // On phones the bottom-sheet may overlay part of the map — close it
      // instead of opening the create flow on the first tap-through.
      if (
        shell &&
        shell.getAttribute("data-panel-state") === "expanded" &&
        window.matchMedia("(max-width: 767.98px)").matches
      ) {
        panelApi.close();
        return;
      }
      openCreateModal(createModalEl, createUrl, event.latlng, load);
    });

    // Keep the Leaflet canvas accurate across viewport / orientation changes.
    window.addEventListener("resize", function () { map.invalidateSize(); });

    load();
    window.setTimeout(function () { map.invalidateSize(); }, 150);
  });
})(window, document);
