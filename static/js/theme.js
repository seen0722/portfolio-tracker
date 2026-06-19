/* Theme system: set before paint (no FOUC), persist choice, follow system by
   default, and emit a `themechange` event so charts can re-render. */
(function () {
  var KEY = "pt-theme";
  var root = document.documentElement;

  function systemPref() {
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function current() {
    return root.getAttribute("data-theme") || "light";
  }

  function apply(theme) {
    root.setAttribute("data-theme", theme);
  }

  // Apply immediately (this script is loaded synchronously in <head>).
  var saved = null;
  try { saved = localStorage.getItem(KEY); } catch (e) {}
  apply(saved || systemPref());

  function setTheme(theme) {
    apply(theme);
    try { localStorage.setItem(KEY, theme); } catch (e) {}
    window.dispatchEvent(new CustomEvent("themechange", { detail: { theme: theme } }));
    updateToggles();
  }

  function updateToggles() {
    var t = current();
    var label = t === "dark" ? "切換淺色模式" : "切換深色模式";
    document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
      btn.textContent = t === "dark" ? "☀" : "☾";
      btn.setAttribute("aria-label", label);
      btn.setAttribute("title", label);
    });
  }

  // Follow system changes only when the user hasn't explicitly chosen.
  if (window.matchMedia) {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function (e) {
      var explicit = null;
      try { explicit = localStorage.getItem(KEY); } catch (err) {}
      if (!explicit) setTheme(e.matches ? "dark" : "light");
    });
  }

  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-theme-toggle]");
    if (!btn) return;
    setTheme(current() === "dark" ? "light" : "dark");
  });

  window.PortfolioTheme = { set: setTheme, current: current, colors: function () {
    var cs = getComputedStyle(root);
    return {
      ink: cs.getPropertyValue("--ink").trim(),
      ink2: cs.getPropertyValue("--ink-2").trim(),
      muted: cs.getPropertyValue("--muted").trim(),
      line: cs.getPropertyValue("--line").trim(),
      accent: cs.getPropertyValue("--accent").trim(),
      surface: cs.getPropertyValue("--surface").trim(),
    };
  } };

  document.addEventListener("DOMContentLoaded", updateToggles);
})();
