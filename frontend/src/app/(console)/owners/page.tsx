"use client";

import { useState } from "react";

import { OwnerForm } from "@/components/owners/OwnerForm";
import { TokensPanel } from "@/components/owners/TokensPanel";
import { Button } from "@/components/ui/Button";
import { DataTable } from "@/components/ui/DataTable";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Modal } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAsync } from "@/hooks/useAsync";
import { useMutation } from "@/hooks/useMutation";
import { ownersApi, type OwnerInput } from "@/lib/api/owners";
import { sitesApi } from "@/lib/api/sites";
import { useAuth } from "@/lib/auth/AuthContext";
import { useI18n } from "@/lib/i18n/I18nProvider";
import type { Owner } from "@/types";

export default function OwnersPage() {
  const { t } = useI18n();
  const { hasRole } = useAuth();
  const isAdmin = hasRole("admin");
  const owners = useAsync(ownersApi.list);
  const sites = useAsync(async () => (await sitesApi.list()).items);
  const m = useMutation();
  const [editing, setEditing] = useState<Owner | null | "new">(null);
  const [tokensOf, setTokensOf] = useState<Owner | null>(null);

  const save = async (v: OwnerInput) => {
    const res = await m.run(() => (editing === "new" ? ownersApi.create(v) : ownersApi.update((editing as Owner).id, v)));
    if (res.ok) {
      setEditing(null);
      owners.reload();
    }
  };

  const remove = async (o: Owner) => {
    if (!confirm(t("owners.confirmDelete", { name: o.name }))) return;
    if ((await m.run(() => ownersApi.remove(o.id))).ok) owners.reload();
  };

  return (
    <>
      <PageHeader
        title={t("nav.owners")}
        subtitle={t("owners.subtitle")}
        actions={isAdmin && <Button onClick={() => setEditing("new")}>{t("owners.new")}</Button>}
      />
      <ErrorBanner error={owners.error ?? m.error} />
      <DataTable
        loading={owners.loading}
        rows={owners.data ?? []}
        columns={[
          {
            key: "name",
            header: t("owners.name"),
            render: (o) => (
              <div>
                <div className="font-medium">{o.name}</div>
                <div className="text-xs text-slate-500">{o.company_name ?? "—"}</div>
              </div>
            ),
          },
          { key: "tax", header: t("owners.taxId"), render: (o) => o.tax_id ?? "—" },
          {
            key: "contact",
            header: t("owners.contactName"),
            render: (o) => (
              <div className="text-xs">
                <div>{o.contact_name ?? "—"}</div>
                <div className="text-slate-500">{o.contact_phone ?? o.company_phone ?? ""}</div>
              </div>
            ),
          },
          {
            key: "usage",
            header: t("owners.usage"),
            render: (o) => (
              <span className="text-xs text-slate-400">
                {t("owners.counts", { sites: o.site_count, devices: o.device_count, tokens: o.token_count })}
              </span>
            ),
          },
          {
            key: "actions",
            header: "",
            className: "text-right",
            render: (o) =>
              isAdmin && (
                <div className="flex justify-end gap-1">
                  <Button variant="ghost" onClick={() => setTokensOf(o)}>
                    {t("owners.tokens")}
                  </Button>
                  <Button variant="ghost" onClick={() => setEditing(o)}>
                    {t("common.edit")}
                  </Button>
                  <Button variant="ghost" onClick={() => remove(o)}>
                    {t("common.delete")}
                  </Button>
                </div>
              ),
          },
        ]}
      />
      <Modal
        open={editing !== null}
        wide
        title={editing === "new" ? t("owners.newTitle") : t("owners.editTitle")}
        onClose={() => setEditing(null)}
      >
        <OwnerForm initial={editing === "new" ? null : editing} busy={m.busy} onSubmit={save} />
      </Modal>
      <Modal
        open={!!tokensOf}
        wide
        title={tokensOf ? t("owners.tokensTitle", { name: tokensOf.name }) : ""}
        onClose={() => (setTokensOf(null), owners.reload())}
      >
        {tokensOf && <TokensPanel owner={tokensOf} sites={sites.data ?? []} />}
      </Modal>
    </>
  );
}
