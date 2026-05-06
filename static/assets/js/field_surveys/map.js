(function (window, document) {
  "use strict";

  function colorForResult(code) {
    if (code === "APOYA") return "#50cd89";
    if (code === "INDECISO") return "#ffc700";
    if (code === "NO_APOYA") return "#f1416c";
    if (code === "NO_ATENDIO") return "#7e8299";
    return "#3e97ff";
  }

  function marker(lat, lng, color) {
    return window.L.circleMarker([lat, lng], {
      radius: 8,
      color: color,
      fillColor: color,
      fillOpacity: 0.85,
      weight: 2
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var el = document.getElementById("field-survey-map");
    if (!el || !window.L) {
      return;
    }
    var map = window.L.map(el).setView([-2.170998, -79.922359], 13);

    var visits = window.L.layerGroup().addTo(map);
    var heat = window.L.layerGroup().addTo(map);
    var ownAds = window.L.layerGroup().addTo(map);
    var competitorAds = window.L.layerGroup().addTo(map);

    var overlays = {
      "Visitas": visits,
      "Mapa de calor de apoyo": heat,
      "Publicidad propia": ownAds,
      "Publicidad competencia": competitorAds
    };

    if (window.LeafletBasemaps && window.LeafletBasemaps.build) {
      window.LeafletBasemaps.build(map, overlays);
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
      window.L.control.layers(null, overlays).addTo(map);
    }

    function load() {
      visits.clearLayers();
      heat.clearLayers();
      ownAds.clearLayers();
      competitorAds.clearLayers();
      var extra = document.querySelector("#map-extra-filters [name='competitor']");
      var url = el.dataset.url || "";
      if (extra && extra.value) {
        url += (url.indexOf("?") === -1 ? "?" : "&") + "competitor=" + encodeURIComponent(extra.value);
      }
      fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } })
        .then(function (response) { return response.json(); })
        .then(function (data) {
          var bounds = [];
          data.visits.forEach(function (item) {
            var point = marker(item.lat, item.lng, colorForResult(item.result))
              .bindPopup("<strong>Visita</strong><br>Votantes: " + item.voters + "<br><a href='" + item.url + "'>Ver detalle</a>");
            point.addTo(visits);
            bounds.push([item.lat, item.lng]);
            if (item.result === "APOYA") {
              window.L.circle([item.lat, item.lng], {
                radius: 90,
                stroke: false,
                fillColor: "#50cd89",
                fillOpacity: 0.22
              }).addTo(heat);
            }
          });
          data.own_ads.forEach(function (item) {
            marker(item.lat, item.lng, "#181c32").bindPopup("<strong>Publicidad propia</strong><br>" + item.type).addTo(ownAds);
            bounds.push([item.lat, item.lng]);
          });
          data.competitor_ads.forEach(function (item) {
            marker(item.lat, item.lng, item.color).bindPopup("<strong>Competencia</strong><br>" + item.competitor + "<br>" + item.type).addTo(competitorAds);
            bounds.push([item.lat, item.lng]);
          });
          if (bounds.length) {
            map.fitBounds(bounds, { padding: [24, 24], maxZoom: 16 });
          }
        });
    }

    var competitor = document.querySelector("#map-extra-filters [name='competitor']");
    if (competitor) {
      competitor.addEventListener("change", load);
    }
    load();
    setTimeout(function () {
      map.invalidateSize();
    }, 150);
  });
})(window, document);
