# Chess V2 alignment review: October 25, 2026

The active dataset is `scanner/data/curated/chess-v2-v3/`, with its manifest at
`scanner/artifacts/curation/chess-v2-v3/prepared/manifest.json`. The hash-bound
policy is `configs/chess-v2-clean-v3.json`; `alignment_results.json` records counts
and fingerprints. Raw downloads and the original Top Down checkpoint are unchanged.

## Why Another Version

An exploratory training run had poor validation scores. Visual inspection found
square images whose boxes only aligned after rotating the image. Equal width and
height meant the earlier dimension audit could not catch these. Other images
needed 180-degree turns, which likewise leave dimensions unchanged.

All 2,108 images retained in v2 were reviewed in box-overlay contact sheets for
alignment and coverage, with larger alternatives inspected where needed. A
color/occupancy score prioritized candidate rotations; it did not assign piece
classes or authorize corrections automatically. Review confirmed **324 additional
rotations** and **43 additional exclusions** for incomplete or misplaced targets.
No missing box or class label was invented. This is not an exhaustive full-size
reannotation of every piece, and imperfect box extents or class labels can remain.

## Active Dataset

| Item | Count |
| --- | ---: |
| Original raw images | 2,232 |
| Retained images | 2,065 |
| Confirmed copies removed | 26 |
| Excluded for review | 141 |
| Retained annotations | 59,452 |
| Retained images rotated relative to raw originals | 410 |
| Independent split components | 25 |

| Split | Images |
| --- | ---: |
| Training | 1,419 |
| Validation | 308 |
| Test | 338 |

All 12 classes remain represented in each split. Existing capture-to-split
assignments are fixed: retained photos never move between train, validation, and
test. Related groups must agree, or publication fails. This prevents previously
used validation images from becoming test data after a label fix. The new model
starts from official COCO weights, not a checkpoint trained on the withdrawn v2.

The v2 local audit blocks training/evaluation. Its source policy and exploratory
training artifacts remain as history, not valid accuracy results. No model test
metrics were used to choose these corrections or exclusions.

## Reproduce And Review

```sh
# Existing published versions cannot be overwritten.
.venv-scanner/bin/python -m scanner.ml curate
open scanner/artifacts/curation/chess-v2-v3/index.html
```

The local `orientation-review-v3/` artifacts include candidate scores, all reviewed
contact sheets, larger diagnostic examples, and per-image decisions. Published
`provenance.json` records raw hashes, original annotation IDs, corrections, and
capture/split lineage. Rotated images are lossless PNGs; unrotated raw image bytes
are copied unchanged. Neither raw archive is modified.

More physical chess sets, cameras, lighting conditions, and verified board-corner
and square labels are still needed for a reliable photo-to-game scanner.
Capture grouping does not prove physical-set independence. Excluded examples
can be recovered through reviewed reannotation in a later version, but they are
not required for this baseline training run.

Attribution: Chess V2 by Public Wspace, Roboflow Universe, CC BY 4.0; original
dataset README/license files are preserved in the curated export.
