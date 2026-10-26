# Scanner ML Pipeline

An offline, 12-class **piece detector**, separate from the FastAPI game service.
It learns from the existing COCO bounding boxes using TorchVision's pretrained
SSDLite320 MobileNetV3-Large backbone and box regressor, with a new chess-specific
classification head. Both the head and backbone are fine-tuned after head warmup.

This is not yet a complete photo-to-game scanner. It returns piece types, colors,
bounding boxes, and confidence scores. The current dataset has no verified board
corners or 64-square labels, so the pipeline deliberately does not invent square
positions, empty-square labels, FENs, or exact-board accuracy. The `/scanner` page
is still a UI prototype; its recognition button is not connected to this model.

The new trained run and its limitations are recorded in
[CHESS_V2_MODEL_CARD.md](CHESS_V2_MODEL_CARD.md). The original small Top Down
benchmark remains separately documented in [MODEL_CARD.md](MODEL_CARD.md).
See [ACCURACY_TRACKER.md](ACCURACY_TRACKER.md) for dated results, box-level
localization versus classification diagnostics, chart-ready snapshots, and the
square-level metrics that cannot yet be measured.
The [Piece Error Analysis](PIECE_ERROR_ANALYSIS.md) breaks down confused labels,
missed pieces, duplicate predictions, and visually reviewed background candidates.

## Setup

Run from the repository root. Use Python 3.12 or 3.13 with these dependency pins; the baseline was
tested with Python 3.13 on an Apple M4. Use a separate environment, **not** the
backend's `.venv`:

```sh
python3 -m venv .venv-scanner
.venv-scanner/bin/python -m pip install -r scanner/ml/requirements-dev.txt
.venv-scanner/bin/python -m scanner.ml prepare
.venv-scanner/bin/python -m scanner.ml train
.venv-scanner/bin/python -m scanner.ml evaluate --split valid \
  --output scanner/artifacts/validation
```

The first training run downloads official TorchVision COCO weights. Subsequent
inference loads local checkpoints without downloading anything. If this Mac's
Python installation reports `CERTIFICATE_VERIFY_FAILED`, install its trusted
certificates using Python's `Install Certificates.command`, or point
`SSL_CERT_FILE` at an installed trusted CA bundle. Do not disable HTTPS verification.

`auto` chooses CUDA, then Apple MPS, then CPU. Override with `--device cpu`,
`--device mps`, or `--device cuda`. Unsupported MPS operations may fall back to CPU.
No cloud service, API key, GPU subscription, or game-server change is required.

## Evaluate and predict

Validation selects the checkpoint by mAP@0.5 and then selects an operating
confidence threshold by validation F1. Read `threshold` from
`scanner/artifacts/validation/metrics.json`. Pass that **same value** to test
evaluation; do not tune on the test results:

```sh
# This baseline selected 0.20; use your validation threshold after retraining.
.venv-scanner/bin/python -m scanner.ml evaluate --split test --threshold 0.20 \
  --output scanner/artifacts/test
.venv-scanner/bin/python -m scanner.ml predict /path/to/photo.jpg --threshold 0.20 \
  --output scanner/artifacts/my-photo
.venv-scanner/bin/python -m pytest scanner/ml/tests
```

`predict` writes `annotated.jpg` and `prediction.json`, with bounding boxes in
EXIF-oriented input-image pixels. Its default threshold, 0.30, is a convenience
for inspection, not a calibration claim. For comparable results use the selected
validation threshold explicitly. Confidence scores are model scores, not
calibrated probabilities that a whole board is correct.

Open `scanner/artifacts/test/report/index.html` locally to inspect ground truth
beside predictions for every test image. The report includes per-class support,
precision, and recall. JSON metrics also contain COCO mAP@0.5, mAP@0.5:0.95,
TP/FP/FN, and the count of images whose annotated detections all match at IoU
at least 0.5 with no extras. That last metric is **not exact-board accuracy**.
Timing is batched local throughput including preprocessing, not browser latency.

To resume an interrupted run, keep its original output directory and `best.pt`:

```sh
.venv-scanner/bin/python -m scanner.ml train \
  --resume scanner/artifacts/baseline/last.pt
```

Only the epoch limit may change when resuming. Python, CPU Torch, and loader RNG
states are retained; exact bitwise reproducibility across GPU platforms or resumed
GPU execution is not guaranteed. Resumed multi-worker augmentation streams are
also not bitwise identical. Configuration, environment, loss curves, validation
scores, and dataset fingerprints are saved beside checkpoints. Checkpoint writes
are atomic. Do not load checkpoints from untrusted sources.
A fresh run will not overwrite an existing run's checkpoints; use a different
`--output` directory to compare configurations.

