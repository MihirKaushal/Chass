# Scanner Improvement Run: 2026-10-26

The selected local pipeline is the existing SSDLite detector, cross-class duplicate
suppression, and a new ResNet18 piece-crop classifier. The game server and its
deployment requirements are unchanged. `/scanner` remains unlinked and experimental.

## Measured Results

Same frozen Chess V2 curated-v3 test set: 338 photos, 6,283 annotated pieces.
All rows use confidence-ordered, class-agnostic matching at IoU >= 0.5 and the
original validation-selected detector threshold 0.25. These are **box-level**
results, not square or complete-board accuracy.

| Pipeline | Correct type/color among located pieces | Correctly typed pieces / all real pieces | Correct unique pieces / all predictions | Missed pieces | Unmatched extra boxes |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original detector | 55.42% | 49.05% | 41.02% | 722 | 1,952 |
| Duplicate suppression only | 55.43% | 48.93% | 54.26% | 737 | 119 |
| Crop classifier only | 96.33% | 85.26% | 71.30% | 722 | 1,952 |
| **Combined, selected on validation** | **96.32%** | **85.02%** | **94.30%** | **737** | **119** |

The combined pipeline correctly labels 5,342 of 5,546 located pieces. Localization
recall is 88.27% (baseline 88.51%). Suppression removes 1,833 unmatched boxes but
also loses 15 formerly localized pieces. It does not improve detector recall.
Remaining error buckets: 204 wrong labels, 737 misses, 1 duplicate candidate,
103 poorly localized extra boxes, and 15 low-overlap background candidates.
Two of the latter are actually missing annotations, addressed below.

| Actual piece, both colors | Before: correct when located | After: correct when located | After: correct / located |
| --- | ---: | ---: | ---: |
| Bishop | 23.16% | 95.14% | 1,056 / 1,110 |
| King | 30.17% | 91.85% | 935 / 1,018 |
| Knight | 59.88% | 99.21% | 1,129 / 1,138 |
| Pawn | 94.71% | 98.47% | 835 / 848 |
| Queen | 69.09% | 97.20% | 1,146 / 1,179 |
| Rook | 83.20% | 95.26% | 241 / 253 |

Color accuracy is 99.96% among located pieces. White rook/pawn test support is
still small; per-color results and confusion matrices are in the report below.

The v4 label overlay adds a visually confirmed black pawn in image 1811 and
black queen in image 1956. It preserves all images, groups, splits, and existing
labels. On these corrected labels, the unchanged combined predictions correctly
classify 5,344 / 5,548 located pieces (96.32%), with 117 extra boxes and 737 misses.
The original model is also re-scored on v4: 55.44% conditional classification.
Neither version replaces the other in the records.

## Training And Selection

- Original detector checkpoint stays unchanged, SHA-256 `88e3093f50114d1c18356b7057027184a6a6f01b99810dd33d62c54ee650105f`.
- Classifier: ImageNet-pretrained ResNet18, 12 type/color classes, 160x160 crops taken from original-resolution photos with 15% context and aspect-preserving padding.
- Last two residual stages and classification head fine-tuned. Frozen earlier stages keep fixed batch-normalization statistics.
- Balanced class sampling: 12,000 training draws per epoch; 12 epochs, batch 48. Training-only affine/color augmentation. All crops retain their original image/capture split.
- AdamW: head LR 0.001, backbone LR 0.0001; label smoothing 0.05. Full configuration and training history are archived.
- Best epoch: 8, chosen by validation macro-F1 96.61%. Validation crop accuracy 97.32%; test **ground-truth-crop** accuracy 95.83%. Those crop-only scores are separate from the detector-box pipeline results above.
- Training took 468 seconds (7.8 minutes), excluding crop-cache generation and official weight download, on this Apple M4 using MPS.
- Duplicate IoU thresholds 0.4/0.5/0.6/0.7/0.8 were compared on validation. IoU 0.4 maximized localization F1 while retaining at least 99% of baseline localized validation pieces. Combined pipeline then selected by validation typed F1, before test evaluation.
- Classifier SHA-256: `898698856d0c44ec82338f84aab9f6a0b5cc726a67645279deb50be2d7b7e4ce`.

We reviewed 288 sampled train/validation crops and recorded their identities.
No unambiguous class swaps were established in that sample. This is not a claim
that every label was verified. The two missing test labels were checked in full
photos and enlarged original-resolution crops, with manually reviewed bounds.

## Local Test

Dependencies and trained artifacts are already present on this machine. From the
repository root, start the separate scanner API:

```sh
./scanner/run-local.sh
```

Keep the frontend running via `./run.sh` or `npm run dev --prefix frontend`, then
open `http://localhost:5173/scanner`. Upload a photo, apply the crop/rotation with
White's home rank at the bottom, and click **Recognize Pieces**. Check all squares,
not just gold-marked uncertain ones. Pieces can be replaced/erased, edits undone,
and the original scan restored.

Only the photo section initially appears; board review and game-details controls
appear after recognition. **Continue-game buttons are still disabled**: this
iteration connects recognition and correction, not game-state import. A photo
cannot establish historical castling rights, en passant, or draw counters.

**Save Prepared Photo** downloads exactly the uploaded cropped image. After
checking every square and confirming the board, **Export Reviewed Labels** saves
the 64 labels with that photo's SHA-256 and orientation. Keep both files together
for future square-accuracy evaluation. These labels are manually verified data,
not automatic ground truth; incorrect confirmations would corrupt the benchmark.

