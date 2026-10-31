// Public Grievance AI Assistant - Client Utilities
document.addEventListener("DOMContentLoaded", function () {
  // 1. Language selector auto-submit
  const langSelect = document.getElementById("lang-select");
  if (langSelect) {
    langSelect.addEventListener("change", function () {
      const form = this.closest("form");
      if (form) form.submit();
    });
  }

  // 2. Collapsible FAQs
  const faqButtons = document.querySelectorAll(".faq-question");
  faqButtons.forEach(btn => {
    btn.addEventListener("click", function () {
      const parent = this.closest(".faq-item");
      if (parent) {
        parent.classList.toggle("open");
        const isExpanded = parent.classList.contains("open");
        this.setAttribute("aria-expanded", isExpanded ? "true" : "false");
      }
    });
  });

  // 3. Multi-step Grievance Form Wizard (Progressive Enhancement)
  const wizardForm = document.getElementById("grievance-form");
  if (wizardForm) {
    const steps = wizardForm.querySelectorAll(".wizard-step-section");
    const stepIndicators = document.querySelectorAll(".wizard-step-indicator");
    let currentStep = 1;

    // Enable JS wizard mode by hiding inactive steps
    wizardForm.classList.add("js-wizard-active");
    showStep(currentStep);

    function showStep(stepNum) {
      steps.forEach((sec, idx) => {
        if (idx + 1 === stepNum) {
          sec.style.display = "block";
        } else {
          sec.style.display = "none";
        }
      });
      stepIndicators.forEach((ind, idx) => {
        if (idx + 1 === stepNum) {
          ind.classList.add("active");
          ind.setAttribute("aria-current", "step");
        } else {
          ind.classList.remove("active");
          ind.removeAttribute("aria-current");
        }
      });
      currentStep = stepNum;

      if (stepNum === 4) {
        // Populate review step
        populateReview();
      }
    }

    function populateReview() {
      const catVal = wizardForm.querySelector("[name='category']")?.value || "";
      const subVal = wizardForm.querySelector("[name='subject']")?.value || "";
      const descVal = wizardForm.querySelector("[name='description']")?.value || "";
      const areaVal = wizardForm.querySelector("[name='area']")?.value || "";
      const landVal = wizardForm.querySelector("[name='landmark']")?.value || "None";
      const nameVal = wizardForm.querySelector("[name='name']")?.value || "Anonymous";
      const contVal = wizardForm.querySelector("[name='contact']")?.value || "None provided";
      const fileInput = wizardForm.querySelector("[name='attachment']");
      const fileVal = fileInput?.files?.[0]?.name || "None";

      const setEl = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
      };

      setEl("rev-category", catVal);
      setEl("rev-subject", subVal);
      setEl("rev-description", descVal);
      setEl("rev-area", areaVal);
      setEl("rev-landmark", landVal);
      setEl("rev-name", nameVal);
      setEl("rev-contact", contVal);
      setEl("rev-attachment", fileVal);
    }

    function validateStep(stepNum) {
      let valid = true;
      clearErrors();

      if (stepNum === 1) {
        const cat = wizardForm.querySelector("[name='category']");
        const sub = wizardForm.querySelector("[name='subject']");
        const desc = wizardForm.querySelector("[name='description']");

        if (!cat.value.trim()) {
          showError(cat, "Please select a category.");
          valid = false;
        }
        if (sub.value.trim().length < 5 || sub.value.trim().length > 120) {
          showError(sub, "Subject must be between 5 and 120 characters.");
          valid = false;
        }
        if (desc.value.trim().length < 20 || desc.value.trim().length > 2000) {
          showError(desc, "Description must be between 20 and 2000 characters.");
          valid = false;
        }
      } else if (stepNum === 2) {
        const area = wizardForm.querySelector("[name='area']");
        if (!area.value.trim()) {
          showError(area, "Please select your municipal ward / area.");
          valid = false;
        }
      } else if (stepNum === 3) {
        const fileInput = wizardForm.querySelector("[name='attachment']");
        if (fileInput && fileInput.files && fileInput.files[0]) {
          const file = fileInput.files[0];
          const ext = file.name.split('.').pop().toLowerCase();
          if (!["pdf", "jpg", "jpeg", "png"].includes(ext)) {
            showError(fileInput, "Only PDF, JPG, and PNG files are allowed.");
            valid = false;
          }
          if (file.size > 2 * 1024 * 1024) {
            showError(fileInput, "File size must not exceed 2 MB.");
            valid = false;
          }
        }
      }
      return valid;
    }

    function showError(field, msg) {
      const parent = field.closest(".form-group");
      if (parent) {
        parent.classList.add("has-error");
        let errSpan = parent.querySelector(".field-error");
        if (!errSpan) {
          errSpan = document.createElement("div");
          errSpan.className = "field-error";
          errSpan.setAttribute("role", "alert");
          parent.appendChild(errSpan);
        }
        errSpan.textContent = msg;
      }
    }

    function clearErrors() {
      wizardForm.querySelectorAll(".has-error").forEach(el => el.classList.remove("has-error"));
      wizardForm.querySelectorAll(".field-error").forEach(el => el.remove());
    }

    // Step button event listeners
    wizardForm.querySelectorAll(".btn-wizard-next").forEach(btn => {
      btn.addEventListener("click", function () {
        if (validateStep(currentStep)) {
          showStep(currentStep + 1);
        }
      });
    });

    wizardForm.querySelectorAll(".btn-wizard-prev").forEach(btn => {
      btn.addEventListener("click", function () {
        showStep(currentStep - 1);
      });
    });
  }
});