For large photos, the Chess V2 config uses `input_size: 320` to perform the
detector's bilinear resize on CPU before GPU transfer. Images and targets are
scaled together, and evaluation/inference restore boxes to original photo pixels.
This matches SSDLite's fixed input resolution; raw images, curated labels, and
dataset fingerprints are unchanged. The setting is stored in the checkpoint and
automatically reused by `evaluate` and `predict`. Older checkpoints retain their
original preprocessing when the setting is absent.

The Chess V2 config also stores seven `anchor_scales` for the six SSDLite feature
maps. Training boxes are typically much smaller than COCO's default anchors at
320x320, so this run uses scales `[0.06, 0.12, 0.24, 0.4, 0.6, 0.8, 1.0]`.
This is an architecture setting, not a confidence threshold. Checkpoint loading
recreates the same anchors; older checkpoints retain the original COCO defaults.
Anchor selection uses training geometry and validation, never held-out test results.

## Current data and split policy

The Top Down v2 export lives in `scanner/data/raw/ChessTopDown.v2-chess2.coco/` and has
327 images, 147 filename-based source groups, and 1,758 boxes.
The existing splits are preserved, not randomly re-split after augmentation:

| Split | Exported images | Source groups | Piece boxes |
| --- | ---: | ---: | ---: |
| Train | 270 | 90 | 1,431 |
| Validation | 40 | 40 | 234 |
| Test | 17 | 17 | 93 |

Training has three exported augmentations per source. Images are already stretched
to 416x416. `prepare` validates decoded sizes, class mapping, individual piece
boxes, image IDs, and source-name/hash leakage across splits. It rejects crowd
regions, corrupt images, path traversal, and invalid boxes. Manifests fingerprint
both labels and image bytes; changed images require preparation again. An unused
`chess-pieces` supercategory is not an empty-square label.

Filename grouping cannot prove that physical chess sets or capture sessions are
independent across splits. The positions are sparse (2-11 annotated pieces), and
the test set is small. Results describe this export only, not unseen real-world
boards or full opening positions. Near-duplicates with different source names
still require a manual review.

Code, configs, and a model card are versioned. Environments, prepared manifests,
weights, full predictions, and reports are ignored under `scanner/artifacts/`.
Back up the trained `best.pt` separately if you want to retain that exact run;
cloning this repository alone does not download the trained chess checkpoint.
The game's deployment requirements remain unchanged.

## Chess V2 intake and curation

The second source is staged separately in `scanner/data/raw/ChessV2.v1i.coco/`.
It is ignored by Git. It contains 2,232 images and 64,399 raw box annotations.
`datasets.py` defines each source's paths, attribution, supercategories, caveats,
and explicit class aliases. Chess V2's `BB`, `BKN`, `WR`, etc. map to the same
12 canonical classes as Top Down; no numeric category IDs are guessed.

```sh
# Rebuild the original manifest after the folder rename; fingerprint stays unchanged.
.venv-scanner/bin/python -m scanner.ml prepare --dataset top-down

# Audit the new source separately. This raw export currently FAILS validation.
.venv-scanner/bin/python -m scanner.ml prepare --dataset chess-v2
```

Chess V2 reports are written to `scanner/artifacts/chess-v2/prepared/`, not over
the existing Top Down manifest. The raw export currently has dimension mismatches,
invalid/duplicate boxes, and cross-split source groups. A failed audit exits with
a short error and writes `audit.json`; it does not publish a training manifest.
If an older manifest exists, a failed re-audit blocks it from being used.
See [CHESS_V2_INTAKE.md](CHESS_V2_INTAKE.md) for the initial findings and
[CHESS_V2_ALIGNMENT.md](CHESS_V2_ALIGNMENT.md) for the active v3 cleanup. The earlier
[v2 curation report](CHESS_V2_CURATION.md) is historical: visual training review
found additional misaligned images that its dimension audit could not detect.

Do not merge the archives, silently rotate labels, or train on the broken raw
export. The reviewed policy in `configs/chess-v2-clean-v3.json` binds corrections
to exact raw image/annotation hashes. It builds a separate curated COCO version:

```sh
# Already built locally; this will refuse to overwrite an existing version.
.venv-scanner/bin/python -m scanner.ml curate
.venv-scanner/bin/python -m scanner.ml compare
open scanner/artifacts/curation/chess-v2-v3/index.html
```

Review queue entries are excluded from every split, not guessed or silently
re-labeled by a model. Corrected rotations use lossless PNGs and preserve the
reviewed annotation coordinate system. Raw downloads and the original Top Down
benchmark remain unchanged. Exact/high-confidence redundant targets are removed;
remaining overlaps at IoU >= 0.50 are conservatively excluded for review, including
some potentially valid occlusions. Unlabeled photos are not treated as empty boards
without explicit visual verification. Similar views remain together in grouped
splits, and each split must support all classes. v3 preserves prior capture-to-split
assignments instead of moving any previously exposed validation captures into test.

To train on the cleaned copy rather than the old baseline:

