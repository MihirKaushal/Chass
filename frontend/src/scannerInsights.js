export const squareName = ({ row, col }) => `${"abcdefgh"[col]}${8 - row}`;

export function boardLabels(board) {
  return board.map((rank) => rank.map((piece) =>
    typeof piece === "string" || piece === null ? piece : `${piece.color}-${piece.type}`));
}

export function scanCorrections(scan, board) {
  if (!scan?.board || !board) return [];
  return boardLabels(board).flatMap((rank, row) => rank.flatMap((after, col) => {
    const before = scan.board[row][col];
    return before === after ? [] : [{ row, col, square: squareName({ row, col }), before, after }];
  }));
}

export function scanSummary(scan, board) {
  return {
    detected: scan?.board?.flat().filter(Boolean).length || 0,
    corrected: scanCorrections(scan, board).length,
    originalFlags: scan?.reviewSquares?.length || 0,
  };
}

export function formatDuration(milliseconds) {
  if (!Number.isFinite(milliseconds) || milliseconds < 0) return "Not measured";
  return milliseconds < 1000 ? `${Math.round(milliseconds)} ms` : `${(milliseconds / 1000).toFixed(1)} s`;
}

export function detectionRects(scan) {
  if (!(scan?.imageWidth > 0 && scan?.imageHeight > 0)) return [];
  return (scan.prediction?.boxes || []).flatMap((box, index) => {
    if (!Array.isArray(box) || box.length !== 4 || !box.every(Number.isFinite)) return [];
    const [left, top, right, bottom] = box.map((value, i) =>
      Math.max(0, Math.min(8, value / (i % 2 ? scan.imageHeight : scan.imageWidth) * 8)));
    return right > left && bottom > top
      ? [{ x: left, y: top, width: right - left, height: bottom - top, index }] : [];
  });
}

// Count visible review time only, not a background tab or an already confirmed board.
export function createReviewClock(now = () => performance.now()) {
  let total = 0;
  let started = null;
  return {
    resume() { if (started === null) started = now(); },
    pause() { if (started !== null) { total += Math.max(0, now() - started); started = null; } },
    elapsed() { return Math.round(total + (started === null ? 0 : Math.max(0, now() - started))); },
  };
}
