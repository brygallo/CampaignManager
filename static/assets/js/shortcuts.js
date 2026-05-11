/**
 * Global keyboard shortcuts for CampaignManager.
 *
 *   ?           Show shortcut cheatsheet
 *   /           Focus the list search input (when on a list page)
 *   Ctrl+/      Focus sidebar quick-search
 *   Ctrl+K      Open command palette (if mounted)
 *   N           New record (if a "Nuevo" button is on screen)
 *   E           Edit current record (if "Editar" button is on screen)
 *   G + letter  Go to: g+h home, g+c campañas, g+a agenda, g+l levantamientos,
 *               g+p publicidad, g+u usuarios, g+m mapa de levantamientos
 *
 * Skipped while typing in inputs/textareas/contenteditable (except Ctrl+ shortcuts).
 */
(function () {
  const isTyping = (el) => !!el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.isContentEditable);

  const goRoutes = {
    h: "/",
    c: "/campaigns/campaign/listar/",
    a: "/political_agenda/politicalagendaevent/listar/",
    l: "/field_surveys/fieldsurvey/listar/",
    p: "/territorial_ads/physicaladvertisement/listar/",
    u: "/authentication/user/listar/",
    e: "/campaigns/election/listar/",
    m: "/field_surveys/map/",
  };

  let gPrimed = false;
  let gPrimedTimer = null;

  const navigate = (url) => { window.location.assign(url); };

  const showCheatsheet = () => {
    if (document.getElementById("cm-shortcuts-modal")) return openCheatsheet();
    const modal = document.createElement("div");
    modal.className = "modal fade";
    modal.id = "cm-shortcuts-modal";
    modal.setAttribute("tabindex", "-1");
    modal.setAttribute("aria-labelledby", "cm-shortcuts-title");
    modal.setAttribute("aria-hidden", "true");

    const dialog = document.createElement("div");
    dialog.className = "modal-dialog modal-dialog-centered modal-lg";
    const content = document.createElement("div");
    content.className = "modal-content";

    const header = document.createElement("div");
    header.className = "modal-header";
    const title = document.createElement("h2");
    title.className = "modal-title fw-bold";
    title.id = "cm-shortcuts-title";
    title.textContent = "Atajos de teclado";
    const closeBtn = document.createElement("button");
    closeBtn.type = "button";
    closeBtn.className = "btn btn-icon btn-sm btn-active-light-primary ms-auto";
    closeBtn.setAttribute("data-bs-dismiss", "modal");
    closeBtn.setAttribute("aria-label", "Cerrar");
    const closeIcon = document.createElement("i");
    closeIcon.setAttribute("data-lucide", "x");
    closeIcon.className = "fs-1";
    closeBtn.appendChild(closeIcon);
    header.appendChild(title);
    header.appendChild(closeBtn);

    const body = document.createElement("div");
    body.className = "modal-body";

    const groups = [
      ["Navegación rápida", [
        ["G luego H", "Inicio"],
        ["G luego C", "Campañas"],
        ["G luego A", "Agenda política"],
        ["G luego L", "Levantamientos"],
        ["G luego M", "Mapa de levantamientos"],
        ["G luego P", "Publicidad territorial"],
        ["G luego E", "Elecciones"],
        ["G luego U", "Usuarios"],
      ]],
      ["Acciones contextuales", [
        ["/", "Buscar en la lista actual"],
        ["Ctrl/⌘ + /", "Buscar en el menú lateral"],
        ["Ctrl/⌘ + K", "Paleta de comandos"],
        ["N", "Crear nuevo registro (en listas)"],
        ["E", "Editar registro actual (en detalles)"],
      ]],
      ["Generales", [
        ["?", "Mostrar este panel"],
        ["Esc", "Cerrar diálogo o limpiar búsqueda"],
      ]],
    ];

    groups.forEach(([sectionTitle, rows]) => {
      const sec = document.createElement("div");
      sec.className = "mb-5";
      const h = document.createElement("h4");
      h.className = "fw-bold text-gray-800 mb-3 fs-6 text-uppercase";
      h.textContent = sectionTitle;
      sec.appendChild(h);
      rows.forEach(([keys, label]) => {
        const row = document.createElement("div");
        row.className = "d-flex align-items-center justify-content-between py-2 border-bottom border-gray-200";
        const left = document.createElement("span");
        left.className = "text-gray-700 fs-7 fw-semibold";
        left.textContent = label;
        const right = document.createElement("span");
        right.className = "d-flex align-items-center gap-1";
        keys.split(/\s+/).forEach(part => {
          const k = document.createElement("kbd");
          k.className = "px-2 py-1 fs-8 bg-light text-gray-800 border border-gray-300 rounded";
          k.textContent = part;
          right.appendChild(k);
        });
        row.appendChild(left);
        row.appendChild(right);
        sec.appendChild(row);
      });
      body.appendChild(sec);
    });

    content.appendChild(header);
    content.appendChild(body);
    dialog.appendChild(content);
    modal.appendChild(dialog);
    document.body.appendChild(modal);

    openCheatsheet();
  };

  const openCheatsheet = () => {
    const el = document.getElementById("cm-shortcuts-modal");
    if (!el || typeof bootstrap === "undefined") return;
    const m = bootstrap.Modal.getOrCreateInstance(el);
    m.show();
  };

  document.addEventListener("keydown", (e) => {
    const target = e.target;
    const typing = isTyping(target);

    // --- Ctrl/⌘ + K → command palette ---
    if ((e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K")) {
      const palette = document.getElementById("cm-command-palette");
      if (palette && typeof bootstrap !== "undefined") {
        e.preventDefault();
        bootstrap.Modal.getOrCreateInstance(palette).show();
      }
      return;
    }

    // --- "?" → cheatsheet ---
    if (!typing && e.key === "?") {
      e.preventDefault();
      showCheatsheet();
      return;
    }

    if (typing) return;

    // --- "/" → focus list search ---
    if (e.key === "/") {
      const search = document.getElementById("id_table_search");
      if (search) {
        e.preventDefault();
        search.focus();
        search.select();
        return;
      }
    }

    // --- "n" → new record ---
    if (e.key === "n" || e.key === "N") {
      const newBtn = document.querySelector('a.btn.btn-primary[href*="agregar"], a.btn.btn-primary[href*="/add/"]');
      if (newBtn) {
        e.preventDefault();
        navigate(newBtn.getAttribute("href"));
        return;
      }
    }

    // --- "e" → edit current record ---
    if (e.key === "e" || e.key === "E") {
      const editBtn = document.querySelector('a.btn[href*="editar"], a.btn[href*="/change/"]');
      if (editBtn && editBtn.classList.contains("btn-primary")) {
        e.preventDefault();
        navigate(editBtn.getAttribute("href"));
        return;
      }
    }

    // --- "g" + letter → go-to navigation ---
    if (e.key === "g" || e.key === "G") {
      e.preventDefault();
      gPrimed = true;
      clearTimeout(gPrimedTimer);
      gPrimedTimer = setTimeout(() => { gPrimed = false; }, 1500);
      return;
    }
    if (gPrimed) {
      const k = e.key.toLowerCase();
      if (goRoutes[k]) {
        e.preventDefault();
        gPrimed = false;
        clearTimeout(gPrimedTimer);
        navigate(goRoutes[k]);
      } else {
        gPrimed = false;
      }
    }
  });
})();
