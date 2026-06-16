/**
 * Approval modal behaviors for territorial advertisements. The form is
 * injected via AJAX (workflows.js), so everything here is delegated from the
 * document and works regardless of when the modal appears (map or detail).
 *
 *  - Dim/disable a unit's size + instructions when its "Aprobar" switch is off.
 *  - "Agregar publicidad": add/remove brand-new advertisement rows and filter
 *    the size options by the chosen type.
 */
(function () {
  if (window.__cmApprovalFormBound) return;
  window.__cmApprovalFormBound = true;

  function toggleUnitBlock(checkbox) {
    var fieldset = checkbox.closest("fieldset");
    if (!fieldset) return;
    var enabled = checkbox.checked;
    fieldset.querySelectorAll("select, textarea, input").forEach(function (input) {
      if (input === checkbox) return;
      input.disabled = !enabled;
    });
    fieldset.style.opacity = enabled ? "" : "0.55";
  }

  function filterSizes(row) {
    if (!row) return;
    var typeSelect = row.querySelector("[data-new-ad-type]");
    var sizeSelect = row.querySelector("[data-new-ad-size]");
    if (!typeSelect || !sizeSelect) return;
    var typeId = typeSelect.value;
    Array.prototype.forEach.call(sizeSelect.options, function (option) {
      var optType = option.getAttribute("data-type");
      if (!optType) return; // keep the "sin tamaño" placeholder
      var match = optType === typeId;
      option.hidden = !match;
      option.disabled = !match;
      if (!match && option.selected) sizeSelect.value = "";
    });
  }

  document.addEventListener("click", function (event) {
    var addBtn = event.target.closest("[data-add-new-ad]");
    if (addBtn) {
      // Inside the map's nested pin modal, a parent handler closes the modal
      // when a click bubbles up. Stop it so adding a row keeps the modal open.
      event.preventDefault();
      event.stopPropagation();
      var fieldset = addBtn.closest("[data-new-ads]");
      if (!fieldset) return;
      var container = fieldset.querySelector("[data-new-ad-container]");
      var template = fieldset.querySelector("#new-ad-row-template");
      if (!container || !template) return;
      var index = parseInt(container.dataset.nextIndex || "0", 10);
      // Clone the <template> content and stamp the row index into the field
      // names (avoids innerHTML; index is always an integer).
      var fragment = template.content.cloneNode(true);
      fragment.querySelectorAll("[name]").forEach(function (el) {
        el.setAttribute("name", el.getAttribute("name").replace(/__I__/g, index));
      });
      container.appendChild(fragment);
      container.dataset.nextIndex = index + 1;
      if (window.lucide && window.lucide.createIcons) window.lucide.createIcons();
      return;
    }
    var removeBtn = event.target.closest("[data-remove-new-ad]");
    if (removeBtn) {
      event.preventDefault();
      event.stopPropagation();
      var row = removeBtn.closest("[data-new-ad-row]");
      if (row) row.remove();
    }
  });

  document.addEventListener("change", function (event) {
    var target = event.target;
    if (!target) return;
    if (target.name && target.name.indexOf("unit_approved_") === 0) {
      toggleUnitBlock(target);
    } else if (target.matches && target.matches("[data-new-ad-type]")) {
      filterSizes(target.closest("[data-new-ad-row]"));
    }
  });
})();
