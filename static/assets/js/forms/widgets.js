(function (window, document, $) {
  "use strict";

  function getScope(selector) {
    if (!selector) {
      return document;
    }
    if (selector.jquery) {
      return selector.get(0) || document;
    }
    return selector;
  }

  function findAll(scope, selector) {
    var elements = [];
    if (scope.matches && scope.matches(selector)) {
      elements.push(scope);
    }
    return elements.concat([].slice.call(scope.querySelectorAll(selector)));
  }

  function initFlatpickr(scope) {
    if (!window.flatpickr) {
      return;
    }

    findAll(scope, ".js-flatpickr-date").forEach(function (element) {
      if (element._flatpickr) {
        return;
      }
      element.type = "text";
      window.flatpickr(element, {
        allowInput: true,
        dateFormat: "Y-m-d",
        disableMobile: true
      });
    });

    findAll(scope, ".js-flatpickr-datetime").forEach(function (element) {
      if (element._flatpickr) {
        return;
      }
      element.type = "text";
      window.flatpickr(element, {
        allowInput: true,
        dateFormat: "Y-m-d H:i",
        disableMobile: true,
        enableTime: true,
        time_24hr: true
      });
    });
  }

  window.initFormWidgets = function (selector) {
    var scope = getScope(selector);

    if (window.cmRenderIcons) {
      window.cmRenderIcons();
    }

    if (window.initSelect2) {
      window.initSelect2(scope);
    }

    if (window.KTApp && typeof window.KTApp.init === "function") {
      window.KTApp.init();
    }

    if (window.KTDialer && typeof window.KTDialer.createInstances === "function") {
      window.KTDialer.createInstances('[data-kt-dialer="true"]');
    }

    if (window.KTImageInput && typeof window.KTImageInput.createInstances === "function") {
      window.KTImageInput.createInstances('[data-kt-image-input="true"]');
    }

    if (window.KTPasswordMeter && typeof window.KTPasswordMeter.createInstances === "function") {
      window.KTPasswordMeter.createInstances('[data-kt-password-meter="true"]');
    }

    initFlatpickr(scope);

    if (window.initLeafletMaps) {
      window.initLeafletMaps(scope);
    }

    if (window.autosize) {
      window.autosize(scope.querySelectorAll('[data-kt-autosize="true"], textarea.form-control'));
    }

    if (window.Inputmask) {
      Inputmask().mask(scope.querySelectorAll("[data-inputmask], .input-mask"));
    } else if ($ && $.fn.inputmask) {
      $(scope).find("[data-inputmask], .input-mask").inputmask();
    }

    if ($ && $.fn.repeater) {
      $(scope).find('[data-repeater="true"]:not([data-form-repeater-initialized="true"])').each(function () {
        $(this).repeater();
        this.setAttribute("data-form-repeater-initialized", "true");
      });
    }
  };

  document.addEventListener("click", function (event) {
    var toggle = event.target.closest(".js-flatpickr-toggle");
    if (!toggle) {
      return;
    }
    var input = toggle.closest(".input-group").querySelector(".js-flatpickr-date, .js-flatpickr-datetime");
    if (input && input._flatpickr) {
      input._flatpickr.open();
    }
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      window.initFormWidgets();
    });
  } else {
    window.initFormWidgets();
  }
})(window, document, window.jQuery);
