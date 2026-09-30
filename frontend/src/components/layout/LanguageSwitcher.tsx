"use client";

import { useI18n } from "@/lib/i18n/I18nProvider";
import { LOCALE_LABELS, LOCALES, type Locale } from "@/lib/i18n/messages";

export function LanguageSwitcher() {
  const { locale, setLocale, t } = useI18n();
  return (
    <select
      aria-label={t("common.language")}
      title={t("common.language")}
      value={locale}
      onChange={(e) => setLocale(e.target.value as Locale)}
      className="rounded-md border border-slate-600 bg-surface-900 px-2 py-1 text-sm text-slate-200 focus:border-brand-500 focus:outline-none"
    >
      {LOCALES.map((l) => (
        <option key={l} value={l}>
          {LOCALE_LABELS[l]}
        </option>
      ))}
    </select>
  );
}
