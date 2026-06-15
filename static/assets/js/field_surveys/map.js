/**
 * Field-surveys map — thin app config over window.CmMapKit.
 *
 * Owns only the app-specific bits: the two pin styles (visit teardrop +
 * competitor pointer), the donut/competitor cluster icons, the create
 * presets, and the data contract of /field_surveys/map_data/
 * ({visits, competitor_ads, truncated, total, returned}). All generic
 * plumbing (map init, basemaps, panel, filters, geolocation, truncation,
 * empty state) lives in static/assets/js/core/map_kit.js.
 */
(function (window, document) {
  "use strict";

  var kit = window.CmMapKit;
  if (!kit) {
    if (window.console && window.console.error) {
      window.console.error("CmMapKit missing: field-survey map cannot start");
    }
    return;
  }

  var ICON_ALIASES = {
    "billboard": "flag",
    "sticker":   "tag",
    "like":      "thumbs-up",
    "dislike":   "thumbs-down",
    "question-2":"help-circle",
    "home-2":    "home",
    "geolocation":"map-pin",
    "cross":     "x"
  };

  // Visual config per support state. Drives icon, color, semantic class.
  // The fallback ("") is used when a survey has not been classified yet.
  var SUPPORT_STATES = {
    "APOYA":      { icon: "thumbs-up",   color: "#50cd89", cls: "is-apoya",      label: "Apoya" },
    "INDECISO":   { icon: "help-circle", color: "#ffc700", cls: "is-indeciso",   label: "Indeciso" },
    "NO_APOYA":   { icon: "thumbs-down", color: "#f1416c", cls: "is-noapoya",    label: "No apoya" },
    "NO_ATENDIO": { icon: "home",        color: "#7e8299", cls: "is-noatendio",  label: "No atendió" },
    "":           { icon: "map-pin",     color: "#3e97ff", cls: "is-pending",    label: "Sin clasificar" }
  };

  var ADVERTISING_BADGES = {
    "ACEPTA":  { icon: "check", cls: "fs-pin__badge--accept", label: "Acepta publicidad" },
    "RECHAZA": { icon: "x",     cls: "fs-pin__badge--reject", label: "Rechaza publicidad" }
  };

  // Order matters: drives the visual sequence of donut segments.
  var CLUSTER_SEGMENTS = ["APOYA", "INDECISO", "NO_APOYA", "NO_ATENDIO", ""];

  function iconName(icon) {
    return kit.safeIconName(icon, ICON_ALIASES, "circle");
  }

  function visitPin(item) {
    var state = SUPPORT_STATES[item.support_code || ""] || SUPPORT_STATES[""];
    var color = kit.safeColor(item.color, state.color);
    var icon = iconName(state.icon);

    var badgeHtml = "";
    var badge = ADVERTISING_BADGES[item.advertising_code || ""];
    if (badge) {
      badgeHtml =
        '<span class="fs-pin__badge ' + badge.cls + '" title="' + badge.label + '">' +
          '<i data-lucide="' + badge.icon + '"></i>' +
        '</span>';
    }

    return window.L.divIcon({
      className: "fs-pin fs-pin--visit " + state.cls,
      html:
        '<span class="fs-pin__shape" style="background:' + color + '">' +
          '<i data-lucide="' + icon + '"></i>' +
        '</span>' +
        '<span class="fs-pin__tail" style="border-top-color:' + color + '"></span>' +
        badgeHtml,
      iconSize: [40, 50],
      iconAnchor: [20, 48],
      popupAnchor: [0, -46]
    });
  }

  // Competitor pins show the party acronym (max 3 letters/numbers) inside a
  // pointed pin so the tip marks the exact detection spot.
  function competitorPin(item) {
    var color = kit.safeColor(item.color, "#d9214e");
    var acronym = String(item.acronym || "")
      .replace(/[^A-Za-z0-9]/g, "")
      .slice(0, 3)
      .toUpperCase();
    return window.L.divIcon({
      className: "fs-pin fs-pin--competitor",
      html:
        '<span class="fs-pin__pointer" style="border-color:' + color + '">' +
          '<span class="fs-pin__pointer-label" style="color:' + color + '">' + acronym + '</span>' +
        '</span>',
      iconSize: [44, 50],
      iconAnchor: [22, 47],
      popupAnchor: [0, -47]
    });
  }

  function buildClusterIcon(cluster) {
    var leaves = cluster.getAllChildMarkers();
    var counts = { "APOYA": 0, "INDECISO": 0, "NO_APOYA": 0, "NO_ATENDIO": 0, "": 0 };
    leaves.forEach(function (marker) {
      var code = marker.options.fsSupportCode;
      if (code === undefined || counts[code] === undefined) {
        counts[""] += 1;
      } else {
        counts[code] += 1;
      }
    });

    var total = leaves.length;
    var size = total < 10 ? 40 : total < 50 ? 48 : 56;

    var stops = [];
    var degSoFar = 0;
    CLUSTER_SEGMENTS.forEach(function (code) {
      var count = counts[code];
      if (!count) {
        return;
      }
      var degSpan = (count / total) * 360;
      var color = SUPPORT_STATES[code].color;
      stops.push(color + " " + degSoFar.toFixed(2) + "deg " + (degSoFar + degSpan).toFixed(2) + "deg");
      degSoFar += degSpan;
    });

    var background = stops.length
      ? "conic-gradient(" + stops.join(", ") + ")"
      : SUPPORT_STATES[""].color;

    return window.L.divIcon({
      html:
        '<span class="fs-cluster" style="background:' + background + '">' +
          '<span class="fs-cluster__inner">' + total + '</span>' +
        '</span>',
      className: "fs-cluster-wrap",
      iconSize: [size, size]
    });
  }

  // Competitor cluster: solid red bubble with a flag, kept visually distinct
  // from the visit donut so the two layers don't get confused at low zoom.
  function buildCompetitorClusterIcon(cluster) {
    var total = cluster.getChildCount();
    var size = total < 10 ? 40 : total < 50 ? 48 : 56;
    return window.L.divIcon({
      html:
        '<span class="fs-cluster fs-cluster--competitor">' +
          '<span class="fs-cluster__inner fs-cluster__inner--competitor">' +
            '<i data-lucide="flag"></i>' +
            '<span class="fs-cluster__count">' + total + '</span>' +
          '</span>' +
        '</span>',
      className: "fs-cluster-wrap",
      iconSize: [size, size]
    });
  }

  var CREATE_PRESETS = {
    visit: {
      title: "Nueva visita",
      subtitle: "Completa los datos de la visita",
      icon: "home-2",
      bgClass: "bg-light-primary text-primary"
    },
    competitor: {
      title: "Nueva detección de competencia",
      subtitle: "Reporta publicidad de la oposición",
      icon: "flag",
      bgClass: "bg-light-danger text-danger"
    }
  };

  function applyCreatePreset(action, createModalEl) {
    var preset = CREATE_PRESETS[action] || CREATE_PRESETS.visit;
    if (!createModalEl) {
      return;
    }
    var titleEl = createModalEl.querySelector("[data-create-title]");
    var subtitleEl = createModalEl.querySelector("[data-create-subtitle]");
    var iconEl = createModalEl.querySelector("[data-create-icon]");
    var iconBg = createModalEl.querySelector("[data-create-icon-bg]");
    if (titleEl) titleEl.textContent = preset.title;
    if (subtitleEl) subtitleEl.textContent = preset.subtitle;
    if (iconEl) {
      var name = iconName(preset.icon);
      if (iconEl.tagName && iconEl.tagName.toLowerCase() === "svg") {
        var replacement = document.createElement("i");
        replacement.setAttribute("data-create-icon", "");
        replacement.setAttribute("data-lucide", name);
        replacement.setAttribute("class", "fs-2");
        replacement.setAttribute("aria-hidden", "true");
        iconEl.replaceWith(replacement);
      } else {
        iconEl.setAttribute("data-lucide", name);
        iconEl.setAttribute("class", "fs-2");
      }
      if (window.cmRenderIcons) window.cmRenderIcons();
    }
    if (iconBg) iconBg.className = "symbol-label " + preset.bgClass;
  }

  var LATLNG_PARAMS = { lat: "latitude", lng: "longitude" };

  function bootMap() {
    var state = {
      pinsLayer: null,
      competitorLayer: null,
      detailModalEl: document.getElementById("field-survey-detail-modal"),
      createModalEl: document.getElementById("field-survey-create-modal"),
      updateModalEl: document.getElementById("field-survey-update-modal"),
      deleteModalEl: document.getElementById("field-survey-delete-modal"),
      chooseModalEl: document.getElementById("field-survey-choose-modal"),
      createUrl: "",
      createCompetitorUrl: ""
    };

    function openCreate(action, latlng, mapState, ctx) {
      var targetUrl = action === "competitor" ? state.createCompetitorUrl : state.createUrl;
      if (!targetUrl) {
        return;
      }
      applyCreatePreset(action, state.createModalEl);
      kit.openCreateModal({
        modalEl: state.createModalEl,
        createUrl: targetUrl,
        latlng: latlng,
        mapState: mapState,
        onSaved: function () { ctx.load(); },
        paramNames: LATLNG_PARAMS,
        saveErrorText: action === "competitor"
          ? "No se pudo guardar la detección de competencia."
          : "No se pudo guardar el levantamiento."
      });
    }

    function onMapClick(latlng, ctx) {
      var mapState = ctx.getMapState();
      var chooseModalEl = state.chooseModalEl;
      if (!chooseModalEl || !window.bootstrap) {
        if (state.createUrl) {
          openCreate("visit", latlng, mapState, ctx);
        }
        return;
      }
      var coordsEl = chooseModalEl.querySelector("[data-choose-coords]");
      if (coordsEl) {
        coordsEl.textContent =
          "En " + latlng.lat.toFixed(6) + " / " + latlng.lng.toFixed(6);
      }
      var modal = window.bootstrap.Modal.getOrCreateInstance(chooseModalEl);
      function pick(event) {
        var action = event.currentTarget.getAttribute("data-choose-action");
        modal.hide();
        openCreate(action, latlng, mapState, ctx);
      }
      // Re-bind on each open so we don't accumulate stale closures.
      Array.prototype.forEach.call(
        chooseModalEl.querySelectorAll("[data-choose-action]"),
        function (btn) { btn.replaceWith(btn.cloneNode(true)); }
      );
      Array.prototype.forEach.call(
        chooseModalEl.querySelectorAll("[data-choose-action]"),
        function (btn) { btn.addEventListener("click", pick); }
      );
      modal.show();
    }

    function wireDetailModal(ctx) {
      var modalEl = state.detailModalEl;
      if (!modalEl) {
        return;
      }
      var editLinkEl = modalEl.querySelector("[data-edit-link]");
      var deleteLinkEl = modalEl.querySelector("[data-delete-link]");
      if (editLinkEl) {
        editLinkEl.addEventListener("click", function (event) {
          event.preventDefault();
          var url = editLinkEl.dataset.actionUrl;
          if (!url) return;
          kit.openUpdateModal({
            modalEl: state.updateModalEl,
            detailModalEl: modalEl,
            updateUrl: url,
            label: modalEl.dataset.currentLabel || "",
            onSaved: function () { ctx.load(); }
          });
        });
      }
      if (deleteLinkEl) {
        deleteLinkEl.addEventListener("click", function (event) {
          event.preventDefault();
          var url = deleteLinkEl.dataset.actionUrl;
          if (!url) return;
          kit.openDeleteModal({
            modalEl: state.deleteModalEl,
            detailModalEl: modalEl,
            deleteUrl: url,
            label: modalEl.dataset.currentLabel || "",
            onDeleted: function () { ctx.load(); }
          });
        });
      }

      // Workflow transitions (workflows.js) used to reload the whole page.
      // While our detail modal is open we re-fetch the body instead so the
      // user stays in place and sees the new state.
      modalEl.addEventListener("workflow:transitioned", function (event) {
        event.preventDefault();
        var detailUrl = modalEl.dataset.currentDetailUrl;
        var bodyEl = modalEl.querySelector("[data-modal-body]");
        if (!detailUrl || !bodyEl) {
          ctx.load();
          return;
        }
        kit.setHtml(bodyEl, kit.loadingHtml("Actualizando..."));
        fetch(detailUrl, {
          headers: { "X-Requested-With": "XMLHttpRequest" },
          credentials: "same-origin"
        })
          .then(function (r) { return r.text(); })
          .then(function (html) {
            var detailHtml = kit.detailHtmlFromPage(html);
            if (!detailHtml) throw new Error("Empty detail content");
            kit.setHtml(bodyEl, detailHtml);
            kit.initDynamicContent(bodyEl);
            ctx.load();
          })
          .catch(function () {
            kit.setHtml(bodyEl, '<div class="alert alert-danger">No se pudo actualizar el detalle.</div>');
          });
      });
    }

    kit.createMapPage({
      mapId: "field-survey-map",
      shellSelector: ".field-survey-map-shell",
      panelId: "field-survey-map-panel",
      counterId: "field-survey-map-count",
      filterCounterId: "field-survey-filter-count",
      filterTriggerSelector: ".field-survey-map-filter-trigger",
      resetId: "field-survey-map-reset",
      myLocationId: "field-survey-my-location",
      filtersId: "field-survey-map-filters",
      truncationId: "field-survey-map-truncated",
      countLabels: { singular: "visita", plural: "visitas" },
      createGateMeters: 100,
      loadErrorLog: "Field survey map data load failed",

      setup: function (ctx) {
        state.createUrl = ctx.el.dataset.createUrl || "";
        state.createCompetitorUrl = ctx.el.dataset.createCompetitorUrl || "";
        state.pinsLayer = ctx.addClusterLayer({ iconCreateFunction: buildClusterIcon });
        state.competitorLayer = ctx.addClusterLayer({ iconCreateFunction: buildCompetitorClusterIcon });
        wireDetailModal(ctx);
        kit.bindLegend({
          legendEl: document.getElementById("field-survey-map-legend"),
          toggleEl: document.getElementById("field-survey-map-legend-toggle"),
          storageKey: "fs:map:legendOpen"
        });
      },

      clickEnabled: function () {
        return !!(state.createUrl || state.createCompetitorUrl);
      },

      onMapClick: onMapClick,

      renderData: function (data, ctx) {
        var bounds = [];
        var visits = data.visits || [];
        var competitorAds = data.competitor_ads || [];

        visits.forEach(function (item) {
          var supportState = SUPPORT_STATES[item.support_code || ""] || SUPPORT_STATES[""];
          var tooltipParts = [item.label, supportState.label];
          if (item.advertising_label) {
            tooltipParts.push(item.advertising_label);
          }
          var marker = window.L.marker([item.lat, item.lng], {
            icon: visitPin(item),
            bubblingMouseEvents: false,
            fsSupportCode: item.support_code || ""
          })
            .bindTooltip(tooltipParts.join(" · "), { direction: "top", offset: [0, -44] })
            .addTo(state.pinsLayer);
          marker.on("click", function () {
            kit.openDetailModal({
              modalEl: state.detailModalEl,
              item: item,
              fallbackTitle: "Levantamiento",
              markerKind: "survey",
              errorText: "No se pudo cargar la información del registro."
            });
          });
          bounds.push([item.lat, item.lng]);
        });

        competitorAds.forEach(function (item) {
          var marker = window.L.marker([item.lat, item.lng], {
            icon: competitorPin(item),
            bubblingMouseEvents: false
          })
            .bindTooltip(item.label + " · " + item.type_label, { direction: "top", offset: [0, -44] })
            .addTo(state.competitorLayer);
          marker.on("click", function () {
            kit.openDetailModal({
              modalEl: state.detailModalEl,
              item: item,
              fallbackTitle: "Detección de competencia",
              markerKind: "competitor",
              errorText: "No se pudo cargar la información del registro."
            });
          });
          bounds.push([item.lat, item.lng]);
        });

        return { count: visits.length, bounds: bounds };
      }
    });
  }

  kit.boot(bootMap);
})(window, document);
