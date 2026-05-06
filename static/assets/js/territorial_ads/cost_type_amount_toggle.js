(function (window, document) {
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

  function init(scope) {
    scope = scope || document;
    var select = scope.querySelector('select[data-cost-type-select="1"]');
    var amountInput = scope.querySelector('[data-cost-amount-input="1"]');
    if (!select || !amountInput) return;
    if (select.dataset.costTypeAmountInitialized === "1") return;
    select.dataset.costTypeAmountInitialized = "1";

    applyState(select, amountInput);

    select.addEventListener("change", function () {
      applyState(select, amountInput);
    });

    if (window.jQuery) {
      window.jQuery(select).on("select2:select select2:clear change.select2", function () {
        applyState(select, amountInput);
      });
    }
  }

  window.CostTypeAmountToggle = { init: init };

  document.addEventListener("DOMContentLoaded", function () {
    init(document);
  });
})(window, document);
