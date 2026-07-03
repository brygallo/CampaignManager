(function (window, document) {
  "use strict";

  function formFromScope(scope) {
    if (!scope) return document;
    if (scope.tagName === "FORM") return scope;
    return scope.querySelector ? scope : document;
  }

  function policyBlocks(scope) {
    var root = formFromScope(scope);
    if (root.matches && root.matches("[data-form-conditional-policies]")) return [root];
    return Array.prototype.slice.call(root.querySelectorAll("[data-form-conditional-policies]"));
  }

  function parsePolicies(block) {
    try {
      return JSON.parse(block.textContent || "[]");
    } catch (error) {
      return [];
    }
  }

  function closestForm(block) {
    return block.closest("form") || block.parentElement || document;
  }

  function fieldsByName(form, name) {
    return Array.prototype.slice.call(form.querySelectorAll('[name="' + CSS.escape(name) + '"]'));
  }

  function fieldValue(form, name) {
    var fields = fieldsByName(form, name);
    if (!fields.length) return "";
    var first = fields[0];
    if (first.type === "checkbox" && fields.length === 1) return first.checked;
    if (first.type === "checkbox") {
      // A group of checkboxes sharing the same name (e.g. CheckboxSelectMultiple)
      // — return the checked values so "contains"/"in" can match against them.
      return fields.filter(function (field) { return field.checked; }).map(function (field) {
        return field.value;
      });
    }
    if (first.type === "radio") {
      var checked = fields.find(function (field) { return field.checked; });
      return checked ? checked.value : "";
    }
    if (first.multiple) {
      return Array.prototype.slice.call(first.selectedOptions).map(function (option) {
        return option.value;
      });
    }
    return first.value;
  }

  function isTruthy(value) {
    if (value === true) return true;
    return ["1", "true", "on", "yes", "si", "sí"].indexOf(String(value).toLowerCase()) !== -1;
  }

  function compare(actual, operator, expected) {
    operator = String(operator || "equals").toLowerCase();
    if (operator === "checked") return isTruthy(actual);
    if (operator === "unchecked") return !isTruthy(actual);
    if (operator === "empty") return actual == null || actual === "" || (Array.isArray(actual) && !actual.length);
    if (operator === "not_empty") return !(actual == null || actual === "" || (Array.isArray(actual) && !actual.length));
    if (operator === "in") return (expected || []).map(String).indexOf(String(actual)) !== -1;
    if (operator === "not_in") return (expected || []).map(String).indexOf(String(actual)) === -1;
    if ([">", "gt", ">=", "gte", "<", "lt", "<=", "lte"].indexOf(operator) !== -1) {
      var actualNumber = Number(actual);
      var expectedNumber = Number(expected);
      if (Number.isNaN(actualNumber) || Number.isNaN(expectedNumber)) return false;
      if (operator === ">" || operator === "gt") return actualNumber > expectedNumber;
      if (operator === ">=" || operator === "gte") return actualNumber >= expectedNumber;
      if (operator === "<" || operator === "lt") return actualNumber < expectedNumber;
      return actualNumber <= expectedNumber;
    }
    if (operator === "contains") {
      if (Array.isArray(actual)) return actual.map(String).indexOf(String(expected)) !== -1;
      return String(actual).indexOf(String(expected)) !== -1;
    }
    if (operator === "startswith") return String(actual).indexOf(String(expected)) === 0;
    if (operator === "endswith") {
      actual = String(actual);
      expected = String(expected);
      return actual.slice(-expected.length) === expected;
    }
    if (operator === "regex") {
      try {
        return new RegExp(String(expected)).test(String(actual));
      } catch (error) {
        return false;
      }
    }
    if (operator === "not_equals") return String(actual) !== String(expected);
    return String(actual) === String(expected);
  }

  function evaluate(form, condition) {
    if (!condition || condition.type === "always") return true;
    if (condition.type === "never") return false;
    if (condition.type === "field") {
      return compare(fieldValue(form, condition.field), condition.operator || "equals", condition.value);
    }
    if (condition.type === "all") {
      return (condition.predicates || []).every(function (part) { return evaluate(form, part); });
    }
    if (condition.type === "any") {
      return (condition.predicates || []).some(function (part) { return evaluate(form, part); });
    }
    if (condition.type === "not") return !evaluate(form, condition.predicate);
    return false;
  }

  function fieldContainer(form, name) {
    return form.querySelector('[data-form-field-container="' + CSS.escape(name) + '"]') ||
      form.querySelector('[data-form-field="' + CSS.escape(name) + '"]');
  }

  function clearField(field) {
    if (field.type === "checkbox" || field.type === "radio") {
      field.checked = false;
    } else if (field.multiple) {
      Array.prototype.slice.call(field.options).forEach(function (option) {
        option.selected = false;
      });
    } else {
      field.value = "";
    }
    if (window.jQuery && window.jQuery.fn && window.jQuery.fn.select2) {
      window.jQuery(field).trigger("change.select2");
    }
  }

  function applyPolicy(form, policy) {
    var active = evaluate(form, policy.condition);
    var effects = policy.effects || [];
    var suppressTarget = effects.indexOf("show") !== -1 && effects.indexOf("hide") === -1
      ? !active
      : active;
    (policy.targets || []).forEach(function (target) {
      var container = fieldContainer(form, target);
      var fields = fieldsByName(form, target);
      var shouldHide = (effects.indexOf("hide") !== -1 || effects.indexOf("show") !== -1) && suppressTarget;
      var shouldDisable = effects.indexOf("disable") !== -1 && suppressTarget;
      if (container) container.classList.toggle("d-none", shouldHide);
      fields.forEach(function (field) {
        field.disabled = shouldDisable;
        if (suppressTarget && effects.indexOf("clear") !== -1) clearField(field);
      });
    });
  }

  function applyRequiredPolicy(form, policy) {
    var active = evaluate(form, policy.condition);
    (policy.targets || []).forEach(function (target) {
      var container = fieldContainer(form, target);
      var fields = fieldsByName(form, target);
      fields.forEach(function (field) {
        field.required = active;
      });
      if (container) {
        var label = container.querySelector("label");
        if (label) label.classList.toggle("required", active);
      }
    });
  }

  function syncForm(form, policies) {
    policies.forEach(function (policy) {
      if (policy.kind === "conditional") applyPolicy(form, policy);
      if (policy.kind === "required") applyRequiredPolicy(form, policy);
    });
  }

  function bindForm(form, policies) {
    if (!form) return;
    form._conditionalPolicies = policies;
    if (form.dataset.conditionalFieldsBound === "true") {
      syncForm(form, policies);
      return;
    }
    form.dataset.conditionalFieldsBound = "true";
    form.addEventListener("change", function () { syncForm(form, form._conditionalPolicies || []); }, true);
    form.addEventListener("input", function () { syncForm(form, form._conditionalPolicies || []); }, true);
    if (window.jQuery) {
      window.jQuery(form).on("select2:select select2:clear", function () {
        syncForm(form, form._conditionalPolicies || []);
      });
    }
    syncForm(form, policies);
  }

  function init(scope) {
    policyBlocks(scope).forEach(function (block) {
      bindForm(closestForm(block), parsePolicies(block));
    });
  }

  window.initConditionalFields = init;

  document.addEventListener("DOMContentLoaded", function () { init(document); });
  document.addEventListener("shown.bs.modal", function (event) { init(event.target); });
})(window, document);
