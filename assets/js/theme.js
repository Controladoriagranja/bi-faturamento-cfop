/* Mesma preferência dos demais relatórios da Granja Brasília. */
(() => {
  const key = "bi-zootecnico-theme";
  function initial() {
    try {const value = localStorage.getItem(key); if (value === "light" || value === "dark") return value;} catch (_) {}
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  function apply(theme) {
    document.documentElement.dataset.theme = theme;
    document.querySelectorAll("[data-theme-toggle]").forEach(button => {
      button.setAttribute("aria-pressed", String(theme === "dark"));
      button.title = theme === "dark" ? "Ativar tema claro" : "Ativar tema escuro";
      button.setAttribute("aria-label", button.title);
      button.querySelector("[data-theme-icon]").textContent = theme === "dark" ? "☀" : "☾";
    });
    document.dispatchEvent(new CustomEvent("dashboard:theme-changed", {detail: {theme}}));
  }
  window.ThemeManager = {
    get: () => document.documentElement.dataset.theme || initial(),
    toggle() {
      const theme = this.get() === "dark" ? "light" : "dark";
      try {localStorage.setItem(key, theme);} catch (_) {}
      apply(theme);
    }
  };
  apply(initial());
  document.addEventListener("click", event => {if (event.target.closest("[data-theme-toggle]")) ThemeManager.toggle();});
})();
