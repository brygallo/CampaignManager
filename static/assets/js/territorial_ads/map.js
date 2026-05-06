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

  function buildPopupUrl(template, id) {
    // The url tag was reversed against pk=0; swap that segment for the real id.
    return template.replace(/\/0\/?$/, "/" + id + "/");
  }

  function setHtml(node, html) {
    // Content originates from our own Django template with autoescape on, so
    // user-supplied fields are HTML-escaped before reaching the browser.
    node.innerHTML = html;
  }

  function openModal(modalEl, ad, popupUrlTemplate) {
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

    fetch(buildPopupUrl(popupUrlTemplate, ad.id), {
      headers: { "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin"
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        titleEl.textContent = data.title || titleEl.textContent;
        detailLink.href = data.url || detailLink.href;
        setHtml(bodyEl, data.html || "");
      })
      .catch(function () {
        setHtml(
          bodyEl,
          '<div class="alert alert-danger">No se pudo cargar la información del aviso.</div>'
        );
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var el = document.getElementById("physical-ad-map");
    if (!el || !window.L) {
      return;
    }

    var modalEl = document.getElementById("physical-ad-modal");
    var popupUrlTemplate = el.dataset.popupUrl || "";

    // Default view: Macas, Morona Santiago.
    var defaultLat = parseFloat(el.dataset.defaultLat) || -2.3046;
    var defaultLng = parseFloat(el.dataset.defaultLng) || -78.1175;
    var defaultZoom = parseInt(el.dataset.defaultZoom || "13", 10);
    var map = window.L.map(el).setView([defaultLat, defaultLng], defaultZoom);
    var pinsLayer = window.L.layerGroup().addTo(map);

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
      fetch(buildUrl(), { headers: { "X-Requested-With": "XMLHttpRequest" } })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          var bounds = [];
          (data.ads || []).forEach(function (ad) {
            var marker = window.L.marker([ad.lat, ad.lng], { icon: pinIcon(ad.color) })
              .bindTooltip(ad.label, { direction: "top", offset: [0, -34] })
              .addTo(pinsLayer);
            marker.on("click", function () {
              openModal(modalEl, ad, popupUrlTemplate);
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

    load();
    setTimeout(function () { map.invalidateSize(); }, 150);
  });
})(window, document);
