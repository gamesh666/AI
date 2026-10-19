"use client";

import clsx from "clsx";

export const GRID_SIZES = [1, 2, 3, 4] as const;
export type GridSize = (typeof GRID_SIZES)[number];

/** Cameras per page: 1, 4, 9 or 16. The actual columns × rows adapt to the screen. */
export function GridSelector({ value, onChange }: { value: GridSize; onChange: (v: GridSize) => void }) {
  return (
    <div className="inline-flex shrink-0 overflow-hidden rounded-item border border-line2">
      {GRID_SIZES.map((n) => (
        <button
          key={n}
          onClick={() => onChange(n)}
          className={clsx(
            "whitespace-nowrap px-2.5 py-1.5 text-sm tabular-nums",
            value === n ? "bg-accent text-on-accent" : "bg-panel text-ink2 hover:bg-panel2",
          )}
        >
          {n}×{n}
        </button>
      ))}
    </div>
  );
}
