"use client";

import { useState } from "react";

import type { EdgeLog } from "@/types";

/**
 * Snapshot with the reported detections drawn on top. Boxes are in the edge's frame pixels
 * (`frame` gives the size) or normalized 0..1 when no frame size is sent.
 * `height` shows it at that height (e.g. 480 = 480p), scaled down when the screen is narrower.
 */
export function SnapshotWithBoxes({ log, height }: { log: EdgeLog; height?: number }) {
  const [ratio, setRatio] = useState(log.frame ? log.frame.width / log.frame.height : 16 / 9);
  if (!log.snapshot_url) return null;
  const normalized = !log.frame;
  const w = log.frame?.width ?? 1;
  const h = log.frame?.height ?? 1;
  return (
    <div
      className="relative mx-auto"
      style={height ? { width: `min(100%, ${Math.round(height * ratio)}px)` } : undefined}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={log.snapshot_url}
        alt={log.event_type}
        className="block h-auto w-full rounded-[10px]"
        onLoad={(e) => {
          const img = e.currentTarget;
          if (img.naturalWidth && img.naturalHeight) setRatio(img.naturalWidth / img.naturalHeight);
        }}
      />
      {log.detections.length > 0 && (
        <svg
          className="pointer-events-none absolute inset-0 h-full w-full"
          viewBox={`0 0 ${w} ${h}`}
          preserveAspectRatio="none"
        >
          {log.detections.map((d, i) => {
            const b = d.bbox;
            return (
              <rect
                key={i}
                x={b.x1}
                y={b.y1}
                width={Math.max(0, b.x2 - b.x1)}
                height={Math.max(0, b.y2 - b.y1)}
                fill="none"
                stroke="var(--cyan)"
                strokeWidth={normalized ? 0.004 : Math.max(2, w / 400)}
              >
                <title>{`${d.class_name} ${(d.confidence * 100).toFixed(0)}%`}</title>
              </rect>
            );
          })}
        </svg>
      )}
    </div>
  );
}
