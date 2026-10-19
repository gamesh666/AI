"use client";

import { useEffect, useState } from "react";

import { useI18n } from "@/lib/i18n/I18nProvider";
import { applyTheme, currentTheme, type Theme } from "@/lib/theme";

/** "☀ Claude 色調 | ☾ 科技風" — leftmost in the top bar, same as REACH AI BOX. */
export function ThemeSwitch() {
  const { t } = useI18n();
  const [theme, setTheme] = useState<Theme>("claude");
  useEffect(() => setTheme(currentTheme()), []);

  const pick = (next: Theme) => {
    applyTheme(next);
    setTheme(next);
  };

  return (
    <div className="theme-switch" role="group" aria-label={t("theme.label")}>
      {(["claude", "tech"] as const).map((k) => (
        <button
          key={k}
          type="button"
          data-theme-btn={k}
          aria-pressed={theme === k}
          className={theme === k ? "active" : undefined}
          onClick={() => pick(k)}
        >
          {t(k === "claude" ? "theme.claude" : "theme.tech")}
        </button>
      ))}
    </div>
  );
}
