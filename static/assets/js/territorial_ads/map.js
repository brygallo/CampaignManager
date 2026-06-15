/**
 * Territorial ads map — thin app config over window.CmMapKit.
 *
 * Owns only the app-specific bits: pin/cluster rendering, the data contract
 * of /publicidad-territorial/mapa/datos/ ({ads, truncated, total, returned})
 * and the choice → create/direct/refusal modal flows. All generic plumbing
 * lives in static/assets/js/core/map_kit.js.
 */
(function (window, document) {
  "use strict";

  var kit = window.CmMapKit;
  if (!kit) {
    if (window.console && window.console.error) {
      window.console.error("CmMapKit missing: territorial ads map cannot start");
    }
    return;
  }

  // Legacy / seeded icon names from the DB mapped to Lucide equivalents.
  // Stored values come from seed_territorial_ads_catalog (document, tag,
  // picture, tablet, flag, element-12) plus historical aliases.
  var ICON_ALIASES = {
    "billboard":  "flag",
    "sticker":    "tag",
    "document":   "file-text",
    "picture":    "image",
    "tablet":     "tablet",
    "element-12": "shapes",
    "flag":       "flag",
    "tag":        "tag"
  };

  // The map data endpoint keeps the historical offered_* parameter names for
  // the request/refusal create forms.
  var OFFERED_PARAMS = { lat: "offered_latitude", lng: "offered_longitude" };

  function pinIcon(color, icon, markerKind) {
    var iconName = kit.safeIconName(icon, ICON_ALIASES, "shapes");
    var pinColor = kit.safeColor(color, "#3388ff");
    var extraClass = "";
    if (markerKind === "refusal") {
      extraClass = " map-type-pin--refusal";
    } else if (markerKind === "unit") {
      extraClass = " map-type-pin--unit";
    } else if (markerKind === "ad") {
      // "ad" == solicitud: diamond shape, distinct from the round unit pins.
      extraClass = " map-type-pin--request";
    }
    return window.L.divIcon({
      className: "map-type-pin" + extraClass,
      html:
        '<span class="map-type-pin__inner" style="background:' + pinColor + ';color:#fff">' +
          '<i data-lucide="' + iconName + '" style="color:#fff"></i>' +
        '</span>',
      iconSize: [38, 38],
      iconAnchor: [19, 19],
      popupAnchor: [0, -18]
    });
  }

  function buildClusterIcon(cluster) {
    var n = cluster.getChildCount();
    var size = n < 10 ? 36 : n < 50 ? 44 : 52;
    return window.L.divIcon({
      html: '<span class="map-cluster-bubble">' + n + '</span>',
      className: "map-cluster",
      iconSize: [size, size]
    });
  }

  // Extra widget wiring for the request create/update forms.
  function initAdFormWidgets(scope) {
    if (window.CostTypeAmountToggle && window.CostTypeAmountToggle.init) {
      window.CostTypeAmountToggle.init(scope);
    }
  }

  // Direct-install form: only show the sizes belonging to the chosen type.
  function initDirectFormWidgets(scope) {
    var typeSelect = scope.querySelector("select[data-direct-type-select]");
    var sizeSelect = scope.querySelector("select[data-direct-size-select]");
    if (!typeSelect || !sizeSelect) {
      return;
    }

    function applySizeFilter() {
      var typeId = typeSelect.value;
      var selectionStillValid = false;
      var options = sizeSelect.querySelectorAll("option[data-type-id]");
      Array.prototype.forEach.call(options, function (option) {
        var matches = !typeId || option.getAttribute("data-type-id") === typeId;
        option.hidden = !matches;
        option.disabled = !matches;
        if (matches && option.value && option.value === sizeSelect.value) {
          selectionStillValid = true;
        }
      });
      if (sizeSelect.value && !selectionStillValid) {
        sizeSelect.value = "";
      }
    }

    // Native listener catches plain <select> changes. When the field is a
    // select2 widget the "change" event is dispatched through jQuery, which a
    // native addEventListener won't see — so also bind via jQuery if present.
    typeSelect.addEventListener("change", applySizeFilter);
    if (window.jQuery) {
      window.jQuery(typeSelect).on("change", applySizeFilter);
    }
    applySizeFilter();
  }

  function bootMap() {
    var state = {
      ctx: null,
      createUrl: "",
      refusalCreateUrl: "",
      directCreateUrl: "",
      pinsLayer: null,
      modalEl: document.getElementById("physical-ad-modal"),
      createModalEl: document.getElementById("physical-ad-create-modal"),
      updateModalEl: document.getElementById("physical-ad-update-modal"),
      deleteModalEl: document.getElementById("physical-ad-delete-modal"),
      refusalUpdateModalEl: document.getElementById("physical-ad-refusal-update-modal"),
      refusalModalEl: document.getElementById("physical-ad-refusal-modal"),
      directModalEl: document.getElementById("physical-ad-direct-modal"),
      choiceModalEl: document.getElementById("physical-ad-choice-modal")
    };

    function openAdCreate(latlng, mapState, ctx) {
      kit.openCreateModal({
        modalEl: state.createModalEl,
        createUrl: state.createUrl,
        latlng: latlng,
        mapState: mapState,
        onSaved: function () { ctx.load(); },
        paramNames: OFFERED_PARAMS,
        // Post to the prefixed create URL (data-create-url), NOT form.action:
        // under django-tenants subfolder routing request.get_full_path()
        // drops the /<tenant>/ prefix, so form.action would 404.
        initFormHook: initAdFormWidgets,
        saveErrorText: "No se pudo guardar el aviso."
      });
    }

    function openDirectCreate(latlng, mapState, ctx) {
      kit.openCreateModal({
        modalEl: state.directModalEl,
        createUrl: state.directCreateUrl,
        latlng: latlng,
        mapState: mapState,
        onSaved: function () { ctx.load(); },
        // The direct endpoint reads latitude/longitude and always answers
        // JSON, so no X-Map-Create header (and no full-page fallback).
        paramNames: { lat: "latitude", lng: "longitude" },
        headerName: null,
        allowRedirectFallback: false,
        bodySelector: "[data-direct-modal-body]",
        submitSelector: "[data-direct-submit]",
        formSelector: "[data-map-direct-form]",
        initFormHook: initDirectFormWidgets,
        saveErrorText: "No se pudo guardar la publicidad."
      });
    }

    function openRefusalCreate(latlng, mapState, ctx) {
      kit.openCreateModal({
        modalEl: state.refusalModalEl,
        createUrl: state.refusalCreateUrl,
        latlng: latlng,
        mapState: mapState,
        onSaved: function () { ctx.load(); },
        paramNames: OFFERED_PARAMS,
        allowRedirectFallback: false,
        bodySelector: "[data-refusal-modal-body]",
        submitSelector: "[data-refusal-submit]",
        formSelector: "[data-map-refusal-form]",
        initFormHook: initAdFormWidgets,
        saveErrorText: "No se pudo guardar el rechazo."
      });
    }

    function onMapClick(latlng, ctx) {
      var mapState = ctx.getMapState();
      var choiceModalEl = state.choiceModalEl;
      if (!choiceModalEl || !window.bootstrap) {
        if (state.createUrl) {
          openAdCreate(latlng, mapState, ctx);
        }
        return;
      }
      var modal = window.bootstrap.Modal.getOrCreateInstance(choiceModalEl);
      function pickHandler(event) {
        var choice = event.currentTarget.getAttribute("data-choice");
        modal.hide();
        window.setTimeout(function () {
          if (choice === "ad" && state.createUrl) {
            openAdCreate(latlng, mapState, ctx);
          } else if (choice === "direct" && state.directCreateUrl) {
            openDirectCreate(latlng, mapState, ctx);
          } else if (choice === "refusal" && state.refusalCreateUrl) {
            openRefusalCreate(latlng, mapState, ctx);
          }
        }, 200);
      }
      // Re-bind on each open so we don't accumulate stale closures.
      var buttons = choiceModalEl.querySelectorAll("[data-choice]");
      Array.prototype.forEach.call(buttons, function (btn) {
        btn.replaceWith(btn.cloneNode(true));
      });
      var fresh = choiceModalEl.querySelectorAll("[data-choice]");
      Array.prototype.forEach.call(fresh, function (btn) {
        btn.addEventListener("click", pickHandler);
      });
      modal.show();
    }

    function wireDetailModal(ctx) {
      var modalEl = state.modalEl;
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
          var isRefusal = modalEl.dataset.markerKind === "refusal";
          kit.openUpdateModal({
            modalEl: isRefusal ? state.refusalUpdateModalEl : state.updateModalEl,
            detailModalEl: modalEl,
            updateUrl: url,
            label: modalEl.dataset.currentLabel || "",
            onSaved: function () { ctx.load(); },
            bodySelector: isRefusal
              ? "[data-refusal-update-modal-body]"
              : "[data-update-modal-body]",
            submitSelector: isRefusal
              ? "[data-refusal-update-submit]"
              : "[data-update-submit]",
            titleSelector: isRefusal
              ? "[data-refusal-update-modal-title]"
              : "[data-update-modal-title]",
            formSelector: isRefusal
              ? "[data-map-refusal-update-form]"
              : "[data-map-update-form]",
            initFormHook: initAdFormWidgets
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
        var isRefusal = modalEl.dataset.markerKind === "refusal";
        fetch(detailUrl, {
          headers: { "X-Requested-With": "XMLHttpRequest" },
          credentials: "same-origin"
        })
          .then(function (r) { return isRefusal ? r.json() : r.text(); })
          .then(function (payload) {
            if (isRefusal) {
              kit.setHtml(bodyEl, (payload && payload.html) || "");
              kit.initDynamicContent(bodyEl);
            } else {
              var detailHtml = kit.detailHtmlFromPage(payload);
              if (!detailHtml) throw new Error("Empty detail content");
              kit.setHtml(bodyEl, detailHtml);
              kit.initDynamicContent(bodyEl);
            }
            ctx.load();
          })
          .catch(function () {
            kit.setHtml(bodyEl, '<div class="alert alert-danger">No se pudo actualizar el detalle.</div>');
          });
      });
    }

    kit.createMapPage({
      mapId: "physical-ad-map",
      shellSelector: ".physical-ad-map-shell",
      panelId: "physical-ad-map-panel",
      counterId: "physical-ad-map-count",
      filterCounterId: "physical-ad-filter-count",
      filterTriggerSelector: ".physical-ad-map-filter-trigger",
      resetId: "physical-ad-map-reset",
      myLocationId: "physical-ad-my-location",
      filtersId: "physical-ad-map-filters",
      truncationId: "physical-ad-map-truncated",
      countLabels: { singular: "ubicación", plural: "ubicaciones" },
      createGateMeters: 50,
      loadErrorLog: "Physical ad map data load failed",

      setup: function (ctx) {
        state.ctx = ctx;
        state.createUrl = ctx.el.dataset.createUrl || "";
        state.refusalCreateUrl = ctx.el.dataset.refusalCreateUrl || "";
        state.directCreateUrl = ctx.el.dataset.directCreateUrl || "";
        state.pinsLayer = ctx.addClusterLayer({ iconCreateFunction: buildClusterIcon });
        wireDetailModal(ctx);
        kit.bindLegend({
          legendEl: document.getElementById("physical-ad-map-legend"),
          toggleEl: document.getElementById("physical-ad-map-legend-toggle"),
          storageKey: "pa:map:legendOpen"
        });
      },

      clickEnabled: function () {
        return !!(state.createUrl || state.refusalCreateUrl || state.directCreateUrl);
      },

      onMapClick: onMapClick,

      renderData: function (data, ctx) {
        var bounds = [];
        var ads = data.ads || [];
        var kindFilter = document.getElementById("pa-map-filter-kind");
        var selectedKind = kindFilter ? kindFilter.value : "";
        if (selectedKind) {
          var markerKindByFilter = {
            request: "ad",
            publicity: "unit",
            refusal: "refusal"
          };
          ads = ads.filter(function (ad) {
            return ad.marker_kind === markerKindByFilter[selectedKind];
          });
        }
        ads.forEach(function (ad) {
          var marker = window.L.marker([ad.lat, ad.lng], {
            icon: pinIcon(ad.color, ad.type_icon, ad.marker_kind),
            bubblingMouseEvents: false
          })
            .bindTooltip(ad.label, { direction: "top", offset: [0, -34] })
            .addTo(state.pinsLayer);
          marker.on("click", function () {
            if (ad.marker_kind === "refusal") {
              // Refusals now open their full detail page in the modal, just
              // like requests/units. The backend points ad.url at the refusal
              // detail page (site:territorial_ads_advertisingrefusal_), and
              // wireDetailModal keys off markerKind "refusal" for the edit flow.
              kit.openDetailModal({
                modalEl: state.modalEl,
                item: ad,
                fallbackTitle: "Rechazo",
                markerKind: "refusal",
                errorText: "No se pudo cargar la información del rechazo."
              });
            } else {
              // "ad" (solicitud) and "unit" (publicidad instalada) both open
              // the request detail page inside the modal.
              kit.openDetailModal({
                modalEl: state.modalEl,
                item: ad,
                fallbackTitle: "Publicidad",
                markerKind: "ad",
                errorText: "No se pudo cargar la información del aviso."
              });
            }
          });
          bounds.push([ad.lat, ad.lng]);
        });
        return { count: ads.length, bounds: bounds };
      }
    });
  }

  kit.boot(bootMap);
})(window, document);
