(function () {
  "use strict";

  function applyState(select, amountInput) {
    var selected = select.options[select.selectedIndex];
    var requires = selected ? selected.getAttribute("data-requires-amount") === "1" : false;
    amountInput.disabled = !requires;
    amountInput.readOnly = !requires;
    if (!requires) {
      amountInput.value = "";
    }
    var wrapper = amountInput.closest(".form-group, .mb-3, .col-md-6, .col-12") || amountInput.parentElement;
    if (wrapper) {
      wrapper.classList.toggle("opacity-50", !requires);
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    var select = document.querySelector('select[data-cost-type-select="1"]');
    var amountInput = document.querySelector('[data-cost-amount-input="1"]');
    if (!select || !amountInput) return;

    applyState(select, amountInput);

    select.addEventListener("change", function () {
      applyState(select, amountInput);
    });

    if (window.jQuery) {
      window.jQuery(select).on("select2:select select2:clear change.select2", function () {
        applyState(select, amountInput);
      });
    }
  });
})();
