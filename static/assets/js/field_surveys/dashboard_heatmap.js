(function (window, document) {
  "use strict";

  var container = document.getElementById("dashboard-support-heatmap");
  if (!container || !window.L || typeof window.L.heatLayer !== "function") {
    return;
  }

  var url = container.dataset.url;
  var query = container.dataset.querystring || "";
  var center = window.TENANT_MAP_CENTER || { lat: -2.3046, lng: -78.1175, zoom: 13 };
  var countEl = document.getElementById("dashboard-heatmap-count");
  var emptyEl = document.getElementById("dashboard-heatmap-empty");
  var legendEl = document.getElementById("dashboard-heatmap-legend");

  var map = window.L.map(container, {
    zoomControl: true,
    scrollWheelZoom: false,
    attributionControl: true
  }).setView([center.lat, center.lng], center.zoom);

  // Use the shared basemap helper so this map matches the rest of the app
  // (CARTO Voyager default + OSM/Satélite toggle). Fall back to a single
  // CARTO tile layer if the helper hasn't loaded.
  if (window.LeafletBasemaps && window.LeafletBasemaps.build) {
    window.LeafletBasemaps.build(map, null, {});
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

  // Per-layer gradient ramps. Keep the high-end color aligned with the layer
  // `color` so the legend swatch matches the densest hot spots.
  var LAYER_STYLES = {
    apoyo: {
      gradient: { 0.2: "#bbf7d0", 0.45: "#4ade80", 0.7: "#16a34a", 1.0: "#166534" }
    },
    indecisos: {
      gradient: { 0.2: "#fef9c3", 0.45: "#fde047", 0.7: "#eab308", 1.0: "#a16207" }
    },
    competencia: {
      gradient: { 0.2: "#fecdd3", 0.45: "#fb7185", 0.7: "#e11d48", 1.0: "#9f1239" }
    }
  };
  var LAYER_ORDER = ["apoyo", "indecisos", "competencia"];

  function setCount(n) {
    if (!countEl) return;
    countEl.textContent = n + (n === 1 ? " punto" : " puntos");
  }

  function showEmpty(show) {
    if (!emptyEl) return;
    emptyEl.classList.toggle("d-none", !show);
  }

  function clearChildren(node) {
    while (node.firstChild) {
      node.removeChild(node.firstChild);
    }
  }

  function renderLegend(layers, heatLayers) {
    if (!legendEl) return;
    clearChildren(legendEl);
    LAYER_ORDER.forEach(function (key) {
      var layer = layers[key];
      if (!layer) return;
      var item = document.createElement("label");
      item.className = "d-inline-flex align-items-center gap-2 me-4 mb-1";
      item.style.cursor = "pointer";

      var checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.className = "form-check-input m-0";
      checkbox.checked = Boolean(heatLayers[key]);
      checkbox.disabled = !layer.count;
      checkbox.addEventListener("change", function () {
        var hl = heatLayers[key];
        if (!hl) return;
        if (checkbox.checked) {
          hl.addTo(map);
        } else {
          map.removeLayer(hl);
        }
      });

      var swatch = document.createElement("span");
      swatch.style.display = "inline-block";
      swatch.style.width = "12px";
      swatch.style.height = "12px";
      swatch.style.borderRadius = "50%";
      swatch.style.background = layer.color;

      var text = document.createElement("span");
      text.className = "fs-7 fw-semibold text-gray-700";
      text.textContent = layer.label + " (" + layer.count + ")";

      item.appendChild(checkbox);
      item.appendChild(swatch);
      item.appendChild(text);
      legendEl.appendChild(item);
    });
  }

  fetch(url + (query ? "?" + query : ""), {
    headers: { Accept: "application/json" },
    credentials: "same-origin"
  })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      var layers = (data && data.layers) || {};
      var total = (data && typeof data.total === "number") ? data.total : 0;
      setCount(total);

      if (!total) {
        showEmpty(true);
        renderLegend(layers, {});
        return;
      }
      showEmpty(false);

      var heatLayers = {};
      var allPoints = [];

      LAYER_ORDER.forEach(function (key) {
        var layer = layers[key];
        if (!layer || !layer.points || !layer.points.length) return;
        var style = LAYER_STYLES[key] || {};
        var hl = window.L.heatLayer(layer.points, {
          radius: 28,
          blur: 22,
          maxZoom: 17,
          minOpacity: 0.35,
          gradient: style.gradient
        });
        hl.addTo(map);
        heatLayers[key] = hl;
        layer.points.forEach(function (p) { allPoints.push([p[0], p[1]]); });
      });

      renderLegend(layers, heatLayers);

      if (allPoints.length) {
        var bounds = window.L.latLngBounds(allPoints);
        if (bounds.isValid()) {
          map.fitBounds(bounds, { padding: [30, 30], maxZoom: 15 });
        }
      }
    })
    .catch(function () {
      setCount(0);
      showEmpty(true);
    });
})(window, document);
