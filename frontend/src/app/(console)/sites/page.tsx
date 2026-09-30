"use client";

import { useState } from "react";

import { SiteForm } from "@/components/sites/SiteForm";
import { Button } from "@/components/ui/Button";
import { DataTable } from "@/components/ui/DataTable";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Modal } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAsync } from "@/hooks/useAsync";
import { useMutation } from "@/hooks/useMutation";
import { sitesApi, type SiteInput } from "@/lib/api/sites";
import { useAuth } from "@/lib/auth/AuthContext";
import type { Site } from "@/types";
import { useI18n } from "@/lib/i18n/I18nProvider";

export default function SitesPage() {
  const { t, formatDateTime } = useI18n();
  const { hasRole } = useAuth();
  const canEdit = hasRole("operator");
  const sites = useAsync(async () => (await sitesApi.list()).items);
  const m = useMutation();
  const [editing, setEditing] = useState<Site | null | "new">(null);

  const save = async (v: SiteInput) => {
    const res = await m.run(() => (editing === "new" ? sitesApi.create(v) : sitesApi.update((editing as Site).id, v)));
    if (res.ok) {
      setEditing(null);
      sites.reload();
    }
  };

  const remove = async (s: Site) => {
    if (!confirm(t("sites.confirmDelete", { name: s.name }))) return;
    if ((await m.run(() => sitesApi.remove(s.id))).ok) sites.reload();
  };

  return (
    <>
      <PageHeader
        title={t("nav.sites")}
        subtitle={t("sites.subtitle")}
        actions={canEdit && <Button onClick={() => setEditing("new")}>{t("sites.new")}</Button>}
      />
      <ErrorBanner error={sites.error ?? m.error} />
      <DataTable
        loading={sites.loading}
        rows={sites.data ?? []}
        columns={[
          { key: "name", header: t("common.name"), render: (s) => <span className="font-medium">{s.name}</span> },
          { key: "code", header: t("sites.siteId"), render: (s) => <code className="text-xs">{s.code}</code> },
          { key: "address", header: t("common.address"), render: (s) => s.address ?? "—" },
          { key: "devices", header: t("sites.edgeDevices"), render: (s) => s.device_count },
          { key: "created", header: t("common.created"), render: (s) => formatDateTime(s.created_at) },
          {
            key: "actions",
            header: "",
            className: "text-right",
            render: (s) =>
              canEdit && (
                <div className="flex justify-end gap-1">
                  <Button variant="ghost" onClick={() => setEditing(s)}>
                    {t("common.edit")}
                  </Button>
                  <Button variant="ghost" onClick={() => remove(s)}>
                    {t("common.delete")}
                  </Button>
                </div>
              ),
          },
        ]}
      />
      <Modal open={editing !== null} title={editing === "new" ? t("sites.newTitle") : t("sites.editTitle")} onClose={() => setEditing(null)}>
        <SiteForm initial={editing === "new" ? null : editing} busy={m.busy} onSubmit={save} />
      </Modal>
    </>
  );
}
