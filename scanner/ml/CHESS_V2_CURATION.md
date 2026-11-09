# Chess V2 curation: October 25, 2026

**Historical, superseded by [alignment-reviewed v3](CHESS_V2_ALIGNMENT.md).**
Training-time visual inspection found additional quarter-turn/180-degree alignment
errors and incomplete annotations. The local v2 audit is now marked invalid to
prevent accidental reuse. The counts below describe the earlier curation pass,
not the active training dataset.

The earlier version is `scanner/data/curated/chess-v2-v2/`.
Its manifest and visual report live in `scanner/artifacts/curation/chess-v2-v2/`.
Machine-readable results are recorded in `curation_results.json`.

## Results

| Item | Final count |
| --- | ---: |
| Raw source images | 2,232 |
| Retained images | 2,108 |
| Removed confirmed copies | 26 |
| Excluded images requiring review | 98 |
| Retained piece annotations | 59,850 |
| Retained photos corrected by reviewed rotation | 87 |
| Independent split components | 25 |

| Split | Images | Piece annotations |
| --- | ---: | ---: |
| Train | 1,450 | 40,461 |
| Validation | 319 | 13,090 |
| Test | 339 | 6,299 |

All 12 classes are represented in each split. Every source image is accounted for:
2,108 + 26 + 98 = 2,232. Of the 28 extra byte-identical raw copies found at intake,
26 were safely removed as copies and the remaining two are in excluded examples.
The full processing log records 88 zero-area artifacts, 249 high-confidence
redundant annotations, and 13 reviewed wrong/redundant labels. Some of those belong
to images later excluded; `retained_actions` distinguishes changes actually used
in the final dataset from all processing events.

The existing model accepted a mixed batch of corrected PNG and dense JPEG inputs
with finite loss and gradients. That is an input/gradient sanity check, not an
accuracy measurement or a new trained model. The original checkpoint remains
`a1af4cedbca97a712a446ac5ee10b03f6225435cf5a607bf821c8b3f542efb15`.

## What changed

- The 12 named piece/color classes are normalized to the original detector's
  class contract. Numeric category IDs are never guessed.
- Quarter-turn direction is recorded **per reviewed image**, with its SHA-256.
  Some frames require clockwise rotation and others counterclockwise rotation.
  Repaired images are saved losslessly; labels keep their reviewed coordinate frame.
- Zero-area point artifacts and reviewed incorrect/redundant labels are removed
  with their original IDs and reasons logged. No missing box is invented.
- Same-class boxes with IoU >= 0.90 are conservatively deduplicated. Other remaining
  box overlaps at IoU >= 0.50 are excluded for manual review, not arbitrarily merged.
  This may exclude some valid but occluded pieces; safety is preferred to guessing.
- Images with unrecoverable geometry, class conflicts, or no usable labels are
  excluded. A particularly important catch was a visibly populated board with no
  annotations: it must not teach the model that those pieces are background.
- Confirmed image copies are removed only when normalized target sets agree.
  Identical images with inconsistent targets are excluded for review. Perceptual
  similarity alone is not sufficient to delete an image.
- Capture dates/families, source-name variants, decoded pixel identity, and close
  perceptual candidates are grouped before split assignment. Whole groups are
  allocated near 70/15/15, then class coverage is repaired by moving whole groups.
  Original raw split assignments are not reused as independent samples.

Every raw image is accounted for as retained, removed copy, or excluded. Original
annotation IDs, original split, source hash, new split/group, and correction history
are in `provenance.json` in the export and `events.json` in the report. Every split
must pass the standard geometry/hash/source-group audit and contain all 12 classes.
Audits also enforce the curated capture/split-group metadata.

## What was preserved

Both raw archives remain byte-for-byte unchanged under `scanner/data/raw/`.
The original Top Down model checkpoint and dataset fingerprint are unchanged.
Sources were compared for byte/perceptual overlap but were **not merged**. No
training, evaluation-score update, website inference, or production deployment
was performed as part of curation.

An initial working pass caught basic issues; a stricter final visual review found
additional overlapping labels. The superseded pass is not the active dataset.
Its audit history is archived; only the v2 manifest should be used for new training.

## Limits and anything needed externally

No account, paid service, API key, or re-download is required. The retained dataset
can be used for training immediately. To recover excluded examples later, inspect:

```sh
open scanner/artifacts/curation/chess-v2-v2/index.html
```

`review_queue.json` lists the exact files, hashes, reasons, previews, and original
annotation IDs. Those examples require reliable manual box/type/color annotation
or recovery of the correct original image/transform. Keep them excluded until
reviewed, record corrections in a new hash-bound policy, and build a new version.
Recovering them is optional and does not block training on the retained data.

This is not a manual reannotation of every piece. A passing audit cannot prove all
semantic labels are correct, and capture-day grouping cannot prove physical-set
independence. Close-candidate checks can miss arbitrary crops/perspective changes.
These detection labels still do not provide board corners, 64-square ground truth,
castling rights, or en passant history. More varied physical sets and verified board
geometry are still valuable for the eventual complete scanner.

Raw attribution: [Chess V2 by Public Wspace](https://universe.roboflow.com/public-wspace/chess-v2-qqtmk),
Roboflow Universe; supplied export README credits Roboflow and lists CC BY 4.0.
Original README/license files are retained in the curated export.
