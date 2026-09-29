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
import { formatRelative, pct } from "@/lib/format";
import type { EdgeDevice, EdgeDeviceWithKey } from "@/types";

export default function DevicesPage() {
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
    if (!confirm(`Rotate key for ${d.name}? The agent must be updated with the new key.`)) return;
    const res = await m.run(() => devicesApi.rotateKey(d.id));
    if (res.ok) setRevealed(res.value);
  };

  const remove = async (d: EdgeDevice) => {
    if (!confirm(`Delete ${d.name} and all its cameras/events?`)) return;
    if ((await m.run(() => devicesApi.remove(d.id))).ok) devices.reload();
  };

  return (
    <>
      <PageHeader
        title="Edge Devices"
        subtitle="Live status via heartbeat (every 10 s)"
        actions={canEdit && <Button onClick={() => setEditing("new")}>+ Provision device</Button>}
      />
      <ErrorBanner error={devices.error ?? m.error} />
      <DataTable
        loading={devices.loading}
        rows={devices.data ?? []}
        columns={[
          {
            key: "name",
            header: "Device",
            render: (d) => (
              <div>
                <div className="font-medium">{d.name}</div>
                <div className="text-xs text-slate-500">{d.device_uuid}</div>
              </div>
            ),
          },
          { key: "site", header: "Site", render: (d) => d.site_name ?? "—" },
          { key: "status", header: "Status", render: (d) => <StatusBadge status={d.status} /> },
          { key: "seen", header: "Last seen", render: (d) => formatRelative(d.last_seen) },
          { key: "host", header: "Host / IP", render: (d) => `${d.hostname ?? "—"} / ${d.ip_address ?? "—"}` },
          { key: "cpu", header: "CPU", render: (d) => pct(d.cpu_usage) },
          { key: "mem", header: "Memory", render: (d) => pct(d.memory_usage) },
          {
            key: "gpu",
            header: "GPU",
            render: (d) => (d.gpu_name ? `${d.gpu_name} · ${pct(d.gpu_usage)}` : "—"),
          },
          { key: "temp", header: "Temp", render: (d) => (d.temperature != null ? `${d.temperature.toFixed(0)}°C` : "—") },
          { key: "cams", header: "Cameras", render: (d) => d.camera_count },
          { key: "ver", header: "Agent", render: (d) => d.agent_version ?? "—" },
          {
            key: "actions",
            header: "",
            className: "text-right",
            render: (d) =>
              canEdit && (
                <div className="flex justify-end gap-1">
                  <Button variant="ghost" onClick={() => m.run(() => devicesApi.command(d.id, "reload_config"))}>
                    Reload
                  </Button>
                  <Button variant="ghost" onClick={() => setEditing(d)}>
                    Edit
                  </Button>
                  {isAdmin && (
                    <Button variant="ghost" onClick={() => rotate(d)}>
                      Rotate key
                    </Button>
                  )}
                  <Button variant="ghost" onClick={() => remove(d)}>
                    Delete
                  </Button>
                </div>
              ),
          },
        ]}
      />
      <Modal
        open={editing !== null}
        title={editing === "new" ? "Provision edge device" : "Edit edge device"}
        onClose={() => setEditing(null)}
      >
        <DeviceForm
          initial={editing === "new" ? null : editing}
          sites={sites.data ?? []}
          busy={m.busy}
          onSubmit={save}
        />
      </Modal>
      <Modal open={!!revealed} title="Device credentials" onClose={() => setRevealed(null)}>
        {revealed && <ApiKeyReveal device={revealed} onClose={() => setRevealed(null)} />}
      </Modal>
    </>
  );
}
