(function () {
  var OPTION_TYPES = ["single_choice", "multiple_choice", "ranking"];
  var NUMERIC_TYPES = ["number", "scale_5", "scale_10", "nps"];

  function closestField(field) {
    if (!field) return null;
    return field.closest(".fv-row, .mb-7, .mb-5, .mb-4, .form-group, .col-12, .col-md-6") || field.parentElement;
  }

  function setFieldVisible(field, visible) {
    var row = closestField(field);
    if (!row) return;
    row.classList.toggle("d-none", !visible);
    if (field.name === "visibility_question") return;
    field.disabled = !visible;
    if (!visible) {
      if (field.multiple) {
        Array.prototype.slice.call(field.options).forEach(function (option) {
          option.selected = false;
        });
      } else if (field.type !== "checkbox") {
        field.value = "";
      }
      if (window.jQuery && window.jQuery.fn.select2) {
        window.jQuery(field).trigger("change.select2");
      }
    }
  }

  function selectedOption(select) {
    return select && select.options ? select.options[select.selectedIndex] : null;
  }

  function parentUsesOptions(questionSelect) {
    var option = selectedOption(questionSelect);
    return option && OPTION_TYPES.indexOf(option.dataset.questionType) !== -1;
  }

  function parentIsNumeric(questionSelect) {
    var option = selectedOption(questionSelect);
    return !!option && NUMERIC_TYPES.indexOf(option.dataset.questionType) !== -1;
  }

  function filterVisibilityOperatorOptions(operatorSelect, questionSelect) {
    if (!operatorSelect) return;
    var numericAllowed = parentIsNumeric(questionSelect);
    var currentValid = true;
    Array.prototype.slice.call(operatorSelect.options).forEach(function (option) {
      if (option.dataset.numericOnly !== "true") return;
      option.hidden = !numericAllowed;
      option.disabled = !numericAllowed;
      if (!numericAllowed && option.selected) currentValid = false;
    });
    if (!currentValid) operatorSelect.value = "equals";
    if (window.jQuery && window.jQuery.fn.select2) {
      window.jQuery(operatorSelect).trigger("change.select2");
    }
  }

  function filterVisibilityOptions(optionSelect, questionSelect) {
    if (!optionSelect || !questionSelect) return;
    var questionId = questionSelect.value || "";
    var currentValid = false;
    Array.prototype.slice.call(optionSelect.options).forEach(function (option) {
      if (!option.value) {
        option.hidden = false;
        option.disabled = false;
        return;
      }
      var matches = option.dataset.questionId === questionId;
      option.hidden = !matches;
      option.disabled = !matches;
      if (matches && option.selected) currentValid = true;
    });
    if (!currentValid) optionSelect.value = "";
    if (window.jQuery && window.jQuery.fn.select2) {
      window.jQuery(optionSelect).trigger("change.select2");
    }
  }

  function initQuestionBuilderForm(scope) {
    var root = scope || document;
    var questionType = root.querySelector('[data-survey-builder-field="question-type"]');
    var options = root.querySelector('[data-survey-builder-field="options"]');
    var visibilityQuestion = root.querySelector('[data-survey-builder-field="visibility-question"]');
    var visibilityOperator = root.querySelector('[data-survey-builder-field="visibility-operator"]');
    var visibilityOption = root.querySelector('[data-survey-builder-field="visibility-option"]');
    var visibilityValue = root.querySelector('[data-survey-builder-field="visibility-value"]');
    if (!questionType && !visibilityQuestion) return;

    function sync() {
      var usesOwnOptions = questionType && OPTION_TYPES.indexOf(questionType.value) !== -1;
      setFieldVisible(options, usesOwnOptions);

      var hasParent = visibilityQuestion && !!visibilityQuestion.value;
      setFieldVisible(visibilityOperator, hasParent);
      if (!hasParent) {
        setFieldVisible(visibilityOption, false);
        setFieldVisible(visibilityValue, false);
        return;
      }

      if (visibilityOperator && visibilityOperator.value === "always") {
        visibilityOperator.value = "equals";
      }
      filterVisibilityOperatorOptions(visibilityOperator, visibilityQuestion);
      var canUseParentOptions = parentUsesOptions(visibilityQuestion);
      filterVisibilityOptions(visibilityOption, visibilityQuestion);
      setFieldVisible(visibilityOption, canUseParentOptions);
      setFieldVisible(visibilityValue, !canUseParentOptions);
    }

    [questionType, visibilityQuestion, visibilityOperator].forEach(function (field) {
      if (!field) return;
      field.addEventListener("change", sync);
      if (window.jQuery && window.jQuery.fn.select2) {
        window.jQuery(field).on("select2:select select2:clear", sync);
      }
    });
    sync();
  }

  window.initSurveyQuestionBuilderForm = initQuestionBuilderForm;

  document.addEventListener("DOMContentLoaded", function () {
    initQuestionBuilderForm(document);
  });
  document.addEventListener("shown.bs.modal", function (event) {
    initQuestionBuilderForm(event.target);
  });
  document.addEventListener("drawer:shown", function (event) {
    initQuestionBuilderForm((event.detail && event.detail.drawer) || event.target);
  });
})();
