"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Field, Input } from "@/components/ui/Field";
import { ThemeSwitch } from "@/components/layout/ThemeSwitch";
import { LanguageSwitcher } from "@/components/layout/LanguageSwitcher";
import { useAuth } from "@/lib/auth/AuthContext";
import { IDLE_FLAG_KEY } from "@/components/layout/IdleLogout";
import { IDLE_LOGOUT_MINUTES } from "@/lib/config";
import { errorMessage } from "@/lib/format";
import { useI18n } from "@/lib/i18n/I18nProvider";

export default function LoginPage() {
  const { login, user, loading } = useAuth();
  const router = useRouter();
  const { t } = useI18n();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [idleNotice, setIdleNotice] = useState(false);

  useEffect(() => {
    try {
      const at = Number(localStorage.getItem(IDLE_FLAG_KEY));
      setIdleNotice(Date.now() - at < 5 * 60_000);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    if (!loading && user) router.replace("/dashboard");
  }, [loading, user, router]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(username, password);
      try {
        localStorage.removeItem(IDLE_FLAG_KEY);
      } catch {
        /* ignore */
      }
      router.replace("/dashboard");
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 p-4">
      <ThemeSwitch />
      <form onSubmit={submit} className="card w-full max-w-sm space-y-4 p-6">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h1 className="serif m-0 text-[24px] font-semibold text-ink">
              AIBOX <em className="not-italic text-accent-hi">SERVER</em>
            </h1>
            <p className="text-sm text-muted">{t("app.loginTagline")}</p>
          </div>
          <LanguageSwitcher />
        </div>
        {idleNotice && !error && (
          <div className="notice" data-state="warn">
            {t("login.idleLoggedOut", { n: IDLE_LOGOUT_MINUTES })}
          </div>
        )}
        <ErrorBanner error={error} />
        <Field label={t("common.username")}>
          <Input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required />
        </Field>
        <Field label={t("common.password")}>
          <Input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </Field>
        <Button type="submit" className="w-full" disabled={busy}>
          {busy ? t("login.signingIn") : t("login.signIn")}
        </Button>
      </form>
    </main>
  );
}
