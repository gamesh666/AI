"use client";

import clsx from "clsx";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { useAuth } from "@/lib/auth/AuthContext";
import type { Role } from "@/types";

interface NavItem {
  href: string;
  label: string;
  icon: string;
  minRole?: Role;
}

const NAV: { section: string; items: NavItem[] }[] = [
  {
    section: "Monitoring",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: "▦" },
      { href: "/monitor", label: "Camera Monitor", icon: "◉" },
      { href: "/events", label: "Detection Events", icon: "⚑" },
    ],
  },
  {
    section: "Management",
    items: [
      { href: "/sites", label: "Sites", icon: "⌂" },
      { href: "/devices", label: "Edge Devices", icon: "▣" },
      { href: "/cameras", label: "Cameras", icon: "◎" },
      { href: "/models", label: "AI Models", icon: "✦" },
      { href: "/users", label: "Users", icon: "☺", minRole: "admin" },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const { hasRole } = useAuth();

  return (
    <aside className="hidden w-56 shrink-0 border-r border-slate-800 bg-surface-800 md:block">
      <div className="px-4 py-4">
        <div className="text-lg font-bold text-white">AI VMS</div>
        <div className="text-xs text-slate-500">Edge Video Intelligence</div>
      </div>
      <nav className="space-y-5 px-2">
        {NAV.map((group) => (
          <div key={group.section}>
            <div className="px-2 pb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              {group.section}
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
                  {item.label}
                </Link>
              ))}
          </div>
        ))}
      </nav>
    </aside>
  );
}
