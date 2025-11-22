// static/js/theme.js
const THEME_KEY = "uap-theme";
const themes = ["default", "rose", "tulip", "beach", "golden", "dark"];

function applyTheme(theme) {
  if (!themes.includes(theme)) theme = "default";
  document.body.classList.remove(...themes.map(t => "theme-" + t));
  document.body.classList.add("theme-" + theme);
  localStorage.setItem(THEME_KEY, theme);
  const selector = document.getElementById("themeSelect");
  if (selector) selector.value = theme;
}

function initTheme() {
  const savedTheme = localStorage.getItem(THEME_KEY) || "default";
  applyTheme(savedTheme);

  const selector = document.getElementById("themeSelect");
  if (selector) {
    selector.addEventListener("change", (e) => {
      applyTheme(e.target.value);
    });
  }
}

// Run after DOM is ready
document.addEventListener("DOMContentLoaded", initTheme);
