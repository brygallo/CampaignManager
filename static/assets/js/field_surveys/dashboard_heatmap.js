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

  var map = window.L.map(container, {
    zoomControl: true,
    scrollWheelZoom: false,
    attributionControl: true
  }).setView([center.lat, center.lng], center.zoom);

  window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; <a href=\"https://www.openstreetmap.org/copyright\">OpenStreetMap</a>"
  }).addTo(map);

  function setCount(n) {
    if (!countEl) return;
    countEl.textContent = n + (n === 1 ? " punto" : " puntos");
  }

  function showEmpty(show) {
    if (!emptyEl) return;
    emptyEl.classList.toggle("d-none", !show);
  }

  fetch(url + (query ? "?" + query : ""), {
    headers: { Accept: "application/json" },
    credentials: "same-origin"
  })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      var pts = (data && data.points) || [];
      setCount(pts.length);
      if (!pts.length) {
        showEmpty(true);
        return;
      }
      showEmpty(false);
      window.L.heatLayer(pts, {
        radius: 28,
        blur: 22,
        maxZoom: 17,
        minOpacity: 0.35,
        gradient: {
          0.2: "#bbf7d0",
          0.45: "#4ade80",
          0.7: "#16a34a",
          1.0: "#166534"
        }
      }).addTo(map);
      var bounds = window.L.latLngBounds(pts.map(function (p) {
        return [p[0], p[1]];
      }));
      if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [30, 30], maxZoom: 15 });
      }
    })
    .catch(function () {
      setCount(0);
      showEmpty(true);
    });
})(window, document);
