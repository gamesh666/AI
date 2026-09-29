"use client";

import { useState } from "react";

import { CameraForm } from "@/components/camera/CameraForm";
import { CameraHealth } from "@/components/camera/CameraHealth";
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
import { applyCameraStatus } from "@/lib/cameraStatus";
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
    cameras.setData((prev) => prev?.map((c) => applyCameraStatus(c, msg)) ?? prev),
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
        subtitle="Identified by site / edge device / camera ID — camera addresses stay on the edge"
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
          {
            key: "name",
            header: "Camera",
            render: (c) => (
              <div>
                <div className="font-medium">{c.name}</div>
                <div className="text-xs text-slate-500">
                  {c.code} {c.has_credentials && "· 🔒"}
                </div>
              </div>
            ),
          },
          { key: "site", header: "Site / Edge", render: (c) => `${c.site_name ?? "—"} / ${c.edge_device_name ?? "—"}` },
          { key: "path", header: "Stream path", render: (c) => <code className="text-xs">{c.stream_path}</code> },
          {
            key: "video",
            header: "Stream / AI",
            render: (c) => (
              <span className="text-xs text-slate-400">
                {c.resolution ?? "source"} @ {c.stream_fps} fps · {c.bitrate} · AI {c.inference_fps} fps
              </span>
            ),
          },
          { key: "health", header: "Health", render: (c) => (c.enabled ? <CameraHealth camera={c} /> : "disabled") },
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
