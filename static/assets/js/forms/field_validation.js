/* field_validation.js — lightweight on-blur validation for candidate-style
   forms. Adds inline feedback for Ecuadorian cédulas and email formats so
   users see issues before submitting. Server-side validation still runs.

   Selectors: any input named exactly "identification" / "cedula" gets a
   10-digit Ecuador cédula check (length + verifier digit). Any input with
   type="email" gets a basic format check.
*/
(function () {
  "use strict";

  const ERROR_CLASS = "cm-field-error";
  const INVALID_CLASS = "is-invalid";

  function showError(input, message) {
    if (!input) return;
    input.classList.add(INVALID_CLASS);
    let hint = input.parentElement.querySelector("." + ERROR_CLASS + "[data-cm-validation]");
    if (!hint) {
      hint = document.createElement("span");
      hint.className = ERROR_CLASS;
      hint.setAttribute("data-cm-validation", "1");
      input.insertAdjacentElement("afterend", hint);
    }
    hint.textContent = message;
  }

  function clearError(input) {
    if (!input) return;
    input.classList.remove(INVALID_CLASS);
    const hint = input.parentElement.querySelector("." + ERROR_CLASS + "[data-cm-validation]");
    if (hint) hint.remove();
  }

  // Ecuador cédula: 10 digits, last digit is a Mod-10 verifier.
  // First 2 digits = province (01–24), 3rd digit < 6 for natural persons.
  function validateCedulaEC(value) {
    const digits = (value || "").replace(/\D/g, "");
    if (digits.length === 0) return null; // empty = let server / required handle it
    if (digits.length !== 10) return "La cédula debe tener 10 dígitos.";
    const province = parseInt(digits.slice(0, 2), 10);
    if (province < 1 || province > 24) return "Los dos primeros dígitos no corresponden a una provincia válida.";
    const third = parseInt(digits[2], 10);
    if (third > 5) return "Esta no parece ser una cédula de persona natural.";
    const coef = [2, 1, 2, 1, 2, 1, 2, 1, 2];
    let sum = 0;
    for (let i = 0; i < 9; i++) {
      let v = parseInt(digits[i], 10) * coef[i];
      if (v >= 10) v -= 9;
      sum += v;
    }
    const verifier = (10 - (sum % 10)) % 10;
    if (verifier !== parseInt(digits[9], 10)) return "El dígito verificador de la cédula no coincide.";
    return null;
  }

  function validateEmail(value) {
    if (!value) return null; // let server / required handle empty
    // Standard practical email check (not RFC 5322 strict — purpose is helpful nudge).
    const re = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/;
    if (!re.test(value)) return "Revisa el correo: parece que falta @ o el dominio.";
    return null;
  }

  function bindCedulaInputs(root) {
    const inputs = root.querySelectorAll('input[name="identification"], input[name="cedula"], input[data-cm-validate="cedula"]');
    inputs.forEach((input) => {
      if (input.dataset.cmValidationBound === "1") return;
      input.dataset.cmValidationBound = "1";
      input.addEventListener("blur", () => {
        const err = validateCedulaEC(input.value);
        if (err) showError(input, err);
        else clearError(input);
      });
      input.addEventListener("input", () => {
        // While typing, only clear error once length is correct again.
        if (input.classList.contains(INVALID_CLASS) && input.value.replace(/\D/g, "").length !== 10) {
          // keep the warning visible but don't re-validate every keystroke
          return;
        }
        if (input.value === "") clearError(input);
      });
    });
  }

  function bindEmailInputs(root) {
    const inputs = root.querySelectorAll('input[type="email"], input[data-cm-validate="email"]');
    inputs.forEach((input) => {
      if (input.dataset.cmValidationBound === "1") return;
      input.dataset.cmValidationBound = "1";
      input.addEventListener("blur", () => {
        const err = validateEmail(input.value.trim());
        if (err) showError(input, err);
        else clearError(input);
      });
      input.addEventListener("input", () => {
        if (input.value === "") clearError(input);
      });
    });
  }

  function init() {
    bindCedulaInputs(document);
    bindEmailInputs(document);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
