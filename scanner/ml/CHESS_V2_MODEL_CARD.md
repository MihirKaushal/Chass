# Chess V2 v3 piece detector

Trained and evaluated locally on October 25, 2026. This is a working **research
baseline**, not a production photo-to-board scanner. It still makes substantial
piece-type errors, so manual correction is necessary. Nothing has been deployed
or connected to the `/scanner` page.

Machine-readable results: [chess_v2_results.json](chess_v2_results.json).
The original [Top Down model and benchmark](MODEL_CARD.md) are preserved.

## Data And Training

| Split | Images | Annotated piece boxes |
| --- | ---: | ---: |
| Training | 1,419 | 40,307 |
| Validation | 308 | 12,862 |
| Held-out test | 338 | 6,283 |
| Total | 2,065 | 59,452 |

There are 12 foreground piece/color classes plus background. Background does not
mean a verified empty chess square. The [v3 alignment review](CHESS_V2_ALIGNMENT.md)
corrected additional image rotations and excluded unresolved annotations before
this run. All retained photos keep their prior capture-level split assignments.
The exploratory v2 runs were withdrawn and were not used to initialize this model.
Raw archives and the original Top Down checkpoint remain unchanged.

- TorchVision SSDLite320 MobileNetV3-Large, with official COCO pretrained backbone
  and box-regression weights and a newly initialized chess classification head.
- Seed 42; batch 8; AdamW; head learning rate 0.003, backbone rate 0.0003, weight
  decay 0.0001. Three frozen-backbone warmup epochs, then full fine-tuning with
  cosine learning-rate decay. Training-only horizontal flips and mild brightness/
  contrast variation; no test augmentation or training on test photos.
- Small-object anchor scales `[0.06, 0.12, 0.24, 0.4, 0.6, 0.8, 1.0]`, selected
  using training-box geometry and validation. COCO's default smallest anchor was
  much larger than a typical piece in these photos at detector resolution.
- CPU bilinear resize to the detector's fixed 320x320 input before GPU transfer,
  with boxes scaled together. Evaluation and inference restore original pixel
  coordinates. Two persistent data-loader workers; four main Torch CPU threads.
- Apple M4 MPS, Python 3.13.12, Torch 2.14.1, TorchVision 0.29.1. Epoch training
  and validation totaled **1,544 seconds, about 25.7 minutes**. This excludes data
  review, curation, interrupted exploratory runs, setup, and final evaluation.
- Maximum 30 epochs; early stopping after 10 epochs without improved validation
  mAP@0.5 stopped at **epoch 24**. The selected checkpoint is **epoch 14**.
- Confidence threshold **0.25** selected by validation micro F1 over 0.10-0.90
  in 0.05 increments, preferring a higher threshold on an exact tie. Test evaluated
  once with that fixed threshold; no model or threshold changes followed test results.

## Results

| Metric | Validation | Held-out test |
| --- | ---: | ---: |
| Detection mAP@0.5 | 58.36% | 49.25% |
| Detection mAP@0.5:0.95 | 32.66% | 25.81% |
| Precision, threshold 0.25 / matching IoU >= 0.5 | 70.33% | 49.47% |
| Recall | 72.32% | 59.16% |
| F1 | 71.31% | 53.89% |
| Correct / extra / missed class-aware detections | 9,302 / 3,924 / 3,560 | 3,717 / 3,796 / 2,566 |
| Images with every annotation matched and no extras | 1 / 308 | 0 / 338 |

**These are bounding-box detection metrics, not 64-square board accuracy.** Even
the all-detections-matched metric does not verify squares, orientation, legality,
unlabeled objects, castling rights, or en passant history. No fully correct
class-aware test detection set was achieved at the selected threshold.

Test inference averaged about **27 ms per image** in batches of eight on MPS,
including input decoding/preprocessing and output transfer. This is warm local
batched throughput, not single-photo browser latency or application startup time.
The checkpoint also completed a real single-photo CPU CLI inference check.

The original Top Down model's test score used a different, much smaller, sparse
dataset. Its 72.65% mAP@0.5 is **not directly comparable** to this test result.

