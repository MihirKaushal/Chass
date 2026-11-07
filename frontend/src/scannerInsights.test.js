import assert from "node:assert/strict";
import { test } from "node:test";
import { createReviewClock, detectionRects, formatDuration, scanCorrections, scanSummary, squareName } from "./scannerInsights.js";
import { reviewedBoardLabels } from "./scannerApi.js";

const empty = () => Array.from({ length: 8 }, () => Array(8).fill(null));

test("corrections compare against original recognition, not edit clicks", () => {
  const original = empty();
  original[0][0] = "black-rook";
  const scan = { board: original, reviewSquares: [{ row: 0, col: 0 }] };
  const board = empty();
  board[7][7] = { type: "king", color: "white" };
  assert.deepEqual(scanCorrections(scan, board), [
    { row: 0, col: 0, square: "a8", before: "black-rook", after: null },
    { row: 7, col: 7, square: "h1", before: null, after: "white-king" },
  ]);
  assert.deepEqual(scanSummary(scan, board), { detected: 1, corrected: 2, originalFlags: 1 });
  assert.equal(scanCorrections(scan, original).length, 0);
  assert.equal(original[0][0], "black-rook");
});

test("photo overlays use processed image dimensions and reject malformed boxes", () => {
  const scan = { imageWidth: 1600, imageHeight: 1600, prediction: { boxes: [
    [0, 0, 200, 200], [-20, -20, 1800, 1800], [NaN, 0, 1, 1], [4, 4, 2, 2], [],
  ] } };
  assert.deepEqual(detectionRects(scan), [
    { x: 0, y: 0, width: 1, height: 1, index: 0 },
    { x: 0, y: 0, width: 8, height: 8, index: 1 },
  ]);
  assert.deepEqual(detectionRects({}), []);
  assert.equal(squareName({ row: 7, col: 0 }), "a1");
});

test("review clock excludes hidden/confirmed intervals and handles repeated events", () => {
  let now = 0;
  const clock = createReviewClock(() => now);
  clock.resume(); now = 100; clock.resume(); now = 150; clock.pause();
  now = 900; clock.pause(); assert.equal(clock.elapsed(), 150);
  clock.resume(); now = 950; assert.equal(clock.elapsed(), 200);
  clock.pause(); assert.equal(clock.elapsed(), 200);
});

test("unknown timings stay unknown, and label exports keep an audit trail without photo bytes", () => {
  assert.equal(formatDuration(undefined), "Not measured");
  assert.equal(formatDuration(-1), "Not measured");
  assert.equal(formatDuration(0), "0 ms");
  assert.equal(formatDuration(1500), "1.5 s");
  const scan = { imageSha256: "a".repeat(64), board: empty(), reviewSquares: [], inferenceMs: 0 };
  const labels = reviewedBoardLabels(scan, empty(), { reviewMs: 123 });
  const record = labels.records[0];
  assert.equal(record.verification, "user_reviewed_not_independently_audited");
  assert.equal(record.review.active_ms, 123);
  assert.deepEqual(record.recognition.board, scan.board);
  assert.equal(record.recognition.inference_ms, 0);
  assert.doesNotMatch(JSON.stringify(labels), /data:image|blob:/);
});
