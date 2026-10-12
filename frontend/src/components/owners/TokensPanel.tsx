"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Field, Input, Select } from "@/components/ui/Field";
import { useAsync } from "@/hooks/useAsync";
import { useMutation } from "@/hooks/useMutation";
import { API_BASE } from "@/lib/config";
import { copyText } from "@/lib/clipboard";
import { ownersApi, type TokenInput } from "@/lib/api/owners";
import { useI18n } from "@/lib/i18n/I18nProvider";
import type { Owner, ProvisioningTokenCreated, Site } from "@/types";

const STATE_TONE = { active: "green", revoked: "gray", expired: "yellow" } as const;

/** Provisioning tokens of one owner: the factory token an edge uses to register itself (shown once). */
export function TokensPanel({ owner, sites }: { owner: Owner; sites: Site[] }) {
  const { t, formatDateTime } = useI18n();
  const tokens = useAsync(() => ownersApi.tokens(owner.id), [owner.id]);
  const m = useMutation();
  const [created, setCreated] = useState<ProvisioningTokenCreated | null>(null);
  const [copied, setCopied] = useState(false);
  const [v, setV] = useState({ label: "", site_id: "", device_prefix: "REACH", max_devices: "", expires: "" });
  const ownerSites = sites.filter((s) => s.owner_id === owner.id);

  const create = async (e: React.FormEvent) => {
    e.preventDefault();
    const body: TokenInput = {
      label: v.label || null,
      site_id: v.site_id || null,
      device_prefix: v.device_prefix,
      max_devices: v.max_devices ? Number(v.max_devices) : null,
      expires_at: v.expires ? new Date(`${v.expires}T23:59:59`).toISOString() : null,
    };
    const res = await m.run(() => ownersApi.createToken(owner.id, body));
    if (res.ok) {
      setCreated(res.value);
      setCopied(false);
      tokens.reload();
    }
  };

  const revoke = async (id: string) => {
    if (!confirm(t("tokens.confirmRevoke"))) return;
    if ((await m.run(() => ownersApi.revokeToken(id))).ok) tokens.reload();
  };

  const snippet = created
    ? `AIVMS_API_URL=${API_BASE.replace(/\/api\/v1$/, "")}\nAIVMS_PROVISIONING_TOKEN=${created.token}\n`
    : "";

  return (
    <div className="space-y-4 text-sm">
      <ErrorBanner error={tokens.error ?? m.error} />
      <p className="text-xs text-slate-400">{t("tokens.hint")}</p>

      {created && (
        <div className="space-y-2 rounded-md border border-amber-500/40 bg-amber-500/10 p-3">
          <p className="text-amber-200">{t("tokens.copyNow")}</p>
          <textarea
            readOnly
            rows={2}
            value={snippet}
            onFocus={(e) => e.currentTarget.select()}
            className="w-full rounded bg-surface-900 p-2 font-mono text-xs"
          />
          <Button variant="secondary" onClick={async () => setCopied(await copyText(snippet))}>
            {copied ? t("sheet.copied") : t("sheet.copyAll")}
          </Button>
        </div>
      )}

      <ul className="divide-y divide-slate-800 rounded border border-slate-700/60">
        {(tokens.data ?? []).length === 0 && <li className="px-3 py-4 text-center text-slate-500">{t("tokens.none")}</li>}
        {tokens.data?.map((tk) => (
          <li key={tk.id} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <code className="text-xs">{tk.token_prefix}…</code>
                <Badge tone={STATE_TONE[tk.state]}>{t(`tokens.state.${tk.state}`)}</Badge>
                {tk.label && <span className="text-slate-300">{tk.label}</span>}
              </div>
              <div className="text-xs text-slate-500">
                {t("tokens.summary", {
                  site: tk.site_name ?? t("common.noSite"),
                  prefix: tk.device_prefix,
                  used: tk.used_devices,
                  max: tk.max_devices ?? "∞",
                })}
                {tk.expires_at && ` · ${t("tokens.expires", { time: formatDateTime(tk.expires_at) })}`}
              </div>
            </div>
            {tk.state === "active" && (
              <Button variant="ghost" onClick={() => revoke(tk.id)}>
                {t("tokens.revoke")}
              </Button>
            )}
          </li>
        ))}
      </ul>

      <form onSubmit={create} className="space-y-3 rounded border border-slate-700/60 p-3">
        <div className="text-xs font-semibold uppercase text-slate-400">{t("tokens.new")}</div>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label={t("tokens.label")}>
            <Input maxLength={128} value={v.label} onChange={(e) => setV({ ...v, label: e.target.value })} />
          </Field>
          <Field label={t("common.site")} hint={t("tokens.siteHint")}>
            <Select value={v.site_id} onChange={(e) => setV({ ...v, site_id: e.target.value })}>
              <option value="">{t("common.none")}</option>
              {ownerSites.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("tokens.devicePrefix")} hint={t("tokens.devicePrefixHint")}>
            <Input
              required
              pattern="[A-Za-z][A-Za-z0-9_\-]{0,15}"
              value={v.device_prefix}
              onChange={(e) => setV({ ...v, device_prefix: e.target.value })}
            />
          </Field>
          <Field label={t("tokens.maxDevices")} hint={t("tokens.maxDevicesHint")}>
            <Input type="number" min={1} value={v.max_devices} onChange={(e) => setV({ ...v, max_devices: e.target.value })} />
          </Field>
          <Field label={t("tokens.expiresAt")} hint={t("tokens.expiresHint")}>
            <Input type="date" value={v.expires} onChange={(e) => setV({ ...v, expires: e.target.value })} />
          </Field>
        </div>
        <Button type="submit" disabled={m.busy}>
          {t("tokens.create")}
        </Button>
      </form>
    </div>
  );
}