## Error Analysis And Limits

At the fixed threshold, a separate class-agnostic greedy IoU check localized
5,561 of 6,283 annotated test pieces (**88.51%**), showing that type recognition
is a major bottleneck. This diagnostic does not replace the class-aware metrics.
Frequent confusions included black Bishop -> black Rook and white King <-> white
Queen. Visual review confirmed missed pieces and overlapping alternative predictions.

Black Pawns were strongest by test AP@0.5 (87.17%). White Rooks were especially
weak (0.89% AP; 2/15 recalled at the operating threshold), and white Pawns also
struggled. Only 15 white Rooks and 50 white Pawns occur in test; class-level results
on these small supports are unstable and should not be generalized.

The splits contain 25 connected capture components: 20 training, two validation,
three test. Grouping prevents known related frames crossing splits, but does not
prove independence of physical chess sets. Similar green/white boards and piece
styles dominate. This benchmark does not establish reliability on a new household
board, phone, or lighting condition. Contact-sheet alignment review is not complete
piece-type reannotation, and residual box/semantic errors may remain. Model confidence
scores are not calibrated probabilities that a board is correct.

The next useful experiments are higher-resolution recognition or a second-stage
classifier on full-resolution piece crops, plus more varied physical sets and
carefully verified labels for similar-looking pieces. Choose future changes on
training/validation data; keep this test result frozen and add a genuinely unseen
board-set holdout rather than tuning against these test errors.

## Local Artifacts

Under `scanner/artifacts/chess-v2-baseline/`:

- `best.pt`: selected checkpoint, about 27 MiB including training state.
- `last.pt`: epoch-24 checkpoint, retained for inspection/resume.
- `config.json`, `provenance.json`, `environment-lock.txt`, `history.json`,
  `training.log`, `evaluation-protocol.json`, and `training-curves.png`.
- `validation/` and `test/`: metrics, predictions, paired ground-truth/prediction
  HTML reports; `test/error-analysis.json` records diagnostic type confusions.
- `example-cpu/annotated.jpg` and `prediction.json`: verified CPU CLI output.

Checkpoint SHA-256:
`88e3093f50114d1c18356b7057027184a6a6f01b99810dd33d62c54ee650105f`.

Dataset fingerprint:
`b09efd5f13d48aff4e5de0b8980c4d92f494d0177613bae0e1473d98330d3e81`.

Artifacts and weights are local and ignored by Git. A clone contains pipeline,
policies, configuration, and results, not the trained checkpoint or large dataset.
ML dependencies remain isolated from the game backend.

## Reproduce And Predict

Use a **new output directory** to retrain; the CLI refuses to overwrite a run:

```sh
.venv-scanner/bin/python -m scanner.ml train \
  --manifest scanner/artifacts/curation/chess-v2-v3/prepared/manifest.json \
  --config scanner/ml/configs/chess-v2-baseline.json \
  --output scanner/artifacts/chess-v2-another-run

open scanner/artifacts/chess-v2-baseline/test/report/index.html
```

This example uses a real local validation photo, not a nonexistent placeholder:

```sh
PHOTO="scanner/data/curated/chess-v2-v3/valid/IMG_20220809_233059_jpg.rf.2617972ceb9a9567022491f3761072bb.png"
.venv-scanner/bin/python -m scanner.ml predict "$PHOTO" \
  --checkpoint scanner/artifacts/chess-v2-baseline/best.pt \
  --threshold 0.25 --output scanner/artifacts/chess-v2-baseline/my-photo
```

Use an actual image path in place of `"$PHOTO"` for your own photo. `predict` writes
boxes, type/color labels, and confidence values, not a playable game position.
The CLI's default checkpoint still refers to the original Top Down benchmark;
pass the new checkpoint explicitly as above. No cloud account, paid GPU, Firebase
credential, or external configuration is needed to use this local model.

Dataset attribution: [Chess V2 by Public Wspace](https://universe.roboflow.com/public-wspace/chess-v2-qqtmk),
Roboflow Universe, CC BY 4.0. Preserve dataset and upstream TorchVision/COCO
attribution and applicable licenses if publishing model downloads.
