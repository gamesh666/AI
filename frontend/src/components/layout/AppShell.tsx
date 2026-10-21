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
        <main className="flex-1 px-4 pb-10 pt-4 sm:px-6 sm:pt-[22px]">{children}</main>
      </div>
      <IdleLogout />
    </div>
  );
}
