"use client";

import { CameraCard } from "@/components/camera/CameraCard";
import type { GridSize } from "@/components/camera/GridSelector";
import type { Camera } from "@/types";
import { useI18n } from "@/lib/i18n/I18nProvider";

const COLS: Record<GridSize, string> = {
  1: "grid-cols-1",
  2: "grid-cols-1 sm:grid-cols-2",
  3: "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3",
  4: "grid-cols-1 sm:grid-cols-2 lg:grid-cols-4",
};

export function CameraGrid({ cameras, size }: { cameras: Camera[]; size: GridSize }) {
  const { t } = useI18n();
  if (cameras.length === 0) {
    return <div className="rounded-lg border border-dashed border-slate-700 p-10 text-center text-slate-500">{t("monitor.noCameras")}</div>;
  }
  return (
    <div className={`grid gap-3 ${COLS[size]}`}>
      {cameras.map((c) => (
        <CameraCard key={c.id} camera={c} />
      ))}
    </div>
  );
}
