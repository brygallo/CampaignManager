/**
 * Leaflet availability guard.
 *
 * Leaflet (and the markercluster plugin) load from a CDN; on flaky
 * connections the script tag can fail silently and every map dies with
 * ``window.L`` undefined. ``window.cmEnsureLeaflet(cb)`` verifies Leaflet is
 * present and, if not, re-injects the script with retries/backoff before
 * invoking ``cb`` with ``window.L`` (or ``null`` after exhausting retries).
 */
(function () {
  "use strict";

  var LEAFLET_SRC = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
  var CLUSTER_SRC = "https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js";
  var MAX_RETRIES = 3;
  var RETRY_BASE_DELAY_MS = 1200;

  var pendingCallbacks = null;

  function loadScript(src, done) {
    var script = document.createElement("script");
    script.src = src;
    script.async = true;
    script.onload = function () { done(true); };
    script.onerror = function () {
      script.remove();
      done(false);
    };
    document.head.appendChild(script);
  }

  function leafletReady() {
    return !!(window.L && window.L.map);
  }

  function finish() {
    var callbacks = pendingCallbacks || [];
    pendingCallbacks = null;
    var result = leafletReady() ? window.L : null;
    callbacks.forEach(function (cb) {
      try { cb(result); } catch (err) { console.error(err); }
    });
  }

  function ensureCluster(done) {
    if (window.L && window.L.markerClusterGroup) { done(); return; }
    // Cluster plugin is optional: callers already fall back to plain layers.
    loadScript(CLUSTER_SRC, function () { done(); });
  }

  function attempt(retry) {
    if (leafletReady()) {
      ensureCluster(finish);
      return;
    }
    if (retry >= MAX_RETRIES) {
      console.error("Leaflet no pudo cargarse tras " + MAX_RETRIES + " intentos.");
      finish();
      return;
    }
    loadScript(LEAFLET_SRC, function (ok) {
      if (ok && leafletReady()) {
        ensureCluster(finish);
        return;
      }
      window.setTimeout(function () { attempt(retry + 1); }, RETRY_BASE_DELAY_MS * (retry + 1));
    });
  }

  window.cmEnsureLeaflet = function (callback) {
    if (leafletReady() && window.L.markerClusterGroup) {
      callback(window.L);
      return;
    }
    if (pendingCallbacks) {
      pendingCallbacks.push(callback);
      return;
    }
    pendingCallbacks = [callback];
    attempt(0);
  };
})();
