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
import { formatDateTime } from "@/lib/format";
import type { Site } from "@/types";

export default function SitesPage() {
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
    if (!confirm(`Delete site "${s.name}"? Devices will be unassigned.`)) return;
    if ((await m.run(() => sitesApi.remove(s.id))).ok) sites.reload();
  };

  return (
    <>
      <PageHeader
        title="Sites"
        subtitle="Physical locations hosting edge devices"
        actions={canEdit && <Button onClick={() => setEditing("new")}>+ New site</Button>}
      />
      <ErrorBanner error={sites.error ?? m.error} />
      <DataTable
        loading={sites.loading}
        rows={sites.data ?? []}
        columns={[
          { key: "name", header: "Name", render: (s) => <span className="font-medium">{s.name}</span> },
          { key: "code", header: "Site ID", render: (s) => <code className="text-xs">{s.code}</code> },
          { key: "address", header: "Address", render: (s) => s.address ?? "—" },
          { key: "devices", header: "Edge devices", render: (s) => s.device_count },
          { key: "created", header: "Created", render: (s) => formatDateTime(s.created_at) },
          {
            key: "actions",
            header: "",
            className: "text-right",
            render: (s) =>
              canEdit && (
                <div className="flex justify-end gap-1">
                  <Button variant="ghost" onClick={() => setEditing(s)}>
                    Edit
                  </Button>
                  <Button variant="ghost" onClick={() => remove(s)}>
                    Delete
                  </Button>
                </div>
              ),
          },
        ]}
      />
      <Modal open={editing !== null} title={editing === "new" ? "New site" : "Edit site"} onClose={() => setEditing(null)}>
        <SiteForm initial={editing === "new" ? null : editing} busy={m.busy} onSubmit={save} />
      </Modal>
    </>
  );
}
