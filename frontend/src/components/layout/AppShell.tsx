"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { IdleLogout } from "@/components/layout/IdleLogout";
import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [navOpen, setNavOpen] = useState(false);
  const pathname = usePathname();
  useEffect(() => setNavOpen(false), [pathname]);

  return (
    <div className="flex min-h-screen">
      <Sidebar open={navOpen} onClose={() => setNavOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onMenu={() => setNavOpen(true)} />
        <main className="flex-1 p-3 md:p-5">{children}</main>
      </div>
      <IdleLogout />
    </div>
  );
}
