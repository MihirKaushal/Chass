# Piece detector baseline: v2 / seed 42

Trained and evaluated locally on October 24, 2026. This is a research baseline,
not a production board-recognition release. See `baseline_results.json` for the
machine-readable metrics and dataset/checkpoint hashes.

## Training

- TorchVision SSDLite320 MobileNetV3-Large, initialized with COCO pretrained weights;
  the classification head is replaced with 12 chess piece/color classes + background.
- Existing v2 split: 270 train / 40 validation / 17 test images; 90 / 40 / 17
  filename-based source groups. Total: 1,758 annotated piece boxes.
- Batch 8, seed 42, AdamW; head learning rate 0.003 and backbone rate 0.0003.
  Three head-only warmup epochs, followed by full fine-tuning and cosine decay.
- Configured maximum 30 epochs, early stopping patience 10 on validation mAP@0.5.
  Stopped at epoch 22; best checkpoint is epoch 12. Epoch compute totaled about
  149 seconds on Apple M4 MPS (excluding download, setup, and initial evaluation).
- No test images are used in gradient updates, checkpoint selection, or confidence
  threshold selection. Existing export augmentations stay in their original split.
- Validation F1 selected confidence threshold **0.20** from a fixed 0.10-0.90 sweep
  in 0.05 increments. Test was evaluated once with that fixed threshold.

## Results

| Metric | Validation (40 images) | Held-out test (17 images) |
| --- | ---: | ---: |
| mAP@0.5 | 66.47% | 72.65% |
| mAP@0.5:0.95 | 33.75% | 35.49% |
| Precision at threshold 0.20, IoU >= 0.5 | 72.46% | 72.94% |
| Recall at threshold 0.20, IoU >= 0.5 | 64.10% | 66.67% |
| F1 | 68.03% | 69.66% |
| Correct / extra / missed detections | 150 / 57 / 84 | 62 / 23 / 31 |
| Images with all annotated detections correct and no extras | 1 / 40 | 2 / 17 |

The untrained chess head had **1.05% validation mAP@0.5**, compared with 66.47%
after fine-tuning. mAP is an object-detection metric, **not** piece-classification
accuracy or 64-square board accuracy. All-detections-correct also does not verify
square assignment, board orientation, legality, or unlabeled objects.

## Limitations and next data priorities

The current model misses pieces and confuses some bishops, queens, rooks, and
knights. Test black bishops have zero recall at the chosen threshold (only three
examples); white bishops have 1/3 recall and black queens 2/4. These tiny supports
cannot establish stable class-level reliability. Manual correction is necessary.
Visual inspection also shows clipped edge pieces and potentially incomplete
annotations; preserve the original evaluation set and create separately versioned,
reviewed labels rather than silently changing it.

The export contains sparse boards (2-11 pieces), 416x416 stretching, pre-existing
augmentation, and few apparent physical sets. Source filenames and exact byte
hashes do not reveal every near-duplicate or shared capture session. Results may
be optimistic for truly unseen sets; the small test set also has high uncertainty.
No full-board or outside-source generalization claim is made.

Prioritize licensed unaugmented originals, dense positions, different physical
sets, complete 12-class annotations, ordered board corners, and verified square
layouts. Group new splits by physical set/session/game and keep an unseen-set
holdout. See the collection checklist in `README.md`.

## Local artifacts and use

- Trained checkpoint: `scanner/artifacts/baseline/best.pt` (about 27 MB including
  training state); latest resume checkpoint: `last.pt` in the same directory.
- Inspection report: `scanner/artifacts/test/report/index.html`.
- CLI example output: `scanner/artifacts/example/annotated.jpg` and `prediction.json`.
- Validation/test predictions, per-class metrics, training history, and dependency
  snapshot are stored under `scanner/artifacts/`.

Artifacts are local and excluded from Git. Back up the checkpoint if needed; the
repository contains the reproducible pipeline, not a downloadable trained model.
The first test-image CLI prediction was also checked on CPU. No FastAPI, browser
inference, automatic FEN creation, or scanner-page connection is deployed.

Dataset attribution: [Chess Top Down Dataset by chess](https://universe.roboflow.com/chess-gftva/chess-top-down),
Roboflow Universe, 2022, CC BY 4.0. The model is derived from TorchVision's official
COCO-pretrained SSDLite weights; retain applicable upstream licenses and attribution
if publishing model downloads. No original dataset files were altered.
