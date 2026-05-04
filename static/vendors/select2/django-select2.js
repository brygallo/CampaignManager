/* global define, jQuery */
(function (factory) {
  if (typeof define === "function" && define.amd) {
    define(["jquery"], factory);
  } else if (typeof module === "object" && module.exports) {
    module.exports = factory(require("jquery"));
  } else {
    factory(jQuery);
  }
}(function ($) {
  "use strict";

  var init = function ($element, options) {
    $element.select2(options);
  };

  var initHeavy = function ($element, options) {
    var settings = $.extend({
      ajax: {
        data: function (params) {
          var result = {
            term: params.term,
            page: params.page,
            field_id: $element.data("field_id")
          };

          var dependentFields = $element.data("select2-dependent-fields");
          if (dependentFields) {
            dependentFields = dependentFields.trim().split(/\s+/);
            $.each(dependentFields, function (i, dependentField) {
              result[dependentField] = $("[name=" + dependentField + "]", $element.closest("form")).val();
            });
          }

          return result;
        },
        processResults: function (data) {
          var results = [];
          var more = false;

          if ($.isArray(data)) {
            results = data;
          } else if (data && $.isArray(data.results)) {
            results = data.results;
            more = Boolean(data.more || (data.pagination && data.pagination.more));
          }

          return {
            results: results,
            pagination: {
              more: more
            }
          };
        }
      }
    }, options);

    $element.select2(settings);
  };

  $.fn.djangoSelect2 = function (options) {
    var settings = $.extend({}, options);
    $.each(this, function (i, element) {
      var $element = $(element);
      if (settings.theme) {
        $element.attr("data-theme", settings.theme);
      }
      if (settings.placeholder && typeof settings.placeholder === "string") {
        $element.attr("data-placeholder", settings.placeholder);
      }
      if ($element.hasClass("django-select2-heavy")) {
        initHeavy($element, settings);
      } else {
        init($element, settings);
      }
      $element.on("select2:select", function (event) {
        var name = $(event.currentTarget).attr("name");
        $("[data-select2-dependent-fields=" + name + "]").each(function () {
          $(this).val("").trigger("change");
        });
      });
    });
    return this;
  };

  return $.fn.djangoSelect2;
}));
