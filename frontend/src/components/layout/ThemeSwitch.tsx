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
    <div className="inline-flex items-center gap-2">
      <span className="hidden whitespace-nowrap text-[13px] font-semibold text-muted sm:inline">{t("theme.label")}</span>
      <div className="theme-switch" role="group" aria-label={t("theme.label")}>
        {(["claude", "tech"] as const).map((k) => {
          const name = t(k === "claude" ? "theme.claude" : "theme.tech");
          return (
            <button
              key={k}
              type="button"
              data-theme-btn={k}
              aria-pressed={theme === k}
              aria-label={name}
              title={name}
              className={theme === k ? "active !px-2.5" : "!px-2.5"}
              onClick={() => pick(k)}
            >
              {k === "claude" ? "☀" : "☾"}
            </button>
          );
        })}
      </div>
    </div>
  );
}
