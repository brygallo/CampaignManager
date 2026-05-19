/**
 * GeolocationGate
 *
 * Pre-aviso + manejo de permisos de geolocalización con Bootstrap.
 *
 * Usa: bootstrap.Modal API, utilidades de Bootstrap y Keenicons. No introduce
 * estilos propios más allá de la animación de pulso del hero.
 *
 * API:
 *   GeolocationGate.require({
 *     mode: "hard" | "soft",      // hard: no se descarta hasta resolver
 *     reason: "Para registrar visitas en tu posición actual",
 *     onGranted: function (position) { ... },
 *     onDenied:  function () { ... },
 *     onSkipped: function () { ... },
 *   });
 *
 *   GeolocationGate.getCurrentPosition({ onGranted, onDenied });
 *
 * Todo el DOM se construye con createElement / textContent.
 */
(function (window, document) {
  "use strict";

  var STORAGE_KEY = "cm.geolocation.preference";
  var SESSION_NAG_KEY = "cm.geolocation.nagged";
  var DEFAULT_REASON = "Necesitamos tu ubicación para llenar el mapa con precisión.";
  var GEO_TIMEOUT_MS = 12000;
  var GEO_MAX_AGE_MS = 30000;

  // ---------- Plataforma / navegador --------------------------------------

  function detectPlatform() {
    var ua = (navigator.userAgent || "").toLowerCase();
    var platform = (navigator.platform || "").toLowerCase();

    var isIOS = /iphone|ipad|ipod/.test(ua) ||
                (platform === "macintel" && navigator.maxTouchPoints > 1);
    var isAndroid = /android/.test(ua);
    var isMac = !isIOS && /mac/.test(platform);
    var isWindows = /win/.test(platform);

    var browser = "other";
    if (/edg\//i.test(navigator.userAgent)) browser = "edge";
    else if (/firefox|fxios/i.test(navigator.userAgent)) browser = "firefox";
    else if (/chrome|crios/i.test(navigator.userAgent) && !/edg\//i.test(navigator.userAgent)) browser = "chrome";
    else if (/safari/i.test(navigator.userAgent) && !/chrome|crios|android/i.test(navigator.userAgent)) browser = "safari";

    var os = "other";
    if (isIOS) os = "ios";
    else if (isAndroid) os = "android";
    else if (isMac) os = "macos";
    else if (isWindows) os = "windows";
    else if (/linux/.test(platform)) os = "linux";

    return { os: os, browser: browser };
  }

  // ---------- Instrucciones por plataforma --------------------------------

  // Cada paso es array de segmentos: ["text", "..."] o ["bold", "..."].
  // Renderizado con createElement / textContent.
  function getReactivationInstructions(platform) {
    var key = platform.os + ":" + platform.browser;
    var T = function (s) { return ["text", s]; };
    var B = function (s) { return ["bold", s]; };

    var matrix = {
      "android:chrome": [
        [T("Toca el ícono de candado o información a la izquierda de la barra de direcciones.")],
        [T("Pulsa "), B("Permisos"), T(" » "), B("Ubicación"), T(".")],
        [T("Cambia la opción a "), B("Permitir"), T(".")],
        [T("Vuelve a esta pestaña y toca "), B("Reintentar"), T(".")]
      ],
      "android:firefox": [
        [T("Toca el ícono de candado a la izquierda de la URL.")],
        [T("Pulsa "), B("Editar permisos"), T(".")],
        [T("Habilita "), B("Acceder a tu ubicación"), T(".")],
        [T("Recarga y toca "), B("Reintentar"), T(".")]
      ],
      "android:edge": [
        [T("Toca el ícono de candado en la barra de direcciones.")],
        [T("Abre "), B("Permisos del sitio"), T(" » "), B("Ubicación"), T(".")],
        [T("Selecciona "), B("Permitir"), T(".")],
        [T("Recarga la página y toca "), B("Reintentar"), T(".")]
      ],
      "ios:safari": [
        [T("Abre "), B("Ajustes"), T(" del iPhone/iPad.")],
        [T("Entra en "), B("Privacidad y seguridad"), T(" » "), B("Localización"), T(".")],
        [T("Verifica que "), B("Localización"), T(" esté activada.")],
        [T("Vuelve a "), B("Safari"), T(" en la lista y elige "), B("Preguntar"), T(" o "), B("Permitir"), T(".")],
        [T("Recarga esta página y toca "), B("Reintentar"), T(".")]
      ],
      "ios:chrome": [
        [T("Abre "), B("Ajustes"), T(" del iPhone/iPad.")],
        [T("Entra en "), B("Privacidad y seguridad"), T(" » "), B("Localización"), T(".")],
        [T("Busca "), B("Chrome"), T(" en la lista y selecciona "), B("Permitir mientras se usa la app"), T(".")],
        [T("Vuelve a Chrome, recarga la página y toca "), B("Reintentar"), T(".")]
      ],
      "ios:firefox": [
        [T("Abre "), B("Ajustes"), T(" del iPhone/iPad.")],
        [T("Entra en "), B("Privacidad y seguridad"), T(" » "), B("Localización"), T(".")],
        [T("Busca "), B("Firefox"), T(" y selecciona "), B("Permitir mientras se usa la app"), T(".")],
        [T("Vuelve a Firefox y toca "), B("Reintentar"), T(".")]
      ],
      "macos:safari": [
        [T("Ve al menú "), B("Safari"), T(" » "), B("Ajustes"), T(" » "), B("Sitios web"), T(".")],
        [T("Selecciona "), B("Localización"), T(" en la barra lateral.")],
        [T("Cambia esta web a "), B("Permitir"), T(".")],
        [T("Recarga la página y haz clic en "), B("Reintentar"), T(".")]
      ],
      "macos:chrome": [
        [T("Haz clic en el candado a la izquierda de la URL.")],
        [T("Abre "), B("Configuración del sitio"), T(".")],
        [T("Cambia "), B("Ubicación"), T(" a "), B("Permitir"), T(".")],
        [T("Recarga la página y haz clic en "), B("Reintentar"), T(".")]
      ],
      "macos:firefox": [
        [T("Haz clic en el candado a la izquierda de la URL.")],
        [T("Pulsa la "), B("X"), T(" junto a 'Bloqueado temporalmente' para Ubicación.")],
        [T("Recarga la página y haz clic en "), B("Reintentar"), T(".")]
      ],
      "windows:chrome": [
        [T("Haz clic en el candado a la izquierda de la URL.")],
        [T("Abre "), B("Configuración del sitio"), T(".")],
        [T("Cambia "), B("Ubicación"), T(" a "), B("Permitir"), T(".")],
        [T("Recarga la página y haz clic en "), B("Reintentar"), T(".")]
      ],
      "windows:edge": [
        [T("Haz clic en el candado a la izquierda de la URL.")],
        [T("Selecciona "), B("Permisos para este sitio"), T(".")],
        [T("Cambia "), B("Ubicación"), T(" a "), B("Permitir"), T(".")],
        [T("Recarga la página y haz clic en "), B("Reintentar"), T(".")]
      ],
      "windows:firefox": [
        [T("Haz clic en el candado a la izquierda de la URL.")],
        [T("Pulsa la "), B("X"), T(" junto a 'Bloqueado temporalmente' para Ubicación.")],
        [T("Recarga la página y haz clic en "), B("Reintentar"), T(".")]
      ]
    };

    var primary = matrix[key];
    if (primary) return primary;

    var osFallbacks = {
      android: [
        [T("Abre los "), B("Ajustes"), T(" de tu navegador o del sistema.")],
        [T("Busca "), B("Permisos"), T(" o "), B("Ubicación"), T(" y permite el acceso para este sitio.")],
        [T("Recarga la página y toca "), B("Reintentar"), T(".")]
      ],
      ios: [
        [T("Abre "), B("Ajustes"), T(" del iPhone/iPad.")],
        [T("Entra en "), B("Privacidad y seguridad"), T(" » "), B("Localización"), T(".")],
        [T("Busca tu navegador y elige "), B("Permitir"), T(".")],
        [T("Recarga y toca "), B("Reintentar"), T(".")]
      ]
    };
    if (osFallbacks[platform.os]) return osFallbacks[platform.os];

    return [
      [T("Abre la configuración de permisos de tu navegador.")],
      [T("Permite el acceso a la ubicación para este sitio.")],
      [T("Recarga la página y vuelve a intentarlo.")]
    ];
  }

  // ---------- Storage helpers ---------------------------------------------

  function readPreference() {
    try { return window.localStorage.getItem(STORAGE_KEY) || null; }
    catch (e) { return null; }
  }
  function writePreference(value) {
    try {
      if (value) window.localStorage.setItem(STORAGE_KEY, value);
      else window.localStorage.removeItem(STORAGE_KEY);
    } catch (e) { /* no-op */ }
  }
  function wasNaggedThisSession() {
    try { return window.sessionStorage.getItem(SESSION_NAG_KEY) === "1"; }
    catch (e) { return false; }
  }
  function markNaggedThisSession() {
    try { window.sessionStorage.setItem(SESSION_NAG_KEY, "1"); }
    catch (e) { /* no-op */ }
  }

  // ---------- DOM helpers --------------------------------------------------

  function clearChildren(node) {
    while (node && node.firstChild) node.removeChild(node.firstChild);
  }
  function appendStepSegments(li, segments) {
    for (var i = 0; i < segments.length; i++) {
      var seg = segments[i];
      if (seg[0] === "bold") {
        var strong = document.createElement("strong");
        strong.textContent = seg[1];
        li.appendChild(strong);
      } else {
        li.appendChild(document.createTextNode(seg[1]));
      }
    }
  }

  function setStatePanel(modal, state) {
    var panels = modal.querySelectorAll("[data-gate-state]");
    for (var i = 0; i < panels.length; i++) {
      var matches = panels[i].getAttribute("data-gate-state") === state;
      panels[i].toggleAttribute("hidden", !matches);
    }
  }
  function fillReason(modal, reason) {
    var nodes = modal.querySelectorAll("[data-gate-reason]");
    for (var i = 0; i < nodes.length; i++) nodes[i].textContent = reason || DEFAULT_REASON;
  }
  function renderInstructions(modal, platform) {
    var list = modal.querySelector("[data-gate-instructions]");
    if (!list) return;
    clearChildren(list);
    var steps = getReactivationInstructions(platform);
    for (var i = 0; i < steps.length; i++) {
      var li = document.createElement("li");
      appendStepSegments(li, steps[i]);
      list.appendChild(li);
    }
    var device = modal.querySelector("[data-gate-device]");
    if (device) {
      var label = ({
        ios: "iPhone / iPad", android: "Android",
        macos: "Mac", windows: "Windows", linux: "Linux"
      })[platform.os] || "Tu dispositivo";
      var browser = ({
        chrome: "Chrome", safari: "Safari", firefox: "Firefox", edge: "Edge"
      })[platform.browser] || "navegador";
      device.textContent = label + " · " + browser;
    }
  }

  // ---------- Banner ------------------------------------------------------
  // Eliminamos el banner persistente — el modal del gate es suficiente y
  // tener dos avisos a la vez resulta confuso. Dejamos las funciones como
  // no-ops para no romper llamadas existentes en el resto del código.

  function ensureBanner() {
    // Si quedó un banner antiguo en el DOM (cache), lo limpiamos.
    var stale = document.getElementById("cm-geo-gate-banner");
    if (stale && stale.parentNode) stale.parentNode.removeChild(stale);
    return null;
  }
  function showBanner(/* banner, text, onActivate */) { /* deshabilitado */ }
  function hideBanner(/* banner */) { /* deshabilitado */ }

  // ---------- HTTPS check --------------------------------------------------

  function isSecureContext() {
    if (typeof window.isSecureContext === "boolean") return window.isSecureContext;
    return /^https:$/.test(location.protocol)
        || location.hostname === "localhost"
        || location.hostname === "127.0.0.1";
  }

  // ---------- Permissions API ---------------------------------------------

  function queryPermission(callback, onChangeExtra) {
    if (!navigator.permissions || !navigator.permissions.query) {
      callback(null); return;
    }
    try {
      navigator.permissions.query({ name: "geolocation" }).then(function (result) {
        callback(result.state);
        result.onchange = function () {
          if (result.state === "granted") writePreference("granted");
          else if (result.state === "denied") writePreference("denied");
          else writePreference(null);
          if (onChangeExtra) onChangeExtra(result.state);
        };
      }).catch(function () { callback(null); });
    } catch (e) { callback(null); }
  }

  function requestPosition(onSuccess, onError) {
    if (!navigator.geolocation) { onError({ code: "unsupported" }); return; }
    navigator.geolocation.getCurrentPosition(
      function (position) { writePreference("granted"); onSuccess(position); },
      function (err) {
        if (err && err.code === 1) writePreference("denied");
        onError(err);
      },
      { enableHighAccuracy: true, timeout: GEO_TIMEOUT_MS, maximumAge: GEO_MAX_AGE_MS }
    );
  }

  // ---------- Bootstrap modal helpers -------------------------------------

  function getBsModal(modal) {
    if (!modal || !window.bootstrap || !window.bootstrap.Modal) return null;
    return window.bootstrap.Modal.getOrCreateInstance(modal, {
      backdrop: "static",
      keyboard: false
    });
  }
  function showModal(modal) { var bs = getBsModal(modal); if (bs) bs.show(); }
  function hideModal(modal) { var bs = getBsModal(modal); if (bs) bs.hide(); }

  // ---------- Controlador -------------------------------------------------

  function GateController(modal, banner) {
    this.modal = modal;
    this.banner = banner;
    this.platform = detectPlatform();
    this._wireModal();
    this._watchPermissionChanges();
  }

  // Si otra parte de la app pide la ubicación con la API nativa (p. ej. el
  // botón "Mi ubicación" propio del mapa), el navegador dispara el cambio
  // de permiso. Aprovechamos el evento para limpiar nuestro banner.
  GateController.prototype._watchPermissionChanges = function () {
    var self = this;
    queryPermission(
      function (state) {
        if (state === "granted") hideBanner(self.banner);
      },
      function (newState) {
        if (newState === "granted") {
          hideBanner(self.banner);
          if (self.modal && self.modal.classList.contains("show")) {
            hideModal(self.modal);
          }
        }
      }
    );
  };

  GateController.prototype._wireModal = function () {
    var self = this;
    var modal = this.modal;
    if (!modal) return;
    var closeBtns = modal.querySelectorAll("[data-gate-close]");
    for (var i = 0; i < closeBtns.length; i++) {
      closeBtns[i].addEventListener("click", function () { self._handleSkip(); });
    }
    var activateBtn = modal.querySelector("[data-gate-activate]");
    if (activateBtn) activateBtn.addEventListener("click", function () { self._activate(); });
    var retryBtn = modal.querySelector("[data-gate-retry]");
    if (retryBtn) retryBtn.addEventListener("click", function () { self._activate(); });
    // The shared sheet modal renders a Bootstrap close button with
    // ``data-bs-dismiss="modal"`` that does NOT pass through ``data-gate-close``.
    // Without this hook, dismissing via the X (or backdrop click / Escape)
    // would close the modal without persisting the "skipped" preference, so
    // the modal would re-open on every map visit. Hook the Bootstrap event
    // so every dismissal path behaves the same as "Continuar sin ubicación".
    modal.addEventListener("hidden.bs.modal", function () {
      var prev = readPreference();
      if (prev !== "granted" && prev !== "denied") writePreference("skipped");
      markNaggedThisSession();
    });
  };

  GateController.prototype._handleSkip = function () {
    var prev = readPreference();
    if (prev !== "granted" && prev !== "denied") writePreference("skipped");
    markNaggedThisSession();
    hideModal(this.modal);
    if (this._onSkipped) this._onSkipped();
    this._softReminder();
  };

  GateController.prototype._activate = function () {
    var self = this;

    // HTTPS y soporte: si fallan, mostramos panel apropiado y abrimos modal.
    if (!isSecureContext()) {
      setStatePanel(this.modal, "insecure");
      showModal(this.modal);
      return;
    }
    if (!navigator.geolocation) {
      setStatePanel(this.modal, "unsupported");
      showModal(this.modal);
      return;
    }

    setStatePanel(this.modal, "loading");
    showModal(this.modal); // visible para que se vea feedback aunque venga del banner

    requestPosition(
      function (position) {
        hideModal(self.modal);
        hideBanner(self.banner);
        if (self._onGranted) self._onGranted(position);
      },
      function (err) {
        if (err && err.code === "unsupported") {
          setStatePanel(self.modal, "unsupported");
          return;
        }
        if (err && err.code === 1) {
          setStatePanel(self.modal, "denied");
          renderInstructions(self.modal, self.platform);
          return;
        }
        setStatePanel(self.modal, "timeout");
      }
    );
  };

  GateController.prototype._softReminder = function () {
    var self = this;
    // El botón "Activar" del banner dispara _activate directo: la heurística
    // anti-nag de require() asumiría que ya preguntamos esta sesión y no
    // haría nada. El click es consentimiento explícito, así que vamos
    // directo al permiso.
    showBanner(this.banner, this._currentReason, function () {
      self._activate();
    });
  };

  GateController.prototype.require = function (options) {
    options = options || {};
    var self = this;
    this._currentMode = options.mode === "hard" ? "hard" : "soft";
    this._currentReason = options.reason || DEFAULT_REASON;
    this._onGranted = options.onGranted || function () {};
    this._onDenied  = options.onDenied  || function () {};
    this._onSkipped = options.onSkipped || function () {};

    if (!this.modal) { this._onSkipped(); return; }

    fillReason(this.modal, this._currentReason);
    renderInstructions(this.modal, this.platform);

    if (!isSecureContext()) {
      setStatePanel(this.modal, "insecure");
      showModal(this.modal);
      return;
    }
    if (!navigator.geolocation) {
      setStatePanel(this.modal, "unsupported");
      showModal(this.modal);
      return;
    }

    queryPermission(function (state) {
      var prev = readPreference();
      if (state === "granted" || prev === "granted") {
        // Permiso ya concedido: persistimos para que sesiones siguientes
        // tampoco abran el modal, y limpiamos cualquier banner pegado.
        writePreference("granted");
        hideBanner(self.banner);
        requestPosition(
          function (pos) {
            hideBanner(self.banner);
            self._onGranted(pos);
          },
          function (err) {
            // El permiso ya estaba activo: NO mostrar el modal "Activa
            // tu ubicación", el usuario ya activó. Solo notificamos al
            // page para que muestre su propio mensaje (GPS lento, etc.).
            if (err && err.code === 1) {
              // Permiso revocado entre la query y la llamada → modal denied.
              writePreference("denied");
              setStatePanel(self.modal, "denied");
              renderInstructions(self.modal, self.platform);
              showModal(self.modal);
              return;
            }
            if (self._onDenied) self._onDenied(err);
          }
        );
        return;
      }
      if (state === "denied") {
        setStatePanel(self.modal, "denied");
        renderInstructions(self.modal, self.platform);
        showModal(self.modal);
        return;
      }
      if (self._currentMode === "soft" && (prev === "skipped" || prev === "denied") && wasNaggedThisSession()) {
        self._softReminder();
        self._onSkipped();
        return;
      }
      self._showPrompt(prev, state);
    });
  };

  GateController.prototype._showPrompt = function (prev, state) {
    if (state === "denied" || prev === "denied") {
      setStatePanel(this.modal, "denied");
      renderInstructions(this.modal, this.platform);
    } else {
      setStatePanel(this.modal, "prompt");
    }
    showModal(this.modal);
  };

  // Hooks para que código externo (p. ej. el botón "Mi ubicación" del mapa
  // que sigue usando navigator.geolocation directo) avise al gate cuando ya
  // tiene la ubicación o cuando el navegador la negó.
  GateController.prototype.notifyGranted = function () {
    writePreference("granted");
    hideBanner(this.banner);
    if (this.modal && this.modal.classList.contains("show")) {
      hideModal(this.modal);
    }
  };

  GateController.prototype.notifyDenied = function () {
    writePreference("denied");
    setStatePanel(this.modal, "denied");
    renderInstructions(this.modal, this.platform);
    showModal(this.modal);
  };

  GateController.prototype.getCurrentPosition = function (options) {
    var self = this;
    if (!isSecureContext()) {
      if (this.modal) {
        setStatePanel(this.modal, "insecure");
        showModal(this.modal);
      }
      if (options && options.onDenied) options.onDenied({ code: "insecure" });
      return;
    }
    requestPosition(
      function (pos) { options && options.onGranted && options.onGranted(pos); },
      function (err) {
        if (self.modal && err && err.code === 1) {
          setStatePanel(self.modal, "denied");
          renderInstructions(self.modal, self.platform);
          showModal(self.modal);
        }
        options && options.onDenied && options.onDenied(err);
      }
    );
  };

  // ---------- Bootstrap ---------------------------------------------------

  function init() {
    var modal = document.getElementById("cm-geo-gate-modal");
    var banner = ensureBanner();
    var controller = new GateController(modal, banner);
    window.GeolocationGate = {
      require: function (opts) { controller.require(opts); },
      getCurrentPosition: function (opts) { controller.getCurrentPosition(opts); },
      detectPlatform: detectPlatform,
      isSecureContext: isSecureContext
    };
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

})(window, document);
