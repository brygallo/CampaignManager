(function (window, document) {
  "use strict";

  function buildBasemaps(map, overlays, opts) {
    opts = opts || {};
    var carto = window.L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
      {
        maxZoom: 20,
        subdomains: "abcd",
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
      }
    );
    var osm = window.L.tileLayer(
      "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
      {
        maxZoom: 19,
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      }
    );
    var satellite = window.L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      {
        maxZoom: 19,
        attribution:
          'Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community'
      }
    );
    var baseLayers = {
      "Mapa (CARTO)": carto,
      "OSM": osm,
      "Satélite": satellite
    };
    var initialBasemap = opts.initialBasemap || "carto";
    if (initialBasemap === "satellite") {
      satellite.addTo(map);
    } else if (initialBasemap === "osm") {
      osm.addTo(map);
    } else {
      carto.addTo(map);
    }
    if (!opts.skipNativeControl) {
      window.L.control.layers(baseLayers, overlays || null, { collapsed: true }).addTo(map);
    }
    return { baseLayers: baseLayers, refs: { carto: carto, osm: osm, satellite: satellite } };
  }

  window.LeafletBasemaps = { build: buildBasemaps };

  function findField(form, name) {
    if (!form || !name) {
      return null;
    }
    return form.querySelector('[name="' + name + '"]');
  }

  function parseNumber(value, fallback) {
    var number = parseFloat(value);
    return Number.isFinite(number) ? number : fallback;
  }

  function setStatus(container, text) {
    var status = container.querySelector("[data-leaflet-status]");
    if (status) {
      status.textContent = text;
    }
  }

  function setPoint(container, marker, latField, lngField, latlng, map, options) {
    options = options || {};
    latField.value = latlng.lat.toFixed(6);
    lngField.value = latlng.lng.toFixed(6);
    latField.dispatchEvent(new Event("change", { bubbles: true }));
    lngField.dispatchEvent(new Event("change", { bubbles: true }));
    if (options.manualField) {
      options.manualField.value = options.manual ? "True" : "False";
      options.manualField.dispatchEvent(new Event("change", { bubbles: true }));
    }
    if (options.accuracyField && options.accuracy !== undefined && options.accuracy !== null) {
      options.accuracyField.value = Number(options.accuracy).toFixed(2);
      options.accuracyField.dispatchEvent(new Event("change", { bubbles: true }));
    }
    marker.setLatLng(latlng).addTo(map);
    setStatus(container, "Lat: " + latField.value + " / Lng: " + lngField.value);
  }

  function initLeafletMap(container) {
    if (container.dataset.leafletInitialized === "true" || !window.L) {
      return;
    }

    var form = container.closest("form");
    var latField = findField(form, container.dataset.latField);
    var lngField = findField(form, container.dataset.lngField);
    var manualField = findField(form, container.dataset.manualField);
    var accuracyField = findField(form, container.dataset.accuracyField);
    var canvas = container.querySelector(".leaflet-map-widget__canvas");
    if (!latField || !lngField || !canvas) {
      return;
    }

    container.dataset.leafletInitialized = "true";

    var tenantCenter = window.TENANT_MAP_CENTER || {};
    var defaultLat = parseNumber(container.dataset.defaultLat, tenantCenter.lat || -2.170998);
    var defaultLng = parseNumber(container.dataset.defaultLng, tenantCenter.lng || -79.922359);
    var zoom = parseInt(container.dataset.defaultZoom || tenantCenter.zoom || "13", 10);
    var lat = parseNumber(latField.value, defaultLat);
    var lng = parseNumber(lngField.value, defaultLng);
    var hasPoint = latField.value !== "" && lngField.value !== "";

    var map = window.L.map(canvas).setView([lat, lng], zoom);
    buildBasemaps(map, null, {
      initialBasemap: container.dataset.defaultBasemap || "carto"
    });

    var marker = window.L.marker([lat, lng], { draggable: true });
    if (hasPoint) {
      marker.addTo(map);
      setStatus(container, "Lat: " + latField.value + " / Lng: " + lngField.value);
    }

    map.on("click", function (event) {
      setPoint(container, marker, latField, lngField, event.latlng, map, { manualField: manualField, manual: true });
    });

    marker.on("dragend", function () {
      setPoint(container, marker, latField, lngField, marker.getLatLng(), map, { manualField: manualField, manual: true });
    });

    var locationButton = container.querySelector("[data-leaflet-current-location]");
    if (locationButton) {
      locationButton.addEventListener("click", function () {
        var onGranted = function (position) {
          var current = window.L.latLng(position.coords.latitude, position.coords.longitude);
          map.setView(current, 17);
          setPoint(container, marker, latField, lngField, current, map, {
            manualField: manualField,
            manual: false,
            accuracyField: accuracyField,
            accuracy: position.coords.accuracy
          });
        };
        var onDenied = function () {
          setStatus(container, "No se pudo obtener la ubicación actual.");
        };

        // Pasamos por el gate global: muestra pre-aviso, instrucciones por
        // plataforma cuando está bloqueado, y aviso de HTTPS si aplica.
        if (window.GeolocationGate) {
          setStatus(container, "Obteniendo ubicación actual...");
          window.GeolocationGate.require({
            mode: "soft",
            reason: "Para precargar tu ubicación actual en el mapa.",
            onGranted: onGranted,
            onDenied: onDenied,
            onSkipped: onDenied
          });
          return;
        }

        // Fallback si el gate no está disponible (no debería pasar).
        if (!navigator.geolocation) {
          setStatus(container, "El navegador no soporta geolocalización.");
          return;
        }
        setStatus(container, "Obteniendo ubicación actual...");
        navigator.geolocation.getCurrentPosition(
          onGranted,
          onDenied,
          { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
        );
      });
    }

    var clearButton = container.querySelector("[data-leaflet-clear]");
    if (clearButton) {
      clearButton.addEventListener("click", function () {
        latField.value = "";
        lngField.value = "";
        marker.remove();
        setStatus(container, "Haz clic en el mapa o usa tu ubicación actual.");
      });
    }

    setTimeout(function () {
      map.invalidateSize();
    }, 150);
  }

  function initDetailMap(container) {
    if (container.dataset.leafletInitialized === "true" || !window.L) {
      return;
    }

    var canvas = container.querySelector(".leaflet-detail-map__canvas");
    if (!canvas) {
      return;
    }

    var zoom = parseInt(container.dataset.zoom || "16", 10);
    var pointsAttr = container.dataset.points;
    var points = null;
    if (pointsAttr) {
      try {
        points = JSON.parse(pointsAttr);
      } catch (e) {
        points = null;
      }
    }

    if (points && points.length) {
      container.dataset.leafletInitialized = "true";
      var multiMap = window.L.map(canvas, {
        dragging: true,
        scrollWheelZoom: false
      });
      buildBasemaps(multiMap);
      var bounds = window.L.latLngBounds([]);
      points.forEach(function (point) {
        var color = point.color || "#3388ff";
        var icon = window.L.divIcon({
          className: "leaflet-detail-pin",
          html:
            '<svg width="30" height="42" viewBox="0 0 30 42" xmlns="http://www.w3.org/2000/svg">' +
              '<path d="M15 0 C6.72 0 0 6.72 0 15 c0 11 15 27 15 27 s15 -16 15 -27 C30 6.72 23.28 0 15 0 z" ' +
                'fill="' + color + '" stroke="#ffffff" stroke-width="2"/>' +
              '<circle cx="15" cy="15" r="5.5" fill="#ffffff"/>' +
            '</svg>',
          iconSize: [30, 42],
          iconAnchor: [15, 42],
          popupAnchor: [0, -38],
          tooltipAnchor: [0, -34]
        });
        var marker = window.L.marker([point.latitude, point.longitude], { icon: icon }).addTo(multiMap);
        var label = point.label || "Ubicación";
        marker.bindTooltip(label, {
          permanent: true,
          direction: "top",
          className: "leaflet-detail-pin-label"
        });
        marker.bindPopup(label + "<br/>Lat: " + point.latitude + "<br/>Lng: " + point.longitude);
        bounds.extend([point.latitude, point.longitude]);
      });
      if (points.length === 1) {
        multiMap.setView(bounds.getCenter(), zoom);
      } else {
        multiMap.fitBounds(bounds, { padding: [40, 40], maxZoom: zoom });
      }
      setTimeout(function () {
        multiMap.invalidateSize();
      }, 150);
      return;
    }

    var lat = parseNumber(container.dataset.lat, null);
    var lng = parseNumber(container.dataset.lng, null);
    if (lat === null || lng === null) {
      return;
    }

    container.dataset.leafletInitialized = "true";
    var title = container.dataset.title || "Ubicación";
    var map = window.L.map(canvas, {
      dragging: true,
      scrollWheelZoom: false
    }).setView([lat, lng], zoom);

    buildBasemaps(map);

    window.L.marker([lat, lng]).addTo(map).bindPopup(title);

    setTimeout(function () {
      map.invalidateSize();
    }, 150);
  }

  window.initLeafletMaps = function (scope) {
    scope = scope || document;
    if (!window.L) {
      return;
    }
    var maps = [];
    if (scope.matches && scope.matches("[data-leaflet-map]")) {
      maps.push(scope);
    }
    maps = maps.concat([].slice.call(scope.querySelectorAll("[data-leaflet-map]")));
    maps.forEach(initLeafletMap);

    var detailMaps = [];
    if (scope.matches && scope.matches("[data-detail-map]")) {
      detailMaps.push(scope);
    }
    detailMaps = detailMaps.concat([].slice.call(scope.querySelectorAll("[data-detail-map]")));
    detailMaps.forEach(initDetailMap);
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      window.initLeafletMaps(document);
    });
  } else {
    window.initLeafletMaps(document);
  }
})(window, document);
