"use client";

import { useEffect, useState } from "react";

import { LanguageSwitcher } from "@/components/layout/LanguageSwitcher";
import { ThemeSwitch } from "@/components/layout/ThemeSwitch";
import { Icon } from "@/components/ui/Icon";
import { useAuth } from "@/lib/auth/AuthContext";
import { useRealtimeStatus } from "@/lib/realtime/RealtimeProvider";
import { useI18n } from "@/lib/i18n/I18nProvider";

function Clock() {
  const { formatDateTime } = useI18n();
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return (
    <span className="hidden items-center gap-1.5 whitespace-nowrap text-[13px] text-muted md:inline-flex">
      <Icon name="clock" size={16} />
      {now ? formatDateTime(now.toISOString()) : "--"}
    </span>
  );
}

/** 54px sticky bar: theme switch | live pill | … | clock | user + role. */
export function Topbar({ onMenu }: { onMenu?: () => void }) {
  const { user } = useAuth();
  const connected = useRealtimeStatus();
  const { t, tEnum } = useI18n();

  return (
    <header className="sticky top-0 z-20 flex h-[54px] shrink-0 items-center gap-2 border-b border-line bg-bg px-3 md:gap-3 md:px-[22px]">
      <button
        onClick={onMenu}
        className="rounded-item p-1.5 text-ink2 hover:bg-panel rail:hidden"
        aria-label={t("nav.menu")}
      >
        <Icon name="menu" />
      </button>
      <ThemeSwitch />
      <span className="conn-pill hidden sm:inline-flex" data-state={connected ? "ok" : "warn"}>
        <span className="dot" />
        {connected ? t("topbar.live") : t("topbar.reconnecting")}
      </span>
      <span className="flex-1" />
      <Clock />
      {/* the sidebar's language switch is hidden in rail mode and on phones */}
      <LanguageSwitcher className="hidden max-w-[7.5rem] sm:block wide:hidden" />
      {user && (
        <span className="inline-flex min-w-0 items-center gap-2">
          <span className="avatar">{user.username.slice(0, 1).toUpperCase()}</span>
          <span className="hidden truncate text-[13.5px] font-semibold text-ink sm:inline">{user.username}</span>
          <span className="role-pill hidden sm:inline">{tEnum("role", user.role)}</span>
        </span>
      )}
    </header>
  );
}
