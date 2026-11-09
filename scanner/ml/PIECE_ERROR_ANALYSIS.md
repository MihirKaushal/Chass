# Piece Error Analysis

Follow-up: the [2026-10-26 improvement run](IMPROVEMENTS.md) implements the label
overlay, duplicate experiment and crop classifier proposed here. This report
preserves the original detector-only error analysis for comparison.

Recorded **2026-10-26**, using the model trained **2026-10-25** on Chess V2 curated
v3. Test: **338 photos, 6,283 annotated pieces, 7,513 predictions** at the frozen
validation-selected confidence threshold **0.25**. No retraining or label changes.

## Which Pieces Are Confused?

Matching uses `confidence_ordered_class_agnostic_iou_v1`: the most confident
predictions claim overlapping annotated pieces first, regardless of class.
"Correct when found" requires both type and color to match among located pieces.
"Missed" means no box matched at IoU >= 0.5, regardless of predicted class.
All numbers measure agreement with annotations; they are not square accuracy.

| Actual type, colors combined | Annotated / located | Correct when found | Missed | Most frequent wrong predicted types (counts) |
| --- | ---: | ---: | ---: | --- |
| Pawn | 955 / 850 | 94.71% | 105 (10.99%) | Rook 25; bishop 11 |
| Rook | 295 / 256 | 83.20% | 39 (13.22%) | Knight 22; bishop 7 and king 7 |
| Queen | 1,304 / 1,181 | 69.09% | 123 (9.43%) | King 282; knight 56 |
| Knight | 1,265 / 1,139 | 59.88% | 126 (9.96%) | Rook 263; bishop 85 |
| King | 1,154 / 1,021 | 30.17% | 133 (11.53%) | Queen 560; knight 104 |
| Bishop | 1,310 / 1,114 | 23.16% | 196 (14.96%) | Rook 517; knight 260 |

The main patterns are **king <-> queen**, **bishop -> rook/knight**, and
**knight -> rook**. Pawns are comparatively easy to classify once localized:
there are **zero pawn -> queen errors in this test matching**, though validation
contains 20. Do not generalize a zero count to every chess set or photo.

Rooks illustrate why recall and precision answer different questions. Most real
rooks are named correctly once found, but the model also calls many other pieces
rooks. Across both colors, only **213 / 1,381 rook predictions (15.42%)** are
correct unique matches. A recognizable shape alone does not guarantee reliability.

## Differences By Color

| Actual class | Annotated | Located | Correct / located | Missed / annotated | Main wrong label (count / located) |
| --- | ---: | ---: | ---: | ---: | --- |
| Black bishop | 857 | 745 | 62 / 745 (8.32%) | 112 / 857 (13.07%) | Black rook: 419 / 745 (56.24%) |
| White bishop | 453 | 369 | 196 / 369 (53.12%) | 84 / 453 (18.54%) | White rook: 98 / 369 (26.56%) |
| Black king | 407 | 377 | 77 / 377 (20.42%) | 30 / 407 (7.37%) | Black queen: 185 / 377 (49.07%) |
| White king | 747 | 644 | 231 / 644 (35.87%) | 103 / 747 (13.79%) | White queen: 374 / 644 (58.07%) |
| Black knight | 564 | 517 | 317 / 517 (61.32%) | 47 / 564 (8.33%) | Black rook: 95 / 517 (18.38%) |
| White knight | 701 | 622 | 365 / 622 (58.68%) | 79 / 701 (11.27%) | White rook: 168 / 622 (27.01%) |
| Black pawn | 905 | 823 | 781 / 823 (94.90%) | 82 / 905 (9.06%) | Black rook: 24 / 823 (2.92%) |
| White pawn | 50 | 27 | 24 / 27 (88.89%) | 23 / 50 (46.00%) | Three different labels, once each |
| Black queen | 442 | 417 | 351 / 417 (84.17%) | 25 / 442 (5.66%) | Black king: 40 / 417 (9.59%) |
| White queen | 862 | 764 | 465 / 764 (60.86%) | 98 / 862 (11.37%) | White king: 238 / 764 (31.15%) |
| Black rook | 280 | 246 | 211 / 246 (85.77%) | 34 / 280 (12.14%) | Black knight: 21 / 246 (8.54%) |
| White rook | 15 | 10 | 2 / 10 (20.00%) | 5 / 15 (33.33%) | White bishop: 5 / 10 (50.00%) |

White pawns and white rooks have the highest miss rates, but their test supports
are only **50 and 15 pieces**. These rates are unstable. By number of misses,
black bishops (112), white kings (103), and white queens (98) are the largest
individual groups; bishops of both colors account for **196 / 722 misses**.

Color recognition remains 99.84% among matched pieces. Differences between black
and white rows can reflect lighting, style, training coverage, and capture groups;
they do not imply that color classification itself is failing.

## Missing Pieces Versus Extra Predictions

There are **722 missed annotations** and **1,952 unmatched predictions**. Extra
boxes are 2.70 times as numerous, but their causes differ:

| Unmatched prediction bucket | Count | Definition |
| --- | ---: | --- |
| Duplicate candidate | 1,812 | IoU >= 0.5 with an already matched annotation, regardless of label |
| Localization candidate | 124 | Best IoU with any annotation is at least 0.1 but below 0.5 |
| Background candidate | 16 | Best IoU with any annotation is below 0.1 |

**92.83% of unmatched predictions overlap an already detected piece.** This
suggests multiple competing labels/boxes for the same object are a much larger
problem than inventing objects on the background. Low-overlap candidates need
visual review because imperfect or missing annotations can produce the same result.

