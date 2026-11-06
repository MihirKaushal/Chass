# Scanner Optimization Experiments: 2026-11-06

## Accepted Changes

- Fine-tune the existing ResNet18 crop classifier with extra King sampling. Training
  uses only the original training split; best epoch selected by validation macro F1.
- Select detection threshold 0.20, overlap 0.40 on validation (308 photos, 12,862
  annotated pieces). Freeze the decision before reading test results.
- Keep FP32 static batch 1. Avoid converting/copying the whole image for every crop.
- Record per-stage inference timings. Wake the game API and model host concurrently
  through public readiness, without sending credentials or keeping servers awake.
- Offer optional browser recognition with a worker, checksum-verified model cache,
  single-thread WASM/WebGPU selection, cancellation and disclosed server fallback.
- Flag missing/duplicate Kings and plausible alternative candidates for manual review.
  Never force a King onto the board based on chess rules alone.

## Accuracy

The frozen test has 338 photos and 6,283 pieces. Compare the previous selected
combined pipeline, not the much weaker detector-only baseline.

| Measure | Previous | Selected |
| --- | ---: | ---: |
| Conditional type/color accuracy | 96.32% | 97.95% |
| Typed piece recall | 85.02% | 89.59% |
| Typed prediction precision | 94.30% | 95.47% |
| Missed pieces | 737 | 536 |
| Unmatched extra detections | 119 | 149 |
| Black King conditional accuracy | 85.64% | 95.34% |
| White King conditional accuracy | 95.48% | 98.96% |

The test was not used to select a runner-up. It is a repeatedly used development
test, not an independent new chess-set evaluation. Exact-square and whole-board
accuracy remain unmeasured. Small validation/test differences are not confidence
intervals. False extra boxes increased even though typed precision improved.

`validation.json`, `selection.json`, `test.json`, and `training-history.json` preserve
the selection history and metrics. `test.json` embeds the pre-promotion decision;
`selection.json` records the later explicit MVP promotion decision.

## Runtime Experiments

macOS arm64, ONNX Runtime 1.31.1, CPU, one inference thread, 30 validation photos
spread across the split, fresh process per configuration. These use original
image sizes, **not** the public API's 2048-pixel resize path. Timings include the
first inference; model load is reported separately. RSS is process peak on macOS.

| Configuration | Median / p95 ms | Peak MiB | Decision |
| --- | ---: | ---: | --- |
| Previous FP32, static batch 1 | 124.7 / 200.7 | 452.3 | Baseline |
| Dynamic FP32, batch 1 | 474.0 / see JSON | 420.9 | Not promoted |
| Dynamic FP32, batch 2 | 600.1 / 991.0 | 423.4 | Not promoted |
| Dynamic FP32, batch 4 | 602.2 / see JSON | 421.9 | Not promoted |
| INT8, batch 1 | 192.3 / see JSON | 367.1 | Not promoted |
| INT8, batch 2 | 193.1 / 310.1 | 368.9 | Not promoted |
| INT8, batch 4 | 191.4 / 316.0 | 363.2 | Not promoted |
| Full image plus four overlapping tiles | 221.1 / 294.5 | 456.3 | Not promoted |
| Selected King classifier + threshold 0.20 | 135.5 / 209.3 | 452.6 | Accuracy/runtime tradeoff accepted |

INT8 used 192 class-balanced **training-only** calibration crops. It improves over
the dynamic FP32 graph, but not the deployed static graph on this machine; CPU
architecture matters. Typed recall fell slightly (84.83 -> 84.67%) on this subset.
Tiling raised recall but produced 111 unmatched boxes vs 17, dropping typed
precision from 95.29% to 87.76%. These candidates remain offline, never default.

The selected model costs about 8.6% more locally because it processes more proposals.
This work does **not** claim server inference became faster. The wake-up optimization
removes sequential startup waits; it cannot remove Render's free-tier cold start.

## Export And Browser Checks

- 40 validation photos: identical boards, review flags, final labels and top-three
  labels between Torch and ONNX. Maximum box delta 0.000489 px.
- One nearly integral crop boundary on image 1434 differed by one crop pixel
  (`ceil(1096.000...)`), causing confidence 0.97363 vs 0.97071. The parity test
  explicitly permits 0.005 confidence difference for this export; default remains
  0.002. Exact board/review/label requirements were **not** relaxed.
- Four synthetic geometry cases: JS crops are pixel-identical to Pillow; detector
  interpolation matches NumPy within 1e-5. Covers portrait/landscape/downsampling.
- The browser worker's inference function ran on a 1024-square smoke photo through
  ONNX Web WASM in Node: identical board, review flags and top-three labels; about
  2.8 seconds locally, excluding model download/setup. This is not a measured
  browser/WebGPU speed guarantee. Actual GPU support varies; fallback is automatic.
- Browser host access was unavailable for visual/GPU QA. The opt-in path remains
  explicitly experimental and does not replace server recognition by default.

## Reproduce

```sh
.venv-scanner/bin/python -m scanner.ml.classifier --help
.venv-scanner/bin/python -m scanner.ml.runtime_experiment benchmark \
  --models scanner/models/onnx --output scanner/artifacts/runtime-new --limit 30
.venv-scanner/bin/python -m scanner.ml.accuracy_experiment \
  --checkpoints scanner/artifacts/crop-classifier-v1/best.pt \
    scanner/artifacts/king-focused-2026-11-06/best.pt \
  --output scanner/artifacts/accuracy-new --test
```

Training config: `scanner/ml/configs/king-focused.json`. Use fresh output paths.
Do not repeatedly tune against the test set. See `scanner/ml/BOARD_COLLECTION.md`
for the next independent collection and exact 64-square evaluation workflow.
Previous deployment weights are preserved in Git commit `db38ede` for rollback.
