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

  window.initFormWidgets = function (selector) {
    var scope = getScope(selector);

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

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      window.initFormWidgets();
    });
  } else {
    window.initFormWidgets();
  }
})(window, document, window.jQuery);