```sh
.venv-scanner/bin/python -m scanner.ml train \
  --manifest scanner/artifacts/curation/chess-v2-v3/prepared/manifest.json \
  --config scanner/ml/configs/chess-v2-baseline.json \
  --output scanner/artifacts/chess-v2-another-run
```

This starts a new model run, not a resume of the Top Down checkpoint. The completed
local run is documented in [CHESS_V2_MODEL_CARD.md](CHESS_V2_MODEL_CARD.md), with
results in `chess_v2_results.json`. Its selected threshold is **0.25**. Pass both
the v3 manifest and new checkpoint explicitly when evaluating:

```sh
.venv-scanner/bin/python -m scanner.ml evaluate \
  --manifest scanner/artifacts/curation/chess-v2-v3/prepared/manifest.json \
  --checkpoint scanner/artifacts/chess-v2-baseline/best.pt \
  --split valid --output scanner/artifacts/chess-v2-baseline/validation
open scanner/artifacts/chess-v2-baseline/test/report/index.html
```

Choose each new run's threshold using its own validation set; do not tune on test.
Compare source-specific results honestly, since the larger dataset has different
holdouts from Top Down. Curation itself does not train a model or update `/scanner`.
Default training/inference still refer to Top Down unless paths are supplied.

## What to collect next

**Yes: obtain unaugmented, original-resolution images with their matching labels
where possible.** Keep the current export for comparison, but do not mix its
augmentations into validation/test when importing those originals. Labels from a
416x416 stretched export must not be copied unchanged onto a larger original.
Split source images first; generate augmentations only inside training.

Place new originals, annotations, and license notes under
`scanner/data/raw/<source-name>/`. This directory is ignored by Git. Keep reviewed
COCO exports in a separate `scanner/data/curated/<version>/` directory with
`train`, `valid`, and `test` folders. To use one, run `prepare --data` with that
export path and a new `--output` path, then pass its manifest to a new training
run. Raw photos are not automatically or silently included in training.

Prioritize the following over more slightly modified copies of the same photo:

- Full 32-piece openings and crowded 20-32-piece middlegames, not just sparse boards.
- Different physical board/piece sets: wood, plastic, tournament, light/dark colors,
  and especially kings, queens, and bishops that look similar from above.
- Different phones/cameras, distances, indoor light, mild shadows, and realistic
  glare. Start with sharp, near-top-down photos with all four board corners visible.
- Both player orientations. Record which edge is White's home rank; EXIF rotation
  alone cannot identify the intended chess orientation.
- Complete pieces and visible bases, without hands, overlays, or cropped board edges.
  Add harder angles/occlusions later as a separate challenge set.
- Empty boards and accurately labeled empty regions, plus full positions/FENs when
  known. Verify all occupied squares and all 12 piece/color classes.
- Four ordered board corners (a1, h1, h8, a8 in photo pixels), in addition to piece
  boxes. Keep orientation and square labels consistent with the full board layout.
- A source/license record and permission to train; a public download is not by
  itself permission to redistribute. Preserve attribution and consent for photos.

Use a `collection.csv` based on `collection.example.csv` to record source images,
board set, session, game, and camera. Keep related captures in one split. For a
new collection, aim around **70/15/15 train/validation/test by independent capture
groups**, not individual images; useful group diversity matters more than an exact
percentage. Keep a genuinely unseen board-set holdout. Preserve the current test
set for longitudinal comparison and never train on it.

The next engineering phase is verified corner/square ground truth, perspective
rectification, detection-to-square assignment (or a separate 13-class square
classifier), uncertain-square correction, and only then connecting `/scanner`.
An image cannot reveal prior castling rights or en passant history; those remain
explicit user confirmations. Store photos locally while collecting; do not put
private photos or large raw exports into public Git history.

## Sources and extension points

- Dataset: [Chess Top Down](https://universe.roboflow.com/chess-gftva/chess-top-down),
  **by chess**, Roboflow Universe, 2022; license **CC BY 4.0**. The export dated
  May 31, 2022 has an `undefined` author field; the live project's citation credits
  `chess`. Retain that credit, project URL, and license when redistributing.
  No upstream images were modified.
- Model: [official TorchVision SSDLite documentation](https://docs.pytorch.org/vision/stable/models/generated/torchvision.models.detection.ssdlite320_mobilenet_v3_large.html).
- Evaluation: [official COCO API](https://github.com/cocodataset/cocoapi).

`datasets.py` owns source profiles and label aliases, `data.py` validation/transforms,
`model.py` the detector/checkpoint contract,
`train.py` optimization, `metrics.py` evaluation, and `report.py` inspection output.
`curation.py` applies hash-bound reviewed decisions, `grouping.py` keeps related
captures together, `curation_report.py` documents exclusions/corrections, and
`compare.py` checks cross-source overlap without merging.
Future board geometry and web inference should be separate adapters rather than
changing the game engine or hiding guessed square labels inside training.
