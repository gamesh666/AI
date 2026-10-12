"use client";

import { useState } from "react";

import { CameraForm } from "@/components/camera/CameraForm";
import { CameraHealth } from "@/components/camera/CameraHealth";
import { Badge } from "@/components/ui/Badge";
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
import { useI18n } from "@/lib/i18n/I18nProvider";

export default function CamerasPage() {
  const { t, formatDateTime } = useI18n();
  const { hasRole } = useAuth();
  const canEdit = hasRole("operator");
  const cameras = useAsync(async () => (await camerasApi.list()).items);
  const devices = useAsync(async () => (await devicesApi.list()).items);
  const models = useAsync(async () => (await modelsApi.list()).items);
  const m = useMutation();
  const [editing, setEditing] = useState<Camera | null | "new">(null);
  const [onlyMissing, setOnlyMissing] = useState(false);
  const missingCount = cameras.data?.filter((c) => c.missing_from_edge_at).length ?? 0;
  const rows = onlyMissing ? (cameras.data ?? []).filter((c) => c.missing_from_edge_at) : (cameras.data ?? []);

  const removeMissing = async () => {
    const targets = (cameras.data ?? []).filter((c) => c.missing_from_edge_at);
    if (!targets.length || !confirm(t("cameras.confirmDeleteMissing", { n: targets.length }))) return;
    for (const c of targets) {
      if (!(await m.run(() => camerasApi.remove(c.id))).ok) break;
    }
    setOnlyMissing(false);
    cameras.reload();
  };

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
    if (!confirm(t("cameras.confirmDelete", { name: c.name }))) return;
    if ((await m.run(() => camerasApi.remove(c.id))).ok) cameras.reload();
  };

  return (
    <>
      <PageHeader
        title={t("nav.cameras")}
        subtitle={t("cameras.subtitle")}
        actions={
          <>
            {missingCount > 0 && (
              <Button variant={onlyMissing ? "primary" : "secondary"} onClick={() => setOnlyMissing(!onlyMissing)}>
                {t("cameras.missingFilter", { n: missingCount })}
              </Button>
            )}
            {canEdit && onlyMissing && missingCount > 0 && (
              <Button variant="danger" onClick={removeMissing} disabled={m.busy}>
                {t("cameras.deleteMissing", { n: missingCount })}
              </Button>
            )}
            {canEdit && (
              <Button onClick={() => setEditing("new")} disabled={!devices.data?.length}>
                {t("cameras.add")}
              </Button>
            )}
          </>
        }
      />
      <ErrorBanner error={cameras.error ?? m.error} />
      <DataTable
        loading={cameras.loading}
        rows={rows}
        columns={[
          {
            key: "name",
            header: t("common.camera"),
            render: (c) => (
              <div>
                <div className="font-medium">{c.name}</div>
                <div className="text-xs text-slate-500">
                  {c.code} {c.has_credentials && "· 🔒"}
                  {!c.source_configured && ` · ${t("cameras.edgeManagedShort")}`}
                </div>
                {c.missing_from_edge_at && (
                  <div className="mt-0.5" title={formatDateTime(c.missing_from_edge_at)}>
                    <Badge tone="yellow">{t("cameras.missingBadge")}</Badge>
                  </div>
                )}
              </div>
            ),
          },
          { key: "site", header: t("cameras.siteEdge"), render: (c) => `${c.site_name ?? "—"} / ${c.edge_device_name ?? "—"}` },
          { key: "path", header: t("cameras.streamPath"), render: (c) => <code className="text-xs">{c.stream_path}</code> },
          {
            key: "video",
            header: t("cameras.streamAi"),
            render: (c) => (
              <span className="text-xs text-slate-400">
                {c.resolution ?? t("cameras.source")} @ {c.stream_fps} fps · {c.bitrate} · AI {c.inference_fps} fps
              </span>
            ),
          },
          { key: "health", header: t("cameras.health"), render: (c) => (c.enabled ? <CameraHealth camera={c} /> : t("status.disabled")) },
          {
            key: "actions",
            header: "",
            className: "text-right",
            render: (c) =>
              canEdit && (
                <div className="flex justify-end gap-1">
                  <Button variant="ghost" onClick={() => setEditing(c)}>
                    {t("common.edit")}
                  </Button>
                  <Button variant="ghost" onClick={() => remove(c)}>
                    {t("common.delete")}
                  </Button>
                </div>
              ),
          },
        ]}
      />
      <Modal open={editing !== null} title={editing === "new" ? t("cameras.addTitle") : t("cameras.editTitle")} onClose={() => setEditing(null)}>
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
