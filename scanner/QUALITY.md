# Scanner Quality Workflow

Chass's scanner is a product feature, not a separate research app. Its user-facing
flow stays **prepare photo -> review board -> continue game**. Technical details
live in the existing Rulebook and versioned offline reports.

## What Is Implemented

- Homepage scanner entry and shared navigation, with the existing Chass theme.
- Selecting any board square highlights the same square in the prepared photo
  and shows a crop beside suggestions. This also works for unflagged empty squares.
- A compact detected/review/corrected summary; original predictions are preserved.
- Collapsed Scan Details: actual model hashes, inference and waiting time,
  optional detection outlines, corrections, and active review time after confirmation.
- Local reviewed-label exports include an audit trail. Photos are not retained by
  the service, and no corrections are silently collected for training.
- The Rulebook shows dated box-level results and explicitly unmeasured board metrics.

## Evaluation Contract

Keep model classification, localization, square assignment, and user corrections
separate. Do not call a box-level result "board accuracy" or a softmax output a
measured probability of correctness.

The verified-board report measures occupancy precision/recall, exact square labels,
whole-board accuracy, per-class confusion/misses/inventions, square corrections
needed, review-flag recall/precision, and available active review times. The scorer
also records local model load/inference timing; this is not hosting cold-start time.

Maintain an untouched unfamiliar-physical-set holdout. Split by set, session and
source group, not random images. The existing regression collection has been reused
and must not be advertised as a fresh generalization test.

See [collection instructions](ml/BOARD_COLLECTION.md). Start with 50-100 carefully
verified boards from at least five physical sets as a practical target, not a
statistical guarantee. Calibration additionally needs enough independent validation
groups for fitting and checking; the current collection has only two.

## Offline Experiments

All commands run from the repository root, write to fresh paths, and leave public
weights and thresholds unchanged. Use validation for choices and freeze them before
an independent test. Never fabricate square labels from detection-box centers.

### Geometry And Missing-Piece Review

```sh
.venv-scanner/bin/python -m scanner.ml.board_experiment \
  --collection scanner/artifacts/verified-v1.json \
  --photos scanner/data/verified/photos \
  --output scanner/artifacts/board-trial-v1.json
```

Compares current box-center mapping with two vertical-anchor heuristics, plus a
lower-threshold detector probe that only adds review flags for possible missed pieces.
The latter is not an independent occupancy classifier and never inserts a piece.
The experiment is blocked until verified validation boards are available. A learned
occupied/empty-square model needs those labels and remains a subsequent experiment.

### Confidence Calibration

```sh
.venv-scanner/bin/python -m scanner.ml.calibration \
  --checkpoint scanner/artifacts/king-focused-2026-11-06/best.pt \
  --cache scanner/artifacts/crops/chess-v2-v3-160 \
  --output scanner/artifacts/calibration-v1.json
```

Fits one temperature on one half of validation groups, evaluates on the other,
and reports negative log likelihood, multiclass Brier score, ECE and reliability bins.
At least four groups are required; otherwise it writes a blocked report. This guard
prevents related crops from falsely making calibration appear independently checked.
It does not improve the predicted class or fix missed pieces. Production scores
remain uncalibrated until a compatible model artifact and independent checks exist.

Method: [Guo et al., On Calibration of Modern Neural Networks](https://proceedings.mlr.press/v70/guo17a.html).

### Frozen Feature Comparison

```sh
.venv-scanner/bin/python -m scanner.ml.feature_probe \
  --cache scanner/artifacts/crops/chess-v2-v3-160 \
  --checkpoint scanner/artifacts/king-focused-2026-11-06/best.pt \
  --output scanner/artifacts/dino-pilot-v1.json
```

Downloads the official pretrained DINO ViT-S/8 backbone using a pinned repository
revision. Extracts frozen features, fits small ridge-classification heads on a
class-capped training subset, and compares with the current ResNet18 on the same
validation crops. Saves source crop IDs, fingerprints, timing, and per-class results.
It is a bounded feasibility probe, not an architecture ranking: the existing
ResNet18 saw more training data. No test images or production weights are changed.

If Python reports a missing certificate authority on macOS, use the installed CA
bundle for this command: `SSL_CERT_FILE=$(.venv-scanner/bin/python -m certifi)`.
Never disable TLS verification. The experiment has no paid API requirement.

Sources: [official DINO implementation](https://github.com/facebookresearch/dino),
[Stanford chess-recognition project](https://cs231n.stanford.edu/papers/text_file_840577057-CS_231N_Final_Paper.pdf).

### Runtime Checks

```sh
.venv-scanner/bin/python -m scanner.ml.runtime_experiment benchmark \
  --models scanner/models/onnx --limit 30 --batch 1 \
  --output scanner/artifacts/runtime-product-v1
```

Record hardware, model hashes, sample IDs, median and p95. Keep service waking,
request/upload latency, model download/setup, and inference separate. Browser
Scan Details measures these stages without background telemetry. Do not claim a
public speed improvement from a local Mac benchmark.

## Promotion Checklist

1. Record hypothesis and baseline; change one component at a time.
2. Check dataset, label, model and preprocessing fingerprints.
3. Compare misses, invented pieces, King recall, exact boards and review burden.
4. Check latency, memory and download size on the actual deployment path.
5. Verify Python/browser output parity and human-review controls.
6. Freeze the candidate, evaluate the untouched set, and retain rollback artifacts.
7. Update the accuracy tracker and user-facing benchmark snapshot with definitions.

## Portfolio Demonstration

Keep one Chass project entry. A short demo can show a physical-board photo, linked
inspection of a doubtful square, correction, and an actual local/online game.
Explain your dataset cleanup, evaluation and deployment decisions, and distinguish
pretrained components from your own integration. Include representative failures
and retained/rejected experiments, not only successful screenshots.

## External Work Still Needed

- Collect varied unaugmented physical-board photos with rights to use them.
- Verify all 64 squares, retain prepared-photo hashes, record set/session/source
  groups, and keep unfamiliar sets out of development.
- Reconnect browser access or manually check desktop layout, on-device inference,
  cancellation, flipping, undo/restore and local/online continuation.
- Push/deploy the changes when ready. No new secret, paid service or database
  migration is required for this update. Model promotion is intentionally separate.
