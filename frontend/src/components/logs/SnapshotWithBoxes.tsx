import type { EdgeLog } from "@/types";

/**
 * Snapshot with the reported detections drawn on top. Boxes are in the edge's frame pixels
 * (`frame` gives the size) or normalized 0..1 when no frame size is sent.
 */
export function SnapshotWithBoxes({ log }: { log: EdgeLog }) {
  if (!log.snapshot_url) return null;
  const normalized = !log.frame;
  const w = log.frame?.width ?? 1;
  const h = log.frame?.height ?? 1;
  return (
    <div className="relative">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={log.snapshot_url} alt={log.event_type} className="w-full rounded" />
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
                stroke="#22d3ee"
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