The local API uses port 8001 and does not persist uploads or send photos to a
third-party AI service. It validates format, byte/pixel limits, and square aspect;
only one inference runs at a time. Stale frontend requests are cancelled/discarded.
Images remain in process memory only during handling. Classifier scores and gold
review thresholds are heuristics, not calibrated correctness probabilities.

Do not expose this development API publicly: it has no authentication or shared
hosting resource controls. The production website does not connect to localhost
or upload photos automatically. `VITE_SCANNER_API_URL` is an explicit override;
leave it unset on Vercel for now. `SCANNER_ALLOWED_ORIGINS` defaults to the local
Vite origins. No Render/Firebase configuration change is required.

Measured warm inference median: 68.5 ms, range 56-242 ms over 14 warm calls;
first inference 2,185 ms, model loading 438 ms. Five fixed test photos were used,
three repetitions each. These timings exclude file decode, HTTP, and UI work;
they are not a production latency guarantee. An actual local HTTP smoke request
returned a board in about 422 ms, including 366 ms inference.

## Reproduce

On a new machine, create `.venv-scanner` and install
`scanner/ml/requirements-dev.txt` (or `scanner/requirements-service.txt` for
inference). Raw data, caches and model weights are intentionally not in Git;
back up `scanner/artifacts/crop-classifier-v1/best.pt`, the detector checkpoint,
and `scanner/artifacts/improvements/experiment-v1/selection.json` together.
The loader verifies both checkpoint hashes against that selection file.

```sh
# Run directories are immutable; choose fresh names for subsequent experiments.
.venv-scanner/bin/python -m scanner.ml.classifier \
  --manifest scanner/artifacts/curation/chess-v2-v3/prepared/manifest.json \
  --cache scanner/artifacts/crops/chess-v2-v3-160 \
  --output scanner/artifacts/crop-classifier-v1

.venv-scanner/bin/python -m scanner.ml.experiment \
  --manifest scanner/artifacts/curation/chess-v2-v3/prepared/manifest.json \
  --artifacts scanner/artifacts/chess-v2-baseline \
  --checkpoint scanner/artifacts/crop-classifier-v1/best.pt \
  --output scanner/artifacts/improvements/experiment-v1

.venv-scanner/bin/python -m scanner.ml.inference YOUR_ACTUAL_PHOTO.jpg
# Add --rectified only for a playing-grid crop with White at the bottom.
.venv-scanner/bin/python -m pytest scanner/ml/tests
npm test --prefix frontend
npm run build --prefix frontend
```

The official pretrained weights download needs a trusted CA bundle. This Mac's
run used `SSL_CERT_FILE=/etc/ssl/cert.pem`; HTTPS verification was not disabled.
Local inference does not download weights.

`label_review.py` reproduces the v4 annotation-only overlay from
`configs/chess-v2-v4-label-review.json`. `experiment_report.py` verifies saved
prediction counts and exports old/new label comparisons without rerunning or
tuning the models. `square_benchmark.py` computes occupancy, exact occupied-piece,
all-square and exact-board accuracy **only** from verified 64-square annotations
with matching photo hashes; it rejects missing/duplicate images or unverified labels.

## Remaining Work And Your Data Collection

The main remaining bottleneck is now **missed pieces and square assignment**, not
most piece-type confusions. The current bbox-center mapper can assign tall/tilted
pieces to neighboring squares. It is a reviewable prototype, not a validated
board-corner or piece-base model. Square accuracy remains unmeasured until we have
verified board labels. Clipping tops of tall pieces when cropping can also hurt.

Collect unaugmented originals from varied physical chess sets, board colors,
lighting and camera angles. Include crowded opening/middlegame positions and
examples of kings, bishops, white pawns and white rooks. Retain empty squares,
shadows and board-edge logos as background examples; do not label them as pieces.
Record the source/license, physical set ID and capture session. Keep a whole new
physical set or session entirely held out; do not distribute near-duplicate photos
of one setup across train/validation/test. Existing sources must be deduplicated
against each other before merging.

For a small evaluation collection, also save the four board corners, orientation,
and manually confirmed 64-square layout. No new cloud accounts or paid tools are
needed. The current test errors have already been inspected during development,
so the next unseen physical-set collection is important for an honest final score.

## Verification

129 Python scanner tests and 182 frontend tests pass; Ruff and the Vite production
build pass. A real local HTTP request exercised the trained detector, classifier,
square mapper and JSON response. Tests cover malformed images, format/size limits,
untrusted browser origins, unavailable models, model failures, concurrent requests,
duplicate handling, crop boundaries, label provenance, square metrics, and frontend
response/cancellation handling. The service remains responsive during inference.

The initial `/scanner` page was checked in Chrome. Full upload-to-correction browser
automation was blocked by the browser extension's file-upload permission, so that
interactive flow still needs a manual check. Normal website uploads do not require
changing extension settings. This is a testing limitation, not an API test failure.

## Recorded Evidence

- [Full results and corrected-label comparison](benchmarks/chess-v2-v3-crops-v1/results.json)
- [Chart-ready metrics CSV](benchmarks/chess-v2-v3-crops-v1/metrics.csv)
- [Per-type test results](benchmarks/chess-v2-v3-crops-v1/test-by_actual_type.csv)
- [Per-color/class test results](benchmarks/chess-v2-v3-crops-v1/test-by_actual_class.csv)
- [Training history](benchmarks/chess-v2-v3-crops-v1/training-history.json)
- [Sampled label audit](benchmarks/label-audit-2026-10-26.json)
