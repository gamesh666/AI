/** Two looks shared with REACH AI BOX; same storage key so the choice feels the same on both. */
export type Theme = "claude" | "tech";
export const THEME_KEY = "reach.theme";

/** Runs in <head> before first paint, so the tech theme never flashes white on reload. */
export const THEME_BOOT_SCRIPT = `(function(){try{var t=localStorage.getItem('${THEME_KEY}');if(t)document.documentElement.dataset.theme=t;}catch(e){}})();`;

export function currentTheme(): Theme {
  return typeof document !== "undefined" && document.documentElement.dataset.theme === "tech" ? "tech" : "claude";
}

export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    // private mode: the choice just is not remembered
  }
  window.dispatchEvent(new CustomEvent("themechange", { detail: theme }));
}
