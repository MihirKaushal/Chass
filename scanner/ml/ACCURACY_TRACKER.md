# Scanner Accuracy Tracker

Last recorded: **2026-10-26**. Current classifier trained: **2026-10-26**;
detector remains the **2026-10-25** checkpoint.
This log separates measurable piece-box diagnostics from future square-level
accuracy. Historical snapshots below remain intact.

## Latest Improvement: Crop Classifier And Duplicate Resolution

The new pipeline was selected on validation, then evaluated on the same 338-photo,
6,283-piece curated-v3 test set. See [IMPROVEMENTS.md](IMPROVEMENTS.md) for training,
all four ablations, corrected-label results, local testing and limitations.

| Box-level measure | Previous detector | Selected combined pipeline |
| --- | ---: | ---: |
| Correct type + color among located pieces | 55.42% (3,082 / 5,561) | **96.32% (5,342 / 5,546)** |
| Correctly typed pieces / all real pieces | 49.05% | **85.02%** |
| Correct unique pieces / all predictions | 41.02% | **94.30%** |
| Localization recall, ignoring type/color | 88.51% | **88.27%** |
| Missed pieces | 722 | **737** |
| Unmatched extra boxes | 1,952 | **119** |

Classification and duplicate errors improved substantially; detector misses did
not. Suppression loses 15 previously localized pieces. New per-piece conditional
accuracies: bishop 95.14%, king 91.85%, knight 99.21%, pawn 98.47%, queen 97.20%,
rook 95.26%. The data still has limited set diversity and small white-rook/pawn
test samples. These are development-benchmark results, not an unseen-set guarantee.

The v4 annotation-only overlay adds two visually verified missing test objects.
Re-scoring both models on those same corrected labels gives 55.44% -> 96.32%
conditional type/color accuracy. The original v3 comparison above is preserved
to isolate model changes from annotation changes.

Machine-readable records: [results JSON](benchmarks/chess-v2-v3-crops-v1/results.json),
[metrics CSV](benchmarks/chess-v2-v3-crops-v1/metrics.csv), and
[training history](benchmarks/chess-v2-v3-crops-v1/training-history.json).
Use the `labels`, `pipeline`, and `split` columns to compare like-for-like results.

## The Three Requested Metrics

| Question | Current result | Why |
| --- | --- | --- |
| Is each square correctly empty or occupied? | **Not measured** | A prototype square mapper now exists, but there is no verified 64-square evaluation collection yet. |
| On correctly detected occupied squares, is the piece type and color correct? | **Not measured at square level** | The closest current box-level diagnostic is **96.32%** type-and-color accuracy among localized pieces. |
| Is each square completely correct: empty, or the exact piece and color? | **Not measured** | Requires both of the above and correct assignment to the actual square. |

These unavailable metrics are `null` in JSON and blank in CSV, **not zero**.
The detector's background class is not a verified empty-square prediction.
Neither image dimensions nor piece bounding boxes establish an 8x8 board grid;
dividing every photo into 64 equal cells would give misleading accuracy.

## Archived Detector-Only Test Results: 2026-10-25

Benchmark: **Chess V2, curated v3**, 338 photos and 6,283 annotated pieces.
Confidence threshold: **0.25**, selected on validation, not on test.
The table below uses one-to-one box matching, ignoring class until after matching.

| Measure | Numerator / denominator | Result |
| --- | ---: | ---: |
| Real pieces located, ignoring type/color (localization recall) | 5,561 / 6,283 | **88.51%** |
| Predicted boxes matching real pieces (localization precision) | 5,561 / 7,513 | **74.02%** |
| Localization F1 | 2 x 5,561 / (7,513 + 6,283) | **80.62%** |
| Correct piece type among matched pieces, ignoring color | 3,085 / 5,561 | **55.48%** |
| Correct color among matched pieces, ignoring type | 5,552 / 5,561 | **99.84%** |
| Correct type AND color among matched pieces | 3,082 / 5,561 | **55.42%** |
| Matched location + correct type/color among ALL predicted boxes | 3,082 / 7,513 | **41.02%** |
| Real pieces matched with correct type/color | 3,082 / 6,283 | **49.05%** |

