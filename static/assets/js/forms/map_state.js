/*!
 * MapState — sync a Leaflet map's view to the URL hash.
 *
 * Hash format: ``#l=<lat>,<lng>&z=<zoom>&b=<basemap>``
 *   - ``l`` / ``z`` always present once the user moves/zooms.
 *   - ``b`` only present when the layer toggle reports a non-default basemap.
 *
 * Why a hash and not a query string?
 *   1. The hash never travels to the server, so it doesn't break Django CSRF
 *      or auth redirects.
 *   2. The browser preserves it across navigations (back button, F5, Edit
 *      modal close) without any extra plumbing.
 *
 * Usage:
 *   var state = window.MapState.attach(map, {
 *     getBasemap: function () { return preferredBasemap; },  // optional
 *     setBasemap: function (name) { ... },                   // optional
 *     defaultBasemap: "carto"
 *   });
 *   // state.restore() returns true if the hash was applied. Callers can
 *   // skip their own fitBounds() call to honour the saved view.
 */
(function (window, document) {
  "use strict";

  function parseHash() {
    var hash = window.location.hash || "";
    if (hash.charAt(0) === "#") hash = hash.substring(1);
    if (!hash) return null;
    var params = {};
    hash.split("&").forEach(function (pair) {
      var eq = pair.indexOf("=");
      if (eq < 0) return;
      params[pair.substring(0, eq)] = decodeURIComponent(pair.substring(eq + 1));
    });
    var ll = params.l ? params.l.split(",") : null;
    var lat = ll && ll.length === 2 ? parseFloat(ll[0]) : null;
    var lng = ll && ll.length === 2 ? parseFloat(ll[1]) : null;
    var zoom = params.z ? parseInt(params.z, 10) : null;
    var basemap = params.b || null;
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null;
    if (!Number.isFinite(zoom)) zoom = null;
    return { lat: lat, lng: lng, zoom: zoom, basemap: basemap };
  }

  function buildHash(lat, lng, zoom, basemap, defaultBasemap) {
    var parts = ["l=" + lat.toFixed(6) + "," + lng.toFixed(6)];
    if (Number.isFinite(zoom)) parts.push("z=" + zoom);
    if (basemap && basemap !== defaultBasemap) parts.push("b=" + basemap);
    return "#" + parts.join("&");
  }

  function attach(map, opts) {
    opts = opts || {};
    var defaultBasemap = opts.defaultBasemap || "carto";
    var getBasemap = typeof opts.getBasemap === "function" ? opts.getBasemap : function () { return defaultBasemap; };
    var setBasemap = typeof opts.setBasemap === "function" ? opts.setBasemap : null;

    var suppress = false;
    function writeHash() {
      if (suppress) return;
      var center = map.getCenter();
      var hash = buildHash(center.lat, center.lng, map.getZoom(), getBasemap(), defaultBasemap);
      // ``replaceState`` keeps the user's history clean — every drag/zoom
      // shouldn't push a new entry.
      try {
        window.history.replaceState(window.history.state, "", window.location.pathname + window.location.search + hash);
      } catch (e) {
        window.location.hash = hash.substring(1);
      }
    }

    function restore() {
      var parsed = parseHash();
      if (!parsed) return false;
      // Suppress while we apply so moveend/zoomend don't rewrite the hash.
      suppress = true;
      try {
        map.setView([parsed.lat, parsed.lng], parsed.zoom != null ? parsed.zoom : map.getZoom());
        if (parsed.basemap && setBasemap) setBasemap(parsed.basemap);
      } finally {
        suppress = false;
      }
      return true;
    }

    map.on("moveend", writeHash);
    map.on("zoomend", writeHash);

    return {
      restore: restore,
      write: writeHash,
      // Build the current map URL with up-to-date hash. Useful for ``?next=``
      // or share links.
      getCurrentUrl: function () {
        var center = map.getCenter();
        var hash = buildHash(center.lat, center.lng, map.getZoom(), getBasemap(), defaultBasemap);
        return window.location.pathname + window.location.search + hash;
      }
    };
  }

  window.MapState = { attach: attach, parseHash: parseHash };
})(window, document);
