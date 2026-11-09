import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { SCANNER_PERFORMANCE } from "./scannerPerformance.js";

const report = (relative) => JSON.parse(readFileSync(new URL(`../../scanner/ml/benchmarks/${relative}`, import.meta.url), "utf8"));

test("published piece-progress chart reproduces saved box-level benchmark counts", () => {
  const original = report("chess-v2-v3-crops-v1/results.json").splits.test.variants;
  const previous = report("optimization-2026-11-06/test.json").metrics;
  const experiment = report("merged-data-2026-11-08/results.json");
  const current = experiment.results.merged.test.combined;
  const sources = [original.baseline, original.combined, previous, experiment.results.merged.test.per_source["chess-v2"]];
  SCANNER_PERFORMANCE.history.forEach((entry, i) => {
    assert.equal(entry.correct, sources[i].correct_type_color);
    assert.equal(entry.located, sources[i].localized_pieces);
  });
  assert.equal(SCANNER_PERFORMANCE.pieces, current.annotated_pieces);
  assert.equal(SCANNER_PERFORMANCE.missed, current.missed_pieces);
  assert.equal(SCANNER_PERFORMANCE.extra, current.unmatched_predictions);
  assert.equal(SCANNER_PERFORMANCE.correctAll, current.correct_type_color);
  assert.equal(SCANNER_PERFORMANCE.photos, current.images);
  assert.equal(SCANNER_PERFORMANCE.located, current.localized_pieces);
  assert.equal(SCANNER_PERFORMANCE.historyPhotos, original.baseline.images);
  assert.equal(SCANNER_PERFORMANCE.historyPieces, previous.annotated_pieces);
  assert.ok(Math.abs(SCANNER_PERFORMANCE.sourceBalancedF1 - experiment.results.merged.test.macro_source_typed_f1) < 1e-12);
  for (const entry of SCANNER_PERFORMANCE.sources) {
    const after = experiment.results.merged.test.per_source[entry.key];
    const before = experiment.results.deployed.test.per_source[entry.key];
    assert.equal(entry.correct, after.correct_type_color);
    assert.equal(entry.previous, before.correct_type_color);
    assert.equal(entry.pieces, after.annotated_pieces);
    assert.equal(entry.photos, after.images);
  }
});

test("real-piece outcomes partition the benchmark and exclude hallucinated detections", () => {
  const data = SCANNER_PERFORMANCE;
  const wrongLabel = data.located - data.correctAll;
  assert.equal(wrongLabel, 134);
  assert.equal(data.correctAll + wrongLabel + data.missed, data.pieces);
  assert.equal(data.pieces - data.missed, data.located);
  assert.equal((data.correctAll / data.pieces * 100).toFixed(2), "89.73");
});
