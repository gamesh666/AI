"use client";

import { useRouter } from "next/navigation";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { LanguageSwitcher } from "@/components/layout/LanguageSwitcher";
import { useAuth } from "@/lib/auth/AuthContext";
import { useRealtimeStatus } from "@/lib/realtime/RealtimeProvider";
import { useI18n } from "@/lib/i18n/I18nProvider";

export function Topbar() {
  const { user, logout } = useAuth();
  const connected = useRealtimeStatus();
  const router = useRouter();
  const { t, tEnum } = useI18n();

  return (
    <header className="flex h-12 items-center justify-end gap-3 border-b border-slate-800 bg-surface-800 px-5">
      <Badge tone={connected ? "green" : "yellow"}>{connected ? t("topbar.live") : t("topbar.reconnecting")}</Badge>
      <span className="text-sm text-slate-300">
        {user?.username} <span className="text-slate-500">({user ? tEnum("role", user.role) : ""})</span>
      </span>
      <LanguageSwitcher />
      <Button
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
