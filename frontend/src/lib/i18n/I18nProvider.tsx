"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { DEFAULT_LOCALE, LOCALES, MESSAGES, type Locale, type MessageKey } from "@/lib/i18n/messages";

const STORAGE_KEY = "aivms.locale";

type Vars = Record<string, string | number>;

interface I18nState {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: MessageKey, vars?: Vars) => string;
  /** Translate a backend enum value (status / role); unknown values are shown as-is. */
  tEnum: (prefix: "status" | "role", value: string) => string;
  formatDateTime: (iso: string | null | undefined) => string;
  formatRelative: (iso: string | null | undefined) => string;
}

const I18nContext = createContext<I18nState | null>(null);

function isLocale(v: unknown): v is Locale {
  return typeof v === "string" && (LOCALES as readonly string[]).includes(v);
}

function interpolate(s: string, vars?: Vars): string {
  return vars ? s.replace(/\{(\w+)\}/g, (m, k: string) => (k in vars ? String(vars[k]) : m)) : s;
}

/** UI language: remembered per browser (localStorage), default Traditional Chinese. */
export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (isLocale(saved)) setLocaleState(saved);
    } catch {
      /* storage unavailable: keep default */
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    try {
      localStorage.setItem(STORAGE_KEY, l);
    } catch {
      /* ignore */
    }
  }, []);

  const value = useMemo<I18nState>(() => {
    const messages = MESSAGES[locale];
    const t = (key: MessageKey, vars?: Vars) => interpolate(messages[key] ?? key, vars);
    const tEnum = (prefix: "status" | "role", v: string) => {
      const key = `${prefix}.${v}` as MessageKey;
      return key in messages ? messages[key] : v;
    };
    return {
      locale,
      setLocale,
      t,
      tEnum,
      formatDateTime: (iso) => (iso ? new Date(iso).toLocaleString(locale) : "—"),
      formatRelative: (iso) => {
        if (!iso) return t("time.never");
        const diff = (Date.now() - new Date(iso).getTime()) / 1000;
        if (diff < 60) return t("time.secondsAgo", { n: Math.max(0, Math.round(diff)) });
        if (diff < 3600) return t("time.minutesAgo", { n: Math.round(diff / 60) });
        if (diff < 86400) return t("time.hoursAgo", { n: Math.round(diff / 3600) });
        return t("time.daysAgo", { n: Math.round(diff / 86400) });
      },
    };
  }, [locale, setLocale]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nState {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used inside <I18nProvider>");
  return ctx;
}
