(function (window, document, $) {
  "use strict";

  var DEFAULT_PLACEHOLDER = "Seleccione un elemento";
  var INIT_FLAG = "campaign-select2-initialized";

  // Build a per-field placeholder ("Selecciona <label>...") by inspecting the
  // nearest visible <label>. Falls back to DEFAULT_PLACEHOLDER if we can't
  // find a meaningful label.
  function buildContextualPlaceholder($field) {
    var fieldId = $field.attr("id");
    var labelText = "";
    if (fieldId) {
      var $label = $('label[for="' + fieldId + '"]').first();
      if ($label.length) labelText = $label.clone().children().remove().end().text().trim();
    }
    if (!labelText) {
      var $closeLabel = $field.closest(".fv-row, .form-group, .mb-3").find("label").first();
      if ($closeLabel.length) labelText = $closeLabel.clone().children().remove().end().text().trim();
    }
    if (!labelText) return DEFAULT_PLACEHOLDER;
    labelText = labelText.replace(/[*:]+\s*$/, "").trim();
    if (!labelText) return DEFAULT_PLACEHOLDER;
    var lower = labelText.toLowerCase();
    var multiple = $field.prop("multiple");
    return (multiple ? "Selecciona " : "Selecciona ") + lower;
  }

  function getScope(selector) {
    if (!selector) {
      return $(document);
    }
    return selector.jquery ? selector : $(selector);
  }

  function getFields(selector) {
    var $scope = getScope(selector);
    return $scope.is(".django-select2")
      ? $scope
      : $scope.find(".django-select2");
  }

  function getPlaceholder($field) {
    var placeholder = $field.attr("data-placeholder") || $field.data("placeholder");
    // Replace the generic Django Select2 default with a per-field contextual hint
    // ("Selecciona elección" instead of "Seleccione un elemento").
    if (!placeholder || placeholder === DEFAULT_PLACEHOLDER) {
      placeholder = buildContextualPlaceholder($field);
    }
    $field.attr("data-placeholder", placeholder);
    return placeholder;
  }

  function normalizeResults(data) {
    var rawResults = [];
    var more = false;

    if ($.isArray(data)) {
      rawResults = data;
    } else if (data && $.isArray(data.results)) {
      rawResults = data.results;
      more = Boolean(data.more || (data.pagination && data.pagination.more));
    }

    return {
      results: rawResults,
      pagination: {
        more: more
      }
    };
  }

  function ajaxOptions($field) {
    return {
      data: function (params) {
        var result = {
          term: params.term,
          page: params.page,
          field_id: $field.data("field_id")
        };
        var dependentFields = $field.data("select2-dependent-fields");

        if (dependentFields) {
          $.each(String(dependentFields).trim().split(/\s+/), function (i, dependentField) {
            result[dependentField] = $("[name=" + dependentField + "]", $field.closest("form")).val();
          });
        }

        return result;
      },
      processResults: normalizeResults
    };
  }

  function prepareField($field, placeholder) {
    if (!$field.prop("multiple")) {
      var $emptyOption = $field.find('option[value=""]').first();
      if ($emptyOption.length === 0) {
        $field.prepend(new Option("", "", false, !$field.val()));
      } else {
        $emptyOption.text("");
      }
    }

    if ($field.prop("multiple")) {
      $field.find('option[value=""]').prop("selected", false);
    }

    $field.attr("data-control", "");
    $field.attr("data-kt-initialized", "1");
    $field.attr("data-placeholder", placeholder);
    $field.attr("data-theme", "bootstrap5");
  }

  function initField(field) {
    var $field = $(field);

    if ($field.data(INIT_FLAG)) {
      return;
    }

    if ($field.hasClass("select2-hidden-accessible")) {
      $field.select2("destroy");
    }

    var placeholder = getPlaceholder($field);
    var dropdownParent = $field.closest(".modal");
    var allowClear = String($field.data("allow-clear")) === "true" && !$field.prop("multiple");
    var options = {
      theme: "bootstrap5",
      width: "100%",
      dropdownAutoWidth: true,
      selectionCssClass: ":all:",
      placeholder: {
        id: "",
        text: placeholder
      },
      allowClear: allowClear,
      dropdownParent: dropdownParent.length ? dropdownParent : $(document.body),
      language: {
        noResults: function () {
          if ($field.data("app") && $field.data("model")) {
            return '<button type="button" class="btn btn-sm btn-primary w-100" onclick="select2create(this)">Crear nuevo</button>';
          }
          return "Sin resultados";
        },
        searching: function () {
          return "Buscando...";
        },
        errorLoading: function () {
          return "No se pudieron cargar los resultados.";
        },
        loadingMore: function () {
          return "Cargando mas resultados...";
        }
      },
      escapeMarkup: function (markup) {
        return markup;
      }
    };

    prepareField($field, placeholder);

    if ($field.hasClass("django-select2-heavy")) {
      options.ajax = ajaxOptions($field);
    }

    $field.select2(options);

    $field.on("select2:select.campaign-select2", function (event) {
      var name = $(event.currentTarget).attr("name");
      $("[data-select2-dependent-fields=" + name + "]").each(function () {
        $(this).val("").trigger("change");
      });
    });

    $field.data(INIT_FLAG, true);
  }

  window.initSelect2 = function (selector) {
    if (!$ || !$.fn || !$.fn.select2) {
      return;
    }

    getFields(selector).each(function () {
      initField(this);
    });
  };

  window.select2create = async function (button) {
    var results = button.closest(".select2-results__options");
    if (!results || !results.id) {
      return;
    }

    var match = results.id.match(/^select2-(.+)-results$/);
    if (!match) {
      return;
    }

    var field = document.getElementById(match[1]);
    var modalElement = document.getElementById("insoles-forms");
    if (!field || !modalElement || !field.dataset.app || !field.dataset.model) {
      return;
    }

    $("#" + field.id).select2("close");

    try {
      var response = await fetch("/insoles/forms/" + field.dataset.app + "/" + field.dataset.model + "/", {
        credentials: "include"
      });
      if (!response.ok) {
        throw new Error("No autorizado");
      }
      var data = await response.json();
      var form = modalElement.querySelector("form");
      var body = modalElement.querySelector(".modal-body");
      form.action = data.create_url;
      form.dataset.element = field.id;
      body.innerHTML = data.template;
      if (window.initFormWidgets) {
        window.initFormWidgets(modalElement);
      } else {
        window.initSelect2(modalElement);
      }
      bootstrap.Modal.getOrCreateInstance(modalElement).show();
    } catch (error) {
      if (window.toastr) {
        window.toastr.error("No tienes permisos para realizar esta acción.", "No autorizado");
      }
    }
  };

  $(document).on("submit", "#insoles-form", async function (event) {
    event.preventDefault();

    var form = this;
    var target = document.getElementById(form.dataset.element);
    if (!target) {
      return;
    }

    var response = await fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      credentials: "include"
    });
    var data = await response.json();

    if (!response.ok) {
      if (window.toastr) {
        window.toastr.error(data.error || "No se pudo guardar el formulario.", "Error");
      }
      return;
    }

    var option = new Option(data.text, data.id, true, true);
    $(target).append(option).trigger("change");
    bootstrap.Modal.getOrCreateInstance(document.getElementById("insoles-forms")).hide();
    form.reset();
  });
})(window, document, window.jQuery);
