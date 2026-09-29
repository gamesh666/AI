"use client";

import { useRouter } from "next/navigation";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useAuth } from "@/lib/auth/AuthContext";
import { useRealtimeStatus } from "@/lib/realtime/RealtimeProvider";

export function Topbar() {
  const { user, logout } = useAuth();
  const connected = useRealtimeStatus();
  const router = useRouter();

  return (
    <header className="flex h-12 items-center justify-end gap-3 border-b border-slate-800 bg-surface-800 px-5">
      <Badge tone={connected ? "green" : "yellow"}>{connected ? "● live" : "○ reconnecting"}</Badge>
      <span className="text-sm text-slate-300">
        {user?.username} <span className="text-slate-500">({user?.role})</span>
      </span>
      <Button
        variant="ghost"
        onClick={async () => {
          await logout();
          router.replace("/login");
        }}
      >
        Sign out
      </Button>
    </header>
  );
}
