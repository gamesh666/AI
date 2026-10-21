"use client";

import clsx from "clsx";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { LanguageSwitcher } from "@/components/layout/LanguageSwitcher";
import { Icon, type IconName } from "@/components/ui/Icon";
import { useAuth } from "@/lib/auth/AuthContext";
import type { MessageKey } from "@/lib/i18n/messages";
import type { Role } from "@/types";
import { useI18n } from "@/lib/i18n/I18nProvider";

interface NavItem {
  href: string;
  label: MessageKey;
  icon: IconName;
  minRole?: Role;
}

const NAV: { section: MessageKey; items: NavItem[] }[] = [
  {
    section: "nav.monitoring",
    items: [
      { href: "/dashboard", label: "nav.dashboard", icon: "dashboard" },
      { href: "/monitor", label: "nav.monitor", icon: "monitor" },
      { href: "/logs", label: "nav.logs", icon: "logs" },
    ],
  },
  {
    section: "nav.management",
    items: [
      { href: "/owners", label: "nav.owners", icon: "owners", minRole: "operator" },
      { href: "/sites", label: "nav.sites", icon: "sites" },
      { href: "/devices", label: "nav.devices", icon: "devices" },
      { href: "/cameras", label: "nav.cameras", icon: "cameras" },
      { href: "/models", label: "nav.models", icon: "models" },
      { href: "/users", label: "nav.users", icon: "users", minRole: "admin" },
    ],
  },
];

const VERSION = process.env.NEXT_PUBLIC_APP_VERSION ?? "0.1.0";

/**
 * 220px column (≥1101px), 64px icon rail (768–1100px), slide-in drawer on phones.
 * Language switch and sign-out sit together at the bottom.
 */
export function Sidebar({ open = false, onClose }: { open?: boolean; onClose?: () => void }) {
  const pathname = usePathname();
  const router = useRouter();
  const { hasRole, logout } = useAuth();
  const { t } = useI18n();
  const [host, setHost] = useState("");
  useEffect(() => setHost(window.location.hostname), []);
  // labels show in the drawer (phones) and the full column; the 768–1100px rail is icons only
  const label = "rail:hidden wide:inline";
  const block = "rail:hidden wide:block";

  return (
    <>
      {open && <div className="backdrop fixed inset-0 z-40 rail:hidden" onClick={onClose} />}
      <aside
        className={clsx(
          "flex shrink-0 flex-col border-r border-line bg-side px-3 pb-3.5 pt-[18px]",
          open ? "fixed inset-y-0 left-0 z-50 w-[220px] overflow-y-auto" : "hidden",
          "rail:sticky rail:top-0 rail:flex rail:h-screen rail:w-16 rail:overflow-y-auto rail:px-2 wide:w-[220px] wide:px-3",
        )}
      >
        <div className="px-2 pb-2">
          <div className={clsx("serif text-[21px] font-semibold leading-tight text-ink", block)}>
            AIBOX <em className="not-italic text-accent-hi">SERVER</em>
          </div>
          <div className="serif hidden text-center text-[17px] font-semibold text-accent-hi rail:block wide:hidden">AI</div>
          <div className={clsx("mt-0.5 text-xs text-muted", block)}>{t("app.tagline")}</div>
        </div>
        <nav className="flex-1">
          {NAV.map((group) => (
            <div key={group.section}>
              <div className={clsx("nav-group", block)}>{t(group.section)}</div>
              {group.items
                .filter((i) => !i.minRole || hasRole(i.minRole))
                .map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    title={t(item.label)}
                    aria-current={pathname.startsWith(item.href) ? "page" : undefined}
                    className="nav-item mb-0.5 rail:justify-center wide:justify-start"
                  >
                    <Icon name={item.icon} className="shrink-0" />
                    <span className={clsx("truncate", label)}>{t(item.label)}</span>
                  </Link>
                ))}
            </div>
          ))}
        </nav>
        <div className="mt-4 space-y-2">
          <LanguageSwitcher className={clsx("w-full", block)} />
          <button
            type="button"
            className="logout-btn"
            title={t("topbar.signOut")}
            onClick={async () => {
              await logout();
              router.replace("/login");
            }}
          >
            <Icon name="logout" />
            <span className={label}>{t("topbar.signOut")}</span>
          </button>
          <div className={clsx("border-t border-line pt-2 text-[11px] leading-relaxed text-faint", block)}>
            <div>v{VERSION} · AIBOX SERVER</div>
            {host && <div className="truncate">{t("shell.host", { host })}</div>}
          </div>
        </div>
      </aside>
    </>
  );
}
