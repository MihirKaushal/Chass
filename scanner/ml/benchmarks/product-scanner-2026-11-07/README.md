# Product Scanner Checkpoint: 2026-11-07

## User-Facing Changes

Linked prepared-photo/square inspection, optional detection outlines, compact
result counts, original-versus-corrected audit, active review time, staged timing,
homepage entry, and collapsed Rulebook performance history. This is the same
Chass feature, not a separate research site. No deployed weight or threshold changed.

## Frozen DINO Pilot

Question: is a small head over frozen DINO features a useful immediate replacement
for the current fine-tuned ResNet18 crop classifier?

- Official DINO ViT-S/8, pinned revision recorded in `dino-pilot.json`.
- 1,536 training crops (128/class) and 768 validation crops (64/class).
- Source-group-disjoint train/validation, fixed seed 42, no test evaluation.
- Same 768 validation crops for both models; ground-truth boxes, not detector crops.
- Four ridge penalties selected on validation, not an independent final test.

| Measure | Current ResNet18 | Frozen DINO + best small head |
| --- | ---: | ---: |
| Correct validation crop labels | 96.09% | 88.15% |
| Local MPS extraction/evaluation time, 768 crops | 1.52 s | 9.31 s |

DINO backbone FP32 parameters alone are about 82.67 MiB. Decision: **not promoted**.
The current model had more training data; this limited probe does not establish
that DINO is intrinsically worse. Timing includes batched crop IO and is not a
browser, Render, or full-scan measurement. More tuning would need a separate
evaluation budget, target-runtime checks and unfamiliar-set evidence.

## Calibration

The existing validation cache contains 12,862 crops but only **two independent
capture groups**. `calibration.json` records a blocked result. The tool requires
at least four groups to separate fitting from a held-out diagnostic without
breaking source groups apart. No temperature was fitted and public scores remain
explicitly uncalibrated. More crops from the same sessions do not solve this gap.

## Runtime

The unchanged deployed ONNX pipeline was rerun on the existing deterministic
30-photo validation subset, CPU single-threaded on the local Mac:

- Model initialization: 120.24 ms.
- Median inference: 153.03 ms; p95: 238.47 ms.
- Peak process RSS: 444.56 MiB; no Torch imported.
- 1,239 annotated pieces, 119 missed pieces, 22 unmatched detections.

The same current model previously measured about 135.5 ms median. This run is
about 12.9% slower, not a speed improvement; machine load and run-to-run noise
are not controlled. Model weights/inference logic are unchanged. No new public
cold-start measurement was made. `runtime.json` records these local results.

## Blocked On Real Data

There is still no verified 64-square collection. Do not infer grid labels from
COCO boxes. Whole-board accuracy, square assignment candidate selection, missing-
piece review gains and review burden remain unmeasured on real boards. The new
evaluation and geometry/review experiments are ready for the collection described
in [BOARD_COLLECTION.md](../../BOARD_COLLECTION.md).

## Reproduce

See [QUALITY.md](../../../QUALITY.md) for commands and promotion checks. Raw pilot
crop IDs and hashes are retained in `dino-pilot.json`; raw local runtime samples
and predictions are under ignored `scanner/artifacts/product-scanner-2026-11-07/`.
No photos, credentials or new model weights are added to the repository.

## Integration Checks

- 219 frontend tests passed; Vite production build passed.
- 157 scanner tests passed; changed Python modules passed Ruff.
- 335 backend tests passed, with one Firestore-emulator-dependent skip.
- Actual ONNX pipeline through the local FastAPI scan endpoint returned HTTP 200,
  64 squares, matching image/model hashes, and 35 detection outlines on a smoke photo.
- The same prepared 512-square fixture through ONNX Web WASM in Node produced
  identical board labels and review flags, with all 35 outlines available. This
  checks the browser inference code, not live browser/WebGPU interaction.
- Live visual QA is still blocked: browser access host unavailable despite enabled
  permissions. Automated render tests cover collapsed disclosures, photo crop
  coordinates, links, uncertainty wording, timing labels, and review gating.

Smoke fixtures were resized for API/parity testing and have no verified square
ground truth. They are deliberately excluded from reported recognition accuracy.
