/* Calendario de agenda política
 *
 * Bootstraps a FullCalendar instance over `#agenda-calendar`, fed by the
 * `data-data-url` JSON endpoint. Filter selects above the calendar trigger
 * a refetch; clicking an event opens a modal with the popup HTML returned
 * by `data-popup-url`.
 */
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", initAgendaCalendar);

  function setHtml(node, html) {
    // Content originates from our own Django templates with autoescape on, so
    // user-supplied fields are HTML-escaped before reaching the browser.
    node.innerHTML = html;
  }

  function initAgendaCalendar() {
    var el = document.getElementById("agenda-calendar");
    if (!el || typeof FullCalendar === "undefined") {
      return;
    }

    var dataUrl = el.dataset.dataUrl;
    var popupUrlTemplate = el.dataset.popupUrl || "";
    var locale = el.dataset.locale || "es";

    var modalEl = document.getElementById("agenda-event-modal");
    var modalBody = modalEl ? modalEl.querySelector("[data-modal-body]") : null;
    var modalTitle = modalEl ? modalEl.querySelector("[data-modal-title]") : null;
    var modalLink = modalEl ? modalEl.querySelector("[data-detail-link]") : null;
    var modal = modalEl && window.bootstrap && bootstrap.Modal
      ? bootstrap.Modal.getOrCreateInstance(modalEl)
      : null;

    var filterForm = document.getElementById("agenda-calendar-filters");
    var filterPanel = document.getElementById("agenda-calendar-panel");
    var filterTrigger = document.querySelector(".agenda-calendar-filter-trigger");
    var filterCount = document.getElementById("agenda-calendar-filter-count");
    var resetBtn = document.getElementById("agenda-calendar-reset");
    var resetBtnInline = document.getElementById("agenda-calendar-reset-inline");

    // Mobile screens cannot fit the month grid; the day cells get so narrow
    // that event titles render as 1-2 chars. Default to the list view there.
    var isMobile = window.matchMedia && window.matchMedia("(max-width: 767.98px)").matches;
    var calendar = new FullCalendar.Calendar(el, {
      locale: locale,
      initialView: isMobile ? "listMonth" : "dayGridMonth",
      firstDay: 1,
      headerToolbar: isMobile
        ? { left: "prev,next today", center: "title", right: "listMonth,dayGridMonth" }
        : { left: "prev,next today", center: "title", right: "dayGridMonth,timeGridWeek,timeGridDay,listMonth" },
      buttonText: {
        today: "Hoy",
        month: "Mes",
        week: "Semana",
        day: "Día",
        list: "Lista",
      },
      nowIndicator: true,
      navLinks: true,
      height: "auto",
      events: function (info, success, failure) {
        var params = new URLSearchParams();
        params.set("start", info.startStr);
        params.set("end", info.endStr);
        appendActiveFilters(params);
        fetch(dataUrl + "?" + params.toString(), {
          headers: { Accept: "application/json" },
          credentials: "same-origin",
        })
          .then(function (res) {
            if (!res.ok) throw new Error("HTTP " + res.status);
            return res.json();
          })
          .then(success)
          .catch(failure);
      },
      eventClick: function (info) {
        info.jsEvent.preventDefault();
        var popupUrl = (info.event.extendedProps && info.event.extendedProps.popup_url)
          || popupUrlTemplate.replace(/\/0\/?$/, "/" + info.event.id + "/");
        openEventModal(popupUrl, info.event);
      },
      eventClassNames: function (arg) {
        var props = arg.event.extendedProps || {};
        return props.is_public === false ? ["agenda-calendar__event--private"] : [];
      },
      eventDidMount: function (arg) {
        var props = arg.event.extendedProps || {};
        if (props.is_public !== false) return;
        var titleNode = arg.el.querySelector(".fc-event-title, .fc-list-event-title");
        if (!titleNode || titleNode.querySelector(".agenda-calendar__lock")) return;
        var icon = document.createElement("i");
        icon.setAttribute("data-lucide", "lock");
        icon.className = "fs-8 me-1 agenda-calendar__lock";
        icon.setAttribute("aria-hidden", "true");
        var label = document.createElement("span");
        label.className = "visually-hidden";
        label.textContent = "Evento privado: ";
        titleNode.prepend(icon);
        titleNode.prepend(label);
        arg.el.setAttribute("title", "Evento privado");
        if (window.cmRenderIcons) window.cmRenderIcons();
      },
    });

    calendar.render();

    function appendActiveFilters(params) {
      if (!filterForm) return;
      Array.prototype.forEach.call(filterForm.elements, function (input) {
        if (!input.name || !input.value) return;
        params.set(input.name, input.value);
      });
    }

    function refetchAndUpdateCount() {
      calendar.refetchEvents();
      if (!filterForm) return;
      var active = 0;
      Array.prototype.forEach.call(filterForm.elements, function (input) {
        if (input.name && input.value) active += 1;
      });
      if (filterCount) {
        if (active) {
          filterCount.textContent = String(active);
          filterCount.hidden = false;
        } else {
          filterCount.hidden = true;
        }
      }
      if (resetBtnInline) {
        // Hide entirely when no filters are applied to keep the toolbar clean.
        resetBtnInline.classList.toggle("d-none", active === 0);
      }
    }

    if (filterForm) {
      filterForm.addEventListener("change", refetchAndUpdateCount);
    }
    function clearFilters() {
      if (!filterForm) return;
      Array.prototype.forEach.call(filterForm.elements, function (input) {
        if (input.tagName === "SELECT" || input.tagName === "INPUT") {
          input.value = "";
        }
      });
      refetchAndUpdateCount();
    }
    if (resetBtn && filterForm) {
      resetBtn.addEventListener("click", clearFilters);
    }
    if (resetBtnInline && filterForm) {
      resetBtnInline.addEventListener("click", clearFilters);
    }
    // Initial sync — make sure inline reset starts hidden when no filters set.
    refetchAndUpdateCount();
    if (filterTrigger && filterPanel) {
      filterTrigger.addEventListener("click", function () {
        var isHidden = filterPanel.hasAttribute("hidden");
        if (isHidden) {
          filterPanel.removeAttribute("hidden");
          filterTrigger.setAttribute("aria-expanded", "true");
        } else {
          filterPanel.setAttribute("hidden", "");
          filterTrigger.setAttribute("aria-expanded", "false");
        }
      });
    }

    var SPINNER_HTML =
      '<div class="text-center text-muted py-10">' +
      '  <div class="spinner-border" role="status"><span class="visually-hidden">Cargando&hellip;</span></div>' +
      '  <div class="mt-3">Cargando&hellip;</div>' +
      '</div>';

    function openEventModal(url, event) {
      if (!modalEl || !modalBody) {
        window.location.href = event.url || "#";
        return;
      }
      setHtml(modalBody, SPINNER_HTML);
      if (modalTitle) modalTitle.textContent = event.title || "Evento";
      if (modalLink) modalLink.setAttribute("href", "#");
      if (modal) modal.show();

      fetch(url, {
        headers: {
          Accept: "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
        credentials: "same-origin",
      })
        .then(function (res) {
          if (!res.ok) throw new Error("HTTP " + res.status);
          return res.json();
        })
        .then(function (data) {
          setHtml(modalBody, data.html || "");
          if (modalTitle && data.title) modalTitle.textContent = data.title;
          if (modalLink && data.url) modalLink.setAttribute("href", data.url);
        })
        .catch(function () {
          setHtml(
            modalBody,
            '<div class="alert alert-danger">No se pudo cargar el evento.</div>'
          );
        });
    }
  }
})();