There are **722 missed pieces**, **1,952 unmatched predictions**, and **2,479
localized pieces with incorrect type and/or color**. Unmatched predictions include
duplicate/alternative labels for real pieces as well as other false alarms; they
are not a count of falsely occupied empty squares.

Assessment: useful localization baseline, **not good enough for reliable automatic
board reconstruction**. Roughly one in nine real pieces is missed and one in four
predicted boxes is unmatched. Color recognition is strong on matched pieces, but
piece type is the main bottleneck. These scores measure agreement with existing
annotations; remaining label errors and limited physical-set diversity also matter.

## Piece-Specific Findings: 2026-10-26

Full results, per-color tables, visual review, and recommendations are in
[PIECE_ERROR_ANALYSIS.md](PIECE_ERROR_ANALYSIS.md). These use the same frozen
predictions and matching protocol as the current baseline.

| Actual piece, colors combined | Correct type/color when located | Missed / annotated | Main confusion |
| --- | ---: | ---: | --- |
| Pawn | 805 / 850 (94.71%) | 105 / 955 (10.99%) | Rook |
| Rook | 213 / 256 (83.20%) | 39 / 295 (13.22%) | Knight |
| Queen | 816 / 1,181 (69.09%) | 123 / 1,304 (9.43%) | King |
| Knight | 682 / 1,139 (59.88%) | 126 / 1,265 (9.96%) | Rook |
| King | 308 / 1,021 (30.17%) | 133 / 1,154 (11.53%) | Queen |
| Bishop | 258 / 1,114 (23.16%) | 196 / 1,310 (14.96%) | Rook, then knight |

Of **1,952 unmatched predictions**, **1,812 (92.83%)** overlap an already matched
piece, **124** have insufficient overlap, and **16** have IoU below 0.1 with all
annotations. Visual inspection of those 16 found 10 predictions on apparently
empty squares, four on printed logos, and two on visible unannotated pieces.
Thus the extra-box count is mostly duplicates; it is not a background hallucination
count. There are **722 missed annotated pieces** and **2,479 wrong labels on
matched pieces**, making type recognition the larger current problem.

White pawns (23/50 missed) and white rooks (5/15 missed) have the highest miss rates,
but very small test samples. Black bishops have the most misses by individual
class (112). Black rook, white queen, and white king are the most frequent
incorrect predicted labels when counting misclassification and extras together.

These priorities were implemented in the 2026-10-26 improvement run above. Next:
improve detector recall and piece-base/square assignment with varied new photos
and a verified unseen board-set holdout. The two flagged missing annotations
are now addressed by the versioned v4 overlay.

Detailed counts and confusion matrices are stored as
[JSON](benchmarks/chess-v2-v3-piece-errors/analysis.json) and
[per-class CSV](benchmarks/chess-v2-v3-piece-errors/test-by_actual_class.csv).

## Methods And Existing Detection Metrics

Diagnostic method ID: `confidence_ordered_class_agnostic_iou_v1`.

1. Keep predictions with confidence at least the validation-selected threshold.
2. Process each photo's predictions from highest to lowest confidence.
3. Match each to the highest-IoU unmatched annotated piece if IoU is at least 0.5.
4. Only then compare piece type and color; each box/annotation is used at most once.
5. Keep unmatched predictions as false alarms. No new suppression or threshold tuning.

Conditional classification excludes unmatched predictions and missed pieces, so
also track the all-prediction precision and all-piece recall above. No square
localization has been verified by these box matches.

The original **class-aware** detection metrics are preserved separately: test
mAP@0.5 **49.25%**, precision **49.47%**, recall **59.16%**, F1 **53.89%**.
They match only boxes with the correct class, so a lower-confidence correct label
can match even if a higher-confidence wrong label overlaps the same piece. That
explains their 3,717 correct detections versus the diagnostic's 3,082. Do not mix
these matching protocols or call mAP "total square accuracy."

The existing exact-detection-set result is **0 / 338 photos** with every annotation
matched and no extras under class-aware matching. This is not exact-board accuracy.

## Dataset And Experiment History

