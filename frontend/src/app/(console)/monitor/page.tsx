"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { CameraGrid } from "@/components/camera/CameraGrid";
import { GRID_SIZES, GridSelector, type GridSize } from "@/components/camera/GridSelector";
import { Button } from "@/components/ui/Button";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Select } from "@/components/ui/Field";
import { useAsync } from "@/hooks/useAsync";
import { camerasApi } from "@/lib/api/cameras";
import { sitesApi } from "@/lib/api/sites";
import { applyCameraStatus } from "@/lib/cameraStatus";
import { useI18n } from "@/lib/i18n/I18nProvider";
import { useRealtime } from "@/lib/realtime/RealtimeProvider";
import type { CameraStatusMessage, DeviceStatusMessage } from "@/types";

const SIZE_KEY = "aivms.monitor.size";

function loadSize(): GridSize {
  try {
    const v = Number(localStorage.getItem(SIZE_KEY));
    return (GRID_SIZES as readonly number[]).includes(v) ? (v as GridSize) : 2;
  } catch {
    return 2;
  }
}

/**
 * Fills exactly the visible area below the top bar on any screen: the grid adapts its columns × rows
 * to the space (see fitGrid) and the page never scrolls.
 */
export default function MonitorPage() {
  const { t } = useI18n();
  const [size, setSize] = useState<GridSize>(2);
  const [siteId, setSiteId] = useState("");
  const [page, setPage] = useState(0);
  const [fullscreen, setFullscreen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => setSize(loadSize()), []);
  useEffect(() => {
    const onChange = () => setFullscreen(document.fullscreenElement === rootRef.current);
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);

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

  // only mount players for the visible page
  const perPage = size * size;
  const all = cameras.data ?? [];
  const pages = Math.max(1, Math.ceil(all.length / perPage));
  const current = Math.min(page, pages - 1);
  const visible = useMemo(() => all.slice(current * perPage, (current + 1) * perPage), [all, current, perPage]);

  const changeSize = (v: GridSize) => {
    setSize(v);
    setPage(0);
    try {
      localStorage.setItem(SIZE_KEY, String(v));
    } catch {
      /* ignore */
    }
  };

  const toggleFullscreen = () => {
    if (document.fullscreenElement) document.exitFullscreen().catch(() => undefined);
    else rootRef.current?.requestFullscreen().catch(() => undefined);
  };

  return (
    <div
      ref={rootRef}
      className={
        fullscreen
          ? "flex h-screen flex-col gap-2 bg-surface-900 p-2"
          : // 3rem = top bar; main padding is 0.75rem (mobile) / 1.25rem (md+) on each side
            "flex h-[calc(100dvh-3rem-1.5rem)] flex-col gap-2 md:h-[calc(100dvh-3rem-2.5rem)]"
      }
    >
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <h1 className="truncate text-lg font-semibold text-white">{t("nav.monitor")}</h1>
          <p className="hidden truncate text-xs text-slate-400 lg:block">{t("monitor.subtitle", { n: all.length })}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Select
            value={siteId}
            onChange={(e) => (setSiteId(e.target.value), setPage(0))}
            className="!w-36 sm:!w-44"
          >
            <option value="">{t("monitor.allSites")}</option>
            {sites.data?.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </Select>
          <GridSelector value={size} onChange={changeSize} />
          {pages > 1 && (
            <div className="flex shrink-0 items-center gap-1 text-sm">
              <Button variant="secondary" className="!px-2" disabled={current === 0} onClick={() => setPage(current - 1)}>
                ‹
              </Button>
              <span className="min-w-[3.5rem] text-center tabular-nums text-slate-400">
                {current + 1} / {pages}
              </span>
              <Button
                variant="secondary"
                className="!px-2"
                disabled={current >= pages - 1}
                onClick={() => setPage(current + 1)}
              >
                ›
              </Button>
            </div>
          )}
          <Button variant="secondary" className="!px-2.5" onClick={toggleFullscreen} title={t(fullscreen ? "monitor.exitFullscreen" : "monitor.fullscreen")}>
            {fullscreen ? "⤡" : "⤢"}
          </Button>
        </div>
      </div>
      {cameras.error && <ErrorBanner error={cameras.error} />}
      <CameraGrid cameras={visible} slots={perPage} />
    </div>
  );
}
