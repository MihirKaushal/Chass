import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { SCANNER_PERFORMANCE } from "./scannerPerformance.js";

const report = (relative) => JSON.parse(readFileSync(new URL(`../../scanner/ml/benchmarks/${relative}`, import.meta.url), "utf8"));

test("published piece-progress chart reproduces saved box-level benchmark counts", () => {
  const original = report("chess-v2-v3-crops-v1/results.json").splits.test.variants;
  const current = report("optimization-2026-11-06/test.json").metrics;
  const sources = [original.baseline, original.combined, current];
  SCANNER_PERFORMANCE.history.forEach((entry, i) => {
    assert.equal(entry.correct, sources[i].correct_type_color);
    assert.equal(entry.located, sources[i].localized_pieces);
  });
  assert.equal(SCANNER_PERFORMANCE.pieces, current.annotated_pieces);
  assert.equal(SCANNER_PERFORMANCE.missed, current.missed_pieces);
  assert.equal(SCANNER_PERFORMANCE.extra, current.unmatched_predictions);
  assert.equal(SCANNER_PERFORMANCE.correctAll, current.correct_type_color);
  assert.equal(SCANNER_PERFORMANCE.photos, original.baseline.images);
});

test("real-piece outcomes partition the benchmark and exclude hallucinated detections", () => {
  const data = SCANNER_PERFORMANCE;
  const current = data.history.at(-1);
  const wrongLabel = current.located - data.correctAll;
  assert.equal(wrongLabel, 118);
  assert.equal(data.correctAll + wrongLabel + data.missed, data.pieces);
  assert.equal(data.pieces - data.missed, current.located);
  assert.equal((data.correctAll / data.pieces * 100).toFixed(2), "89.59");
});
