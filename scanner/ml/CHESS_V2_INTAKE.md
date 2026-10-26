# Chess V2 intake: October 25, 2026

Source: [Chess V2 by Public Wspace](https://universe.roboflow.com/public-wspace/chess-v2-qqtmk).
The supplied export README credits Roboflow and lists CC BY 4.0. Keep both source
credit and export license records. README reports no preprocessing or augmentation;
that is not proof that all upstream images are distinct, correctly oriented originals.

Raw directory: `scanner/data/raw/ChessV2.v1i.coco/`, approximately 967 MB.
The archive has not been modified, merged, or used for training.

## Raw inventory

| Split | Images | Box annotations |
| --- | ---: | ---: |
| Train | 1,704 | 48,801 |
| Validation | 495 | 14,436 |
| Test | 33 | 1,162 |
| Total | 2,232 | 64,399 |

The 12 foreground classes are `BB`, `BK`, `BKN`, `BP`, `BQ`, `BR`, `WB`, `WK`,
`WKN`, `WP`, `WQ`, and `WR`. The unused `Chess` supercategory is not an empty-square
class. The `chess-v2` profile explicitly maps names, not numeric IDs, to canonical
piece/color labels.

## Findings

- **97 dimension mismatches:** decoded image size disagrees with the COCO image
  record. Of these, 96 have swapped width/height. Do not assume whether pixels or
  labels need rotation, or guess clockwise versus counterclockwise. Review with
  box overlays before making a reversible correction in a curated copy.
- **88 invalid boxes** detected in dimension-matching images, including zero-area
  boxes. More issues could be hidden in the 97 mismatched images, which the audit
  skips rather than trusting their coordinate system.
- **8 exact duplicate piece boxes** with the same class and coordinates, despite
  distinct annotation IDs.
- **3 source-name groups cross train/validation:** `IMG_20220808_141918_jpg`,
  `IMG_20220808_141217_jpg`, and `IMG_20220808_140616_jpg`. Their independence is
  unproven; a corrected split must keep related source variants together.
- Hashing **all 2,232 files** found **2,204 unique byte hashes**, or **28 extra
  exact image copies**. A curated export should retain one representative with
  verified annotations, while retaining a removal/provenance log.
- **0 exact byte-hash matches with Top Down.** This does not establish visual
  independence: resizing, re-encoding, crop changes, and related capture sessions
  require perceptual/manual review before combining sources.
- Some scenes deliberately contain more than 32 pieces. One validation image has
  103 annotations. These are not necessarily illegal detector-training examples;
  inspect annotation quality and avoid treating them as legal chess positions.

The strict audit currently reports 196 failures and creates no training manifest.
It verifies dimensions for 2,135 images; that lower number is not the archive's
total. Raw counts remain separate in `declared_total_images` and
`declared_total_annotations`.

## Next preparation step

Create a **new curated version**, leaving this archive and the original Top Down
benchmark intact. Resolve or quarantine uncertain orientation/geometry, review
invalid boxes, deduplicate identical annotations and images, then group related
captures into leakage-safe splits. Compare source-specific validation separately;
do not overwrite the original baseline metrics or claim a combined-data gain from
different test sets. Only train after the curated audit passes.

No dataset re-download or paid service is required to begin this cleanup. Keep
collecting varied physical sets and good full-board images in the meantime.

Local detailed reports:
`scanner/artifacts/chess-v2/prepared/audit.json` and
`scanner/artifacts/chess-v2/intake_summary.json`.
