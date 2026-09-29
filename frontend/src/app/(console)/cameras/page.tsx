"use client";

import { useState } from "react";

import { CameraForm } from "@/components/camera/CameraForm";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { DataTable } from "@/components/ui/DataTable";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Modal } from "@/components/ui/Modal";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAsync } from "@/hooks/useAsync";
import { useMutation } from "@/hooks/useMutation";
import { camerasApi, type CameraInput } from "@/lib/api/cameras";
import { devicesApi } from "@/lib/api/devices";
import { modelsApi } from "@/lib/api/models";
import { useAuth } from "@/lib/auth/AuthContext";
import { useRealtime } from "@/lib/realtime/RealtimeProvider";
import type { Camera, CameraStatusMessage } from "@/types";

export default function CamerasPage() {
  const { hasRole } = useAuth();
  const canEdit = hasRole("operator");
  const cameras = useAsync(async () => (await camerasApi.list()).items);
  const devices = useAsync(async () => (await devicesApi.list()).items);
  const models = useAsync(async () => (await modelsApi.list()).items);
  const m = useMutation();
  const [editing, setEditing] = useState<Camera | null | "new">(null);

  useRealtime<CameraStatusMessage>("camera.status", (msg) =>
    cameras.setData((prev) => prev?.map((c) => (c.id === msg.camera_id ? { ...c, status: msg.status } : c)) ?? prev),
  );

  const save = async (body: Partial<CameraInput>) => {
    const res = await m.run(() =>
      editing === "new" ? camerasApi.create(body as CameraInput) : camerasApi.update((editing as Camera).id, body),
    );
    if (res.ok) {
      setEditing(null);
      cameras.reload();
    }
  };

  const remove = async (c: Camera) => {
    if (!confirm(`Delete camera "${c.name}"?`)) return;
    if ((await m.run(() => camerasApi.remove(c.id))).ok) cameras.reload();
  };

  return (
    <>
      <PageHeader
        title="Cameras"
        subtitle="RTSP / ONVIF cameras attached to edge devices"
        actions={
          canEdit && (
            <Button onClick={() => setEditing("new")} disabled={!devices.data?.length}>
              + Add camera
            </Button>
          )
        }
      />
      <ErrorBanner error={cameras.error ?? m.error} />
      <DataTable
        loading={cameras.loading}
        rows={cameras.data ?? []}
        columns={[
          { key: "name", header: "Name", render: (c) => <span className="font-medium">{c.name}</span> },
          { key: "site", header: "Site", render: (c) => c.site_name ?? "—" },
          { key: "device", header: "Edge device", render: (c) => c.edge_device_name ?? "—" },
          {
            key: "rtsp",
            header: "RTSP",
            render: (c) => (
              <span className="font-mono text-xs text-slate-400">
                {c.rtsp_url_masked} {c.has_credentials && <Badge>🔒 auth</Badge>}
              </span>
            ),
          },
          { key: "stream", header: "Stream ID", render: (c) => <code className="text-xs">{c.stream_id}</code> },
          { key: "status", header: "Status", render: (c) => <StatusBadge status={c.enabled ? c.status : "disabled"} /> },
          {
            key: "ai",
            header: "AI",
            render: (c) => <Badge tone={c.ai_enabled ? "blue" : "gray"}>{c.ai_enabled ? (c.ai_model_name ?? "on") : "off"}</Badge>,
          },
          {
            key: "actions",
            header: "",
            className: "text-right",
            render: (c) =>
              canEdit && (
                <div className="flex justify-end gap-1">
                  <Button variant="ghost" onClick={() => setEditing(c)}>
                    Edit
                  </Button>
                  <Button variant="ghost" onClick={() => remove(c)}>
                    Delete
                  </Button>
                </div>
              ),
          },
        ]}
      />
      <Modal open={editing !== null} title={editing === "new" ? "Add camera" : "Edit camera"} onClose={() => setEditing(null)}>
        <CameraForm
          initial={editing === "new" ? null : editing}
          devices={devices.data ?? []}
          models={models.data ?? []}
          busy={m.busy}
          onSubmit={save}
        />
      </Modal>
    </>
  );
}
