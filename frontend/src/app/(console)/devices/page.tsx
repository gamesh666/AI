"use client";

import { useState } from "react";

import { ApiKeyReveal } from "@/components/devices/ApiKeyReveal";
import { DeviceForm } from "@/components/devices/DeviceForm";
import { StatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { DataTable } from "@/components/ui/DataTable";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Modal } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAsync } from "@/hooks/useAsync";
import { useLiveDevices } from "@/hooks/useLiveDevices";
import { useMutation } from "@/hooks/useMutation";
import { devicesApi, type DeviceInput } from "@/lib/api/devices";
import { sitesApi } from "@/lib/api/sites";
import { useAuth } from "@/lib/auth/AuthContext";
import { pct } from "@/lib/format";
import type { EdgeDevice, EdgeDeviceWithKey } from "@/types";
import { useI18n } from "@/lib/i18n/I18nProvider";

export default function DevicesPage() {
  const { t, formatRelative } = useI18n();
  const { hasRole } = useAuth();
  const canEdit = hasRole("operator");
  const isAdmin = hasRole("admin");
  const devices = useLiveDevices();
  const sites = useAsync(async () => (await sitesApi.list()).items);
  const m = useMutation();
  const [editing, setEditing] = useState<EdgeDevice | null | "new">(null);
  const [revealed, setRevealed] = useState<EdgeDeviceWithKey | null>(null);

  const save = async (v: DeviceInput) => {
    if (editing === "new") {
      const res = await m.run(() => devicesApi.create(v));
      if (!res.ok) return;
      setRevealed(res.value);
    } else if (editing) {
      const res = await m.run(() => devicesApi.update(editing.id, { name: v.name, site_id: v.site_id }));
      if (!res.ok) return;
    }
    setEditing(null);
    devices.reload();
  };

  const rotate = async (d: EdgeDevice) => {
    if (!confirm(t("devices.confirmRotate", { name: d.name }))) return;
    const res = await m.run(() => devicesApi.rotateKey(d.id));
    if (res.ok) setRevealed(res.value);
  };

  const remove = async (d: EdgeDevice) => {
    if (!confirm(t("devices.confirmDelete", { name: d.name }))) return;
    if ((await m.run(() => devicesApi.remove(d.id))).ok) devices.reload();
  };

  return (
    <>
      <PageHeader
        title={t("nav.devices")}
        subtitle={t("devices.subtitle")}
        actions={canEdit && <Button onClick={() => setEditing("new")}>{t("devices.provision")}</Button>}
      />
      <ErrorBanner error={devices.error ?? m.error} />
      <DataTable
        loading={devices.loading}
        rows={devices.data ?? []}
        columns={[
          {
            key: "name",
            header: t("devices.device"),
            render: (d) => (
              <div>
                <div className="font-medium">{d.name}</div>
                <div className="text-xs text-slate-500">{d.device_uuid}</div>
              </div>
            ),
          },
          { key: "site", header: t("common.site"), render: (d) => d.site_name ?? "—" },
          { key: "status", header: t("devices.status"), render: (d) => <StatusBadge status={d.status} /> },
          { key: "seen", header: t("devices.lastSeen"), render: (d) => formatRelative(d.last_seen) },
          { key: "host", header: t("devices.host"), render: (d) => `${d.hostname ?? "—"} / ${d.ip_address ?? "—"}` },
          { key: "cpu", header: "CPU", render: (d) => pct(d.cpu_usage) },
          { key: "mem", header: t("devices.memory"), render: (d) => pct(d.memory_usage) },
          {
            key: "gpu",
            header: "GPU",
            render: (d) => (d.gpu_name ? `${d.gpu_name} · ${pct(d.gpu_usage)}` : "—"),
          },
          { key: "temp", header: t("devices.temp"), render: (d) => (d.temperature != null ? `${d.temperature.toFixed(0)}°C` : "—") },
          { key: "cams", header: t("common.cameras"), render: (d) => d.camera_count },
          { key: "ver", header: t("devices.agent"), render: (d) => d.agent_version ?? "—" },
          {
            key: "actions",
            header: "",
            className: "text-right",
            render: (d) =>
              canEdit && (
                <div className="flex justify-end gap-1">
                  <Button variant="ghost" onClick={() => m.run(() => devicesApi.command(d.id, "reload_config"))}>
                    {t("devices.reload")}
                  </Button>
                  <Button variant="ghost" onClick={() => setEditing(d)}>
                    {t("common.edit")}
                  </Button>
                  {isAdmin && (
                    <Button variant="ghost" onClick={() => rotate(d)}>
                      {t("devices.rotateKey")}
                    </Button>
                  )}
                  <Button variant="ghost" onClick={() => remove(d)}>
                    {t("common.delete")}
                  </Button>
                </div>
              ),
          },
        ]}
      />
      <Modal
        open={editing !== null}
        title={editing === "new" ? t("devices.provisionTitle") : t("devices.editTitle")}
        onClose={() => setEditing(null)}
      >
        <DeviceForm
          initial={editing === "new" ? null : editing}
          sites={sites.data ?? []}
          busy={m.busy}
          onSubmit={save}
        />
      </Modal>
      <Modal open={!!revealed} title={t("devices.credentialsTitle")} onClose={() => setRevealed(null)}>
        {revealed && <ApiKeyReveal device={revealed} onClose={() => setRevealed(null)} />}
      </Modal>
    </>
  );
}
