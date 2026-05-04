(function (window, document) {
  "use strict";

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

    var defaultLat = parseNumber(container.dataset.defaultLat, -2.170998);
    var defaultLng = parseNumber(container.dataset.defaultLng, -79.922359);
    var zoom = parseInt(container.dataset.defaultZoom || "13", 10);
    var lat = parseNumber(latField.value, defaultLat);
    var lng = parseNumber(lngField.value, defaultLng);
    var hasPoint = latField.value !== "" && lngField.value !== "";

    var map = window.L.map(canvas).setView([lat, lng], zoom);
    window.L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

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
        if (!navigator.geolocation) {
          setStatus(container, "El navegador no soporta geolocalización.");
          return;
        }
        setStatus(container, "Obteniendo ubicación actual...");
        navigator.geolocation.getCurrentPosition(
          function (position) {
            var current = window.L.latLng(position.coords.latitude, position.coords.longitude);
            map.setView(current, 17);
            setPoint(container, marker, latField, lngField, current, map, {
              manualField: manualField,
              manual: false,
              accuracyField: accuracyField,
              accuracy: position.coords.accuracy
            });
          },
          function () {
            setStatus(container, "No se pudo obtener la ubicación actual.");
          },
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
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      window.initLeafletMaps(document);
    });
  } else {
    window.initLeafletMaps(document);
  }
})(window, document);
