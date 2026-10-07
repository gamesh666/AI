"use client";

import { useRouter } from "next/navigation";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { LanguageSwitcher } from "@/components/layout/LanguageSwitcher";
import { useAuth } from "@/lib/auth/AuthContext";
import { useRealtimeStatus } from "@/lib/realtime/RealtimeProvider";
import { useI18n } from "@/lib/i18n/I18nProvider";

export function Topbar({ onMenu }: { onMenu?: () => void }) {
  const { user, logout } = useAuth();
  const connected = useRealtimeStatus();
  const router = useRouter();
  const { t, tEnum } = useI18n();

  return (
    <header className="flex h-12 shrink-0 items-center gap-2 border-b border-slate-800 bg-surface-800 px-3 md:gap-3 md:px-5">
      <button
        onClick={onMenu}
        className="rounded px-2 py-1 text-lg text-slate-300 hover:bg-surface-700 md:hidden"
        aria-label={t("nav.menu")}
      >
        ☰
      </button>
      <span className="flex-1" />
      <Badge tone={connected ? "green" : "yellow"}>{connected ? t("topbar.live") : t("topbar.reconnecting")}</Badge>
      <span className="hidden whitespace-nowrap text-sm text-slate-300 sm:inline">
        {user?.username} <span className="text-slate-500">({user ? tEnum("role", user.role) : ""})</span>
      </span>
      <LanguageSwitcher />
      <Button
        className="whitespace-nowrap"
        variant="ghost"
        onClick={async () => {
          await logout();
          router.replace("/login");
        }}
      >
        {t("topbar.signOut")}
      </Button>
    </header>
  );
}
