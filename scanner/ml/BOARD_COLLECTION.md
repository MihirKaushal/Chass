# Verified Board Collection

The piece-box benchmark cannot measure empty-square accuracy or correct placement
on the 8x8 grid. This collection fills that gap without treating model predictions
as ground truth. Photos stay local unless you explicitly share them.

## What To Collect

- Prefer unaugmented originals and permissively licensed images. Preserve license,
  source URL and capture provenance. Keep augmented siblings in the same split.
- Prioritize different **physical chess sets**, especially Kings with unusual
  crowns, Black Kings near pawns/bishops, and White Kings near Queens.
- Include full 32-piece openings, crowded middlegames, sparse endgames, both piece
  colors, shadows, glare and varied phones. Use real top-down photos, not diagrams.
- Start with 50-100 reviewed boards across at least five physical sets. This is a
  practical collection target, not a statistically sufficient accuracy guarantee.
- Use about 70/15/15 train/validation/test **by physical set**, not random images.
  An unseen set/session test is more useful than an exact percentage. Keep the
  existing frozen benchmark unchanged and never tune from the new test split.

## Label A Board

1. In `/scanner`, crop to the actual 64-square grid, White at the bottom.
2. Download **Prepared Photo**. Keep the original separately; the exported labels
   match the prepared image's SHA-256, not the unedited original.
3. Review every square, including empty ones. Correct missing/misidentified pieces.
   Do not assume a high-confidence prediction is true. Have a second person check
   difficult Kings/Queens and tall pieces' actual bases when possible.
4. Confirm the reviewed board, then **Export For Accuracy Testing**. Keep the photo
   and JSON together under `scanner/data/verified/` (ignored by Git).
5. Add each photo hash to `groups.json`, recording its physical set, capture session
   and split. Check the exported labels again against the prepared photo before
   setting `labels_checked: true`. Prefer a second reviewer for ambiguous pieces.
   Also keep a provenance/license note alongside the collection.

```json
{
  "REPLACE_WITH_IMAGE_SHA256_FROM_EXPORT": {
    "board_set": "wooden-staunton-a", "session": "wooden-a-2026-11-07-phone-a",
    "source_group": "original-photo-or-burst-id", "split": "test", "labels_checked": true
  }
}
```

## Assemble And Measure

```sh
.venv-scanner/bin/python -m scanner.ml.board_collection collect \
  --photos scanner/data/verified/photos --exports scanner/data/verified/labels/*.json \
  --groups scanner/data/verified/groups.json --output scanner/artifacts/verified-v1.json

.venv-scanner/bin/python -m scanner.ml.board_collection score \
  --photos scanner/data/verified/photos --collection scanner/artifacts/verified-v1.json \
  --split valid --output scanner/artifacts/verified-v1-valid-results.json
```

The collector deduplicates exact photos, rejects conflicting labels, requires
matching image hashes, and prevents one physical set appearing in multiple splits.
Session IDs must identify the actual session, not a generic name such as `day1`.
Assign every recrop, rotation, and near-duplicate burst a shared `source_group`.
Sessions and source groups cannot cross splits, even if a board_set was mislabeled.
It does not detect every near-duplicate: review burst photos/derived crops manually.
The scorer records model hashes, occupancy accuracy, occupied-square type/color
accuracy, full 13-class square accuracy, whole-board accuracy, misses and inventions.
Use `--split test` only after locking the model and thresholds. No automatic training
or uploading occurs when collecting labels.

Exports now preserve the original recognized board, model hashes, changed squares,
and active review time. These are diagnostic records, not independent ground truth.
The collector requires a second explicit label check for these exports. Legacy
manually verified collections remain readable; their verification quality still
depends on the original reviewer.

Reports include occupancy precision/recall, class confusion (including empty),
per-piece misses/inventions, exact-board accuracy, required square corrections,
and whether review flags caught actual errors. Active review time is descriptive:
it excludes hidden tabs and time after confirmation and does not prove correctness.
