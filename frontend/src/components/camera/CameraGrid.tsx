"use client";

import { useEffect, useRef, useState } from "react";

import { CameraCard } from "@/components/camera/CameraCard";
import { useI18n } from "@/lib/i18n/I18nProvider";
import { fitGrid } from "@/lib/gridLayout";
import type { Camera } from "@/types";

const GAP = 8;

/** Fills its parent exactly: `slots` tiles laid out to the parent's size, no scrolling. */
export function CameraGrid({ cameras, slots }: { cameras: Camera[]; slots: number }) {
  const { t } = useI18n();
  const ref = useRef<HTMLDivElement>(null);
  const [box, setBox] = useState({ w: 0, h: 0 });

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) =>
      setBox({ w: entry.contentRect.width, h: entry.contentRect.height }),
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // never lay out more slots than there are cameras on a single page
  const count = Math.max(1, Math.min(slots, cameras.length || 1));
  const { cols, rows } = fitGrid(count, box.w, box.h, GAP);

  return (
    <div ref={ref} className="min-h-0 flex-1">
      {cameras.length === 0 ? (
        <div className="flex h-full items-center justify-center rounded-lg border border-dashed border-slate-700 text-slate-500">
          {t("monitor.noCameras")}
        </div>
      ) : (
        <div
          className="grid h-full w-full"
          style={{
            gap: GAP,
            gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`,
            gridTemplateRows: `repeat(${rows}, minmax(0, 1fr))`,
          }}
        >
          {cameras.map((c) => (
            <CameraCard key={c.id} camera={c} />
          ))}
        </div>
      )}
    </div>
  );
}
