"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { useAuth } from "@/lib/auth/AuthContext";
import { RealtimeProvider } from "@/lib/realtime/RealtimeProvider";

/** Every page in this group requires a logged-in user and shares one realtime connection. */
export default function ConsoleLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading || !user) {
    return <div className="flex min-h-screen items-center justify-center text-slate-400">Loading…</div>;
  }

  return (
    <RealtimeProvider>
      <AppShell>{children}</AppShell>
    </RealtimeProvider>
  );
}
