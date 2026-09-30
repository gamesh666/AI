"use client";

import clsx from "clsx";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/lib/auth/AuthContext";
import type { MessageKey } from "@/lib/i18n/messages";
import type { Role } from "@/types";
import { useI18n } from "@/lib/i18n/I18nProvider";

interface NavItem {
  href: string;
  label: MessageKey;
  icon: string;
  minRole?: Role;
}

const NAV: { section: MessageKey; items: NavItem[] }[] = [
  {
    section: "nav.monitoring",
    items: [
      { href: "/dashboard", label: "nav.dashboard", icon: "▦" },
      { href: "/monitor", label: "nav.monitor", icon: "◉" },
      { href: "/events", label: "nav.events", icon: "⚑" },
    ],
  },
  {
    section: "nav.management",
    items: [
      { href: "/sites", label: "nav.sites", icon: "⌂" },
      { href: "/devices", label: "nav.devices", icon: "▣" },
      { href: "/cameras", label: "nav.cameras", icon: "◎" },
      { href: "/models", label: "nav.models", icon: "✦" },
      { href: "/users", label: "nav.users", icon: "☺", minRole: "admin" },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const { hasRole } = useAuth();
  const { t } = useI18n();

  return (
    <aside className="hidden w-56 shrink-0 border-r border-slate-800 bg-surface-800 md:block">
      <div className="px-4 py-4">
        <div className="text-lg font-bold text-white">AI VMS</div>
        <div className="text-xs text-slate-500">{t("app.tagline")}</div>
      </div>
      <nav className="space-y-5 px-2">
        {NAV.map((group) => (
          <div key={group.section}>
            <div className="px-2 pb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              {t(group.section)}
            </div>
            {group.items
              .filter((i) => !i.minRole || hasRole(i.minRole))
              .map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={clsx(
                    "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm",
                    pathname.startsWith(item.href)
                      ? "bg-brand-600/20 text-brand-100"
                      : "text-slate-300 hover:bg-surface-700",
                  )}
                >
                  <span className="w-4 text-center">{item.icon}</span>
                  {t(item.label)}
                </Link>
              ))}
          </div>
        ))}
      </nav>
    </aside>
  );
}