These are our overlap diagnostics, not a run of the full
[TIDE evaluation toolkit](https://www.ecva.net/papers/eccv_2020/papers_ECCV/papers/123480562.pdf).
The installed TorchVision SSD code performs suppression separately by class;
different-class boxes can survive on the same piece. See the
[SSD implementation](https://docs.pytorch.org/vision/main/_modules/torchvision/models/detection/ssd.html)
and [batched NMS definition](https://docs.pytorch.org/vision/main/_modules/torchvision/ops/boxes.html).

## Which Labels Are Overpredicted?

These are the six labels with the most incorrect predictions. A wrong label on a
real piece is separate from an unmatched extra box; each prediction is counted once.

| Predicted label | All predictions | Wrong label on matched piece | Duplicate | Poor overlap | Background candidate | Total incorrect |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Black rook | 991 | 576 | 188 | 16 | 0 | 780 |
| White queen | 1,198 | 397 | 330 | 2 | 4 | 733 |
| White king | 899 | 248 | 407 | 8 | 5 | 668 |
| Black knight | 848 | 339 | 181 | 11 | 0 | 531 |
| White rook | 390 | 297 | 87 | 4 | 0 | 388 |
| Black queen | 695 | 201 | 135 | 7 | 1 | 344 |

Looking only at extra unmatched boxes, white king (420), white queen (336), and
black rook (204) are most common. Looking only at the 16 background candidates:
white king 5, white queen 4, white pawn 4, black pawn 2, black queen 1.

## Visual Review And Label Issues

Inspected all 16 test background candidates, plus seven classification examples.
The background review found **10 predictions on apparently empty squares**, **4
on printed chess logos**, and **2 on visible pieces lacking an overlapping label**.
The empty-square count includes two competing labels at the same location.

- Image 1811: visible black piece at the lower-right board edge is unannotated; the model predicts black pawn with score 0.98.
- Image 1956: visible black piece at the right board edge is unannotated; the model predicts black queen with score 0.32.

These two objects were also checked in full photos with all annotation boxes drawn.
They are flagged for a label audit. Their exact class still needs confirmation;
they should not automatically be counted as genuine background hallucinations.
The frozen benchmark and its labels remain intact. A corrected dataset must have
a new version and fingerprint, with comparison against the old benchmark clearly labeled.
This limited review does not establish that all other labels are correct.

## What To Improve Next

1. **Audit labels for the difficult classes and missing objects.** Prioritize bishops, kings/queens, white rooks, and white pawns in training/validation. Record confirmed corrections and preserve capture-level splits. Resolve evaluation label issues under a new benchmark version.
2. **Benchmark duplicate resolution on validation.** Evaluate grouping competing boxes into one physical piece proposal, across classes. Monitor recall on adjacent pieces: overlapping boxes can belong to different pieces. Choosing one label alone will not fix a high-confidence wrong classification.
3. **Train a classifier on detailed piece crops.** The current detector processes the entire photo at 320x320, as specified by the [SSDLite architecture](https://docs.pytorch.org/vision/master/models/ssdlite.html). Median training piece size is only about 23x25 pixels after that resize. Crop from the original-resolution images before resizing for classification, using reviewed annotations and balanced sampling across the 12 classes. Preserve image/capture groups when splitting crops, and include training-only crop jitter to approximate imperfect detections. Test its value on the complete detector-plus-classifier pipeline; accurate classification on ideal ground-truth crops alone is insufficient.
4. **Add varied sets and verified board geometry.** New sets should emphasize the confusion pairs above. Correct board boundaries can exclude border logos and later constrain proposals to individual squares. Keep uncertain labels reviewable and evaluate on an unseen physical-set holdout.

The proposed crop classifier is the main model experiment; duplicate resolution
is a smaller validation experiment alongside it. Model selection and thresholds
must use validation. This investigation has exposed test errors, so a new unseen
board-set holdout is especially useful for an honest final evaluation.

The validation/test classification gap also reflects class composition: pawns
are **53.84% of matched validation pieces** but only **15.29% of matched test
pieces**. Reweighting validation per-class accuracies by the test matched-class
counts yields **61.82%**, compared with original validation 78.90% and test 55.42%.
This arithmetic diagnostic is not a corrected score or causal explanation, but
shows why future reports should include per-class and balanced averages.

## Reproduction And Evidence

- [Analysis JSON](benchmarks/chess-v2-v3-piece-errors/analysis.json), including validation and test counts.
- [Actual-class CSV](benchmarks/chess-v2-v3-piece-errors/test-by_actual_class.csv), [predicted-label CSV](benchmarks/chess-v2-v3-piece-errors/test-by_predicted_class.csv), and [confusions CSV](benchmarks/chess-v2-v3-piece-errors/test-confusions.csv).
- [Visual review observations](benchmarks/chess-v2-v3-piece-errors/visual-review.json), with exact image IDs and boxes.
- Local review contact sheets: `scanner/artifacts/chess-v2-baseline/piece-error-review/` (ignored by Git).

Run `python -m scanner.ml.piece_errors` in `.venv-scanner`, with `--snapshot`,
`--manifest`, `--artifacts`, `--recorded-on`, and a new `--output` directory.
Optional `--review` writes the per-detection evidence into a local directory.
Input fingerprints and saved prediction hashes must match the frozen snapshot.
The report's counts are checked against the original matching diagnostics.
