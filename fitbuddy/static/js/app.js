document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("form").forEach((form) => {
    form.addEventListener("submit", () => {
      const button = form.querySelector("button[type='submit']");
      if (button && !form.action.endsWith("/submit-feedback")) {
        button.disabled = true;
        button.dataset.originalText = button.innerHTML;
        button.innerHTML = "Building your plan <span>…</span>";
      }
    });
  });
});

