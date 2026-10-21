/**
 * Choose columns × rows for `count` tiles in a `width` × `height` box so that each 16:9 video is as
 * large as possible. A 2×2 selection on a portrait phone therefore becomes 1 column × 4 rows, on a
 * wide monitor 2 × 2 (or 4 × 1 on an ultra-wide): always fits, never scrolls.
 */
export function fitGrid(
  count: number,
  width: number,
  height: number,
  gap = 8,
  aspect = 16 / 9,
): { cols: number; rows: number } {
  if (count <= 1 || width <= 0 || height <= 0) return { cols: 1, rows: 1 };
  let best = { cols: count, rows: 1, size: -1 };
  for (let cols = 1; cols <= count; cols++) {
    const rows = Math.ceil(count / cols);
    const cellW = (width - gap * (cols - 1)) / cols;
    const cellH = (height - gap * (rows - 1)) / rows;
    if (cellW <= 0 || cellH <= 0) continue;
    // width of the largest 16:9 video that fits the cell
    const videoW = Math.min(cellW, cellH * aspect);
    // prefer fewer empty cells when sizes are equal
    if (videoW > best.size + 0.5 || (Math.abs(videoW - best.size) <= 0.5 && cols * rows < best.cols * best.rows)) {
      best = { cols, rows, size: videoW };
    }
  }
  return { cols: best.cols, rows: best.rows };
}
