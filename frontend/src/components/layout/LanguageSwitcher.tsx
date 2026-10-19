"use client";

import clsx from "clsx";

import { useI18n } from "@/lib/i18n/I18nProvider";
import { LOCALE_LABELS, LOCALES, type Locale } from "@/lib/i18n/messages";

export function LanguageSwitcher({ className }: { className?: string }) {
  const { locale, setLocale, t } = useI18n();
  return (
    <select
      aria-label={t("common.language")}
      title={t("common.language")}
      value={locale}
      onChange={(e) => setLocale(e.target.value as Locale)}
      className={clsx("field w-auto py-1", className)}
    >
      {LOCALES.map((l) => (
        <option key={l} value={l}>
          {LOCALE_LABELS[l]}
        </option>
      ))}
    </select>
  );
}
