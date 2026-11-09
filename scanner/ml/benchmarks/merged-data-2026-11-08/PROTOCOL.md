# Two-Source Scanner Experiment

Registered before candidate evaluation on November 8, 2026. This is an offline
experiment; it does not replace the website's models or benchmark snapshot.

## Question

Does adding Chess Top Down to curated Chess V2 improve piece recognition across
both sources without degrading the existing Chess V2 behavior?

This tests source coverage, not generalization to independently collected physical
sets. Top Down does not identify physical sets/sessions, its test split contains
only 17 photos / 93 pieces, and both collections have earlier development exposure.
No verified 64-square ground truth is available, so whole-board and empty-square
accuracy cannot be inferred from these detection annotations.

## Dataset Safety

- Preserve the original image files, labels, and split assignments.
- Verify source manifest fingerprints and image SHA-256 hashes.
- Group augmentation filename families, existing curated capture components,
  decoded-pixel identities, and rotation/mirror-aware perceptual candidates.
- Do not move previously exposed training/validation images into test.
- Quarantine added-source images in less protected splits when their component
  touches a held-out image. Fail for conflicts involving frozen base splits.
- Remove exact added-source pixel duplicates only when their annotations agree;
  conflicting annotations require manual review.
- Keep validation/test records identical between the two experiment arms.

The audit found 132 perceptual pairs, none crossing data sources. One Top Down
validation image was excluded because it is related to a test image. Absence of
cross-source matches is not proof that no relationship exists.

| Source | Train images / pieces | Validation images / pieces | Test images / pieces |
| --- | ---: | ---: | ---: |
| Chess V2 | 1,419 / 40,307 | 308 / 12,862 | 338 / 6,283 |
| Top Down | 270 / 1,431 | 39 / 227 | 17 / 93 |

The control excludes Top Down **training** records, but uses the same combined
validation and test records as the merged arm. The original 40-image Top Down
validation benchmark remains untouched in its original directory.

## Controlled Training

Both arms start from the same deployed detector and King-focused classifier Torch
checkpoints. This is paired continuation training, not a from-scratch experiment.
Source manifest checks prevent checkpoint transfer from relocating or relabeling
previously seen images. Checkpoint hashes are recorded in `protocol.json`.

Both arms use seed 42 and exactly the same maximum optimizer-update budgets:

- Detector: six epochs, 1,424 sampled images/epoch, batch eight, 178 updates/epoch.
- Classifier: six epochs, 12,000 sampled crops/epoch, batch 48, 250 updates/epoch.
- Patience equals the epoch budget; both arms complete the same number of updates.
- Control samples only Chess V2. Merged samples 75% Chess V2 / 25% Top Down in
  expectation, to prevent the larger collection from overwhelming the added data.
- Classifier sampling is class-balanced within each source, retaining the same
  King-focused multipliers in both arms. Detector and classifier use unchanged
  augmentation and architecture. Learning rates are identical between arms.

The seed does not guarantee bitwise deterministic MPS training. A single seed
cannot measure variability across independent training runs.

## Selection And Metrics

Select detector checkpoints by equal-source mean validation mAP@0.5; classifier
checkpoints by equal-source mean validation macro-F1. Select the final detector
threshold from 0.15 / 0.20 / 0.25 / 0.30 using validation only, with duplicate
suppression overlap fixed at 0.40. Persist all selections before test inference.
The unchanged deployed baseline retains its existing threshold of 0.20.

**Primary metric:** equal-source mean typed F1. Within each source:

`typed F1 = 2 * correctly located and typed pieces / (real pieces + predictions)`

Matching is confidence-ordered and class-agnostic at IoU >= 0.5 before checking
type/color, consistent with the existing scanner accuracy tracker. This metric
penalizes misses, incorrect labels, and extra predictions. The equal-source average
prevents the 338-image Chess V2 test set from hiding the 17-image Top Down result.

Also report pooled and source-specific typed recall, typed precision, localization
recall, classification accuracy conditional on localization, misses, extras,
per-class errors/confusions, and King typed recall. Report a 2,000-replicate paired
group bootstrap interval for the primary difference, resampling within each source.
Chess V2 test has only three capture components; intervals are descriptive and
cannot establish unfamiliar-set generalization.

## Promotion Gate

The merged candidate must exceed **both** the unchanged deployed pipeline and the
equal-budget control by at least one percentage point of macro source typed F1.
Neither source may lose more than two percentage points of typed recall or typed
precision, and King typed recall must not fall by more than two points per source.
The paired bootstrap interval's lower bound versus control must be positive.

Passing the accuracy gate is not an automatic deployment: ONNX export parity,
memory/latency measurements, and scanner integration checks remain separate gates.
Keep the existing public model if the candidate fails. Do not tune another candidate
against the reported test failures and relabel that as an untouched test.

## Reproduce

```sh
.venv-scanner/bin/python -m scanner.ml.merge \
  --base scanner/artifacts/curation/chess-v2-v3/prepared/manifest.json \
  --added scanner/artifacts/prepared/manifest.json \
  --output scanner/artifacts/merged-2026-11-08

.venv-scanner/bin/python -m scanner.ml.merge_experiment prepare \
  --merge scanner/artifacts/merged-2026-11-08 \
  --output scanner/artifacts/merge-experiment-2026-11-08

.venv-scanner/bin/python -m scanner.ml.merge_experiment fit \
  --merge scanner/artifacts/merged-2026-11-08 \
  --output scanner/artifacts/merge-experiment-2026-11-08

.venv-scanner/bin/python -m scanner.ml.merge_evaluate \
  --merge scanner/artifacts/merged-2026-11-08 \
  --training scanner/artifacts/merge-experiment-2026-11-08 \
  --output scanner/artifacts/merge-evaluation-2026-11-08
```

Use fresh output directories for another run. Raw data, caches, image-level outputs,
and candidate weights stay local under ignored `scanner/data/` and `scanner/artifacts/`.
Dataset credits remain [Chess V2 by Public Wspace](https://universe.roboflow.com/public-wspace/chess-v2-qqtmk)
and [Chess Top Down by chess](https://universe.roboflow.com/chess-gftva/chess-top-down),
Roboflow Universe, both CC BY 4.0.
