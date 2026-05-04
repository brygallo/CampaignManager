(function (window, $) {
  "use strict";

  window.initSelect2 = function (selector) {
    var $scope = selector ? $(selector) : $(document);
    $scope.find(".django-select2").each(function () {
      var $field = $(this);
      if ($field.data("campaign-select2-initialized")) {
        return;
      }
      var dropdownParent = $field.closest(".modal");
      $field.djangoSelect2({
        placeholder: "Seleccione un elemento",
        dropdownAutoWidth: true,
        width: "100%",
        dropdownParent: dropdownParent.length ? dropdownParent : undefined,
        language: {
          noResults: function () {
            if ($field.data("app") && $field.data("model")) {
              return "<button type=\"button\" class=\"btn btn-sm btn-primary w-100\" onclick=\"select2create(this)\">Crear nuevo</button>";
            }
            return "Sin resultados";
          },
          searching: function () {
            return "Buscando...";
          }
        },
        escapeMarkup: function (markup) {
          return markup;
        }
      });
      $field.data("campaign-select2-initialized", true);
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

  $(function () {
    window.initSelect2();
  });
})(window, window.jQuery);