Both runs use TorchVision SSDLite320 MobileNetV3-Large with a COCO-pretrained
backbone/box regressor and a chess-specific 12-class head. See the linked model
cards and JSON snapshots for complete settings and per-class results.

| Training date | Run / dataset | Train / valid / test photos | Training boxes | Best epoch | Test mAP@0.5 | Located-piece type + color |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 2026-10-24 | Top Down baseline | 270 / 40 / 17 | 1,431 | 12 | 72.65% | 82.19% (60 / 73) |
| 2026-10-25 | Chess V2 curated v3 | 1,419 / 308 / 338 | 40,307 | 14 | 49.25% | 55.42% (3,082 / 5,561) |

**These are different benchmarks, not an improvement/regression curve.** The
original holdout is small and sparse; the larger holdout has different capture
groups and piece distributions. Do not plot them as if only model quality changed.
Superseded v2 exploratory runs are excluded from this history.

The v3 run uses 320x320 CPU pre-resizing, small-object anchor scales, AdamW,
three frozen-backbone warmup epochs, then full fine-tuning and cosine decay.
Seed 42; 24 epochs completed; checkpoint selected by validation mAP@0.5.
Validation localization recall is **86.16%** and matched type/color accuracy
**78.90%**, versus test **88.51%** and **55.42%** respectively. The classification
gap and limited capture-group diversity need further investigation.

- [Current model card](CHESS_V2_MODEL_CARD.md)
- [Original model card](MODEL_CARD.md)
- [Current JSON snapshot](benchmarks/chess-v2-v3-baseline.json) and [chart-ready CSV](benchmarks/chess-v2-v3-baseline.csv)
- [Original JSON snapshot](benchmarks/top-down-baseline.json) and [chart-ready CSV](benchmarks/top-down-baseline.csv)

Snapshots preserve dates, split sizes, dataset fingerprints, checkpoint/prediction
hashes, settings, counts, confusion tables, and both matching protocols. CSV rates
are fractions from 0 to 1. Keep validation and test separate in charts, and group
comparisons by dataset fingerprint, split, and diagnostic method. Hashes identify
the archived files; they do not establish independent physical chess sets.

## Recording The Next Run

After training/evaluation, export the already-saved predictions to a **new** snapshot
filename using `python -m scanner.ml.benchmark` in `.venv-scanner`. For example,
this reproduces the current diagnostic in an ignored scratch directory:

```sh
.venv-scanner/bin/python -m scanner.ml.benchmark \
  --results scanner/ml/chess_v2_results.json \
  --manifest scanner/artifacts/curation/chess-v2-v3/prepared/manifest.json \
  --artifacts scanner/artifacts/chess-v2-baseline \
  --run-id chess-v2-v3-baseline \
  --recorded-on 2026-10-26 \
  --output scanner/artifacts/benchmark-check/chess-v2-v3-baseline.json
```

The command validates dataset fingerprints and prediction coverage, reproduces
the recorded class-aware detection counts, writes JSON plus CSV, and refuses to
overwrite an existing snapshot. It does not run inference, retrain, or tune.
For a future run, supply that run's results, manifest, artifacts, ID, and actual
recording date; retain its versioned snapshot under `scanner/ml/benchmarks/` and
append a row here. Preserve older entries rather than replacing their scores.

## Future Square-Level Benchmark

Create a frozen set of real-board photos with verified orientation, four corners,
and an exact empty/piece/color label for every square. Evaluate the entire image
pipeline, including user-confirmed geometry if that is the product workflow.

- **Occupancy accuracy:** (correctly empty + correctly occupied) / all squares.
- **Conditional type/color accuracy:** exact piece/color matches / squares that are truly occupied AND predicted occupied.
- **Typed occupied precision:** exact piece/color matches / all predicted occupied squares, including false alarms.
- **Total 13-class square accuracy:** (correctly empty + exact piece/color matches on the correct square) / all squares.
- **Exact-board accuracy:** boards with all 64 labels correct / evaluated boards.

Also retain occupied precision/recall and class-balanced scores: many empty squares
can inflate overall accuracy. Keep physical-set/session holdouts and verify labels.
Do not train or select thresholds against the held-out test set.
