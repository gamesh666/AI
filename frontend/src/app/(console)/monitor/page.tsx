"use client";

import { useMemo, useState } from "react";

import { CameraGrid } from "@/components/camera/CameraGrid";
import { GridSelector, type GridSize } from "@/components/camera/GridSelector";
import { Button } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Select } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAsync } from "@/hooks/useAsync";
import { camerasApi } from "@/lib/api/cameras";
import { applyCameraStatus } from "@/lib/cameraStatus";
import { sitesApi } from "@/lib/api/sites";
import { useRealtime } from "@/lib/realtime/RealtimeProvider";
import type { CameraStatusMessage, DeviceStatusMessage } from "@/types";

export default function MonitorPage() {
  const [size, setSize] = useState<GridSize>(2);
  const [siteId, setSiteId] = useState("");
  const [page, setPage] = useState(0);

  const sites = useAsync(async () => (await sitesApi.list()).items);
  const cameras = useAsync(async () => (await camerasApi.list({ enabled: true, site_id: siteId || undefined })).items, [
    siteId,
  ]);

  useRealtime<CameraStatusMessage>("camera.status", (msg) =>
    cameras.setData((prev) => prev?.map((c) => applyCameraStatus(c, msg)) ?? prev),
  );
  useRealtime<DeviceStatusMessage>("device.status", (msg) =>
    cameras.setData(
      (prev) =>
        prev?.map((c) => (c.edge_device_id === msg.device_id ? { ...c, edge_device_status: msg.status } : c)) ?? prev,
    ),
  );

  // only mount players for the visible page: size×size tiles
  const perPage = size * size;
  const all = cameras.data ?? [];
  const pages = Math.max(1, Math.ceil(all.length / perPage));
  const current = Math.min(page, pages - 1);
  const visible = useMemo(() => all.slice(current * perPage, (current + 1) * perPage), [all, current, perPage]);

  return (
    <>
      <PageHeader
        title="Camera Monitor"
        subtitle={`${all.length} cameras · AI-annotated streams from the edge · WebRTC with HLS fallback`}
        actions={
          <>
            <Select value={siteId} onChange={(e) => (setSiteId(e.target.value), setPage(0))} className="w-44">
              <option value="">All sites</option>
              {sites.data?.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </Select>
            <GridSelector value={size} onChange={(v) => (setSize(v), setPage(0))} />
          </>
        }
      />
      <ErrorBanner error={cameras.error} />
      <CameraGrid cameras={visible} size={size} />
      {pages > 1 && (
        <div className="mt-4 flex items-center justify-center gap-3 text-sm">
          <Button variant="secondary" disabled={current === 0} onClick={() => setPage(current - 1)}>
            ‹ Prev
          </Button>
          <span className="text-slate-400">
            Page {current + 1} / {pages}
          </span>
          <Button variant="secondary" disabled={current >= pages - 1} onClick={() => setPage(current + 1)}>
            Next ›
          </Button>
        </div>
      )}
    </>
  );
}
