# Board Scanner Workspace

The scanner is research tooling plus an experimental local `/scanner` workflow.
Open **Scanner** from the shared Chass navigation. Its Rulebook section explains
photo preparation, manual review, privacy, and current limitations. The page shows
recognition availability; uploads and crop/rotation work without the service,
while recognition requires `./scanner/run-local.sh`. Game import is still disabled.
Visiting Scanner preserves an existing Customizer draft. Leaving Scanner with a
photo loaded asks for confirmation because photos and corrections are not saved.
No ML packages or datasets are deployed with the FastAPI game server.
See [Improvements And Local Testing](ml/IMPROVEMENTS.md) for the trained two-stage
pipeline, accuracy comparison and `./scanner/run-local.sh` startup instructions.

```text
scanner/
  ml/                          Pipeline code, pinned dependencies, tests, policies, documentation
  data/
    raw/
      ChessTopDown.v2-chess2.coco/  Original small baseline dataset (historically tracked)
      ChessV2.v1i.coco/            Original larger download (not tracked)
    curated/
      chess-v2-v3/              Active, alignment-reviewed COCO export
      chess-v2-v2/              Superseded audit snapshot; not for training
  artifacts/
    baseline/                  Original trained model, unchanged
    prepared/                  Original baseline manifest
    validation/ and test/      Original baseline evaluation
    chess-v2/                  Raw intake audit
    curation/chess-v2-v3/      Active audit, lineage, corrections, exclusions, visual review
    chess-v2-baseline/          New training run on the v3 dataset
    crop-classifier-v1/         Trained ResNet18 classifier and training history
    crops/chess-v2-v3-160/      Original-resolution piece crop cache
    improvements/experiment-v1/ Frozen comparison, model selection and predictions
    curation/chess-v2-v4/       Annotation-only overlay; two missing test pieces
```

New raw data, curated copies, and artifacts are ignored by Git. The small Top Down
source was already tracked before this layout change; it remains available for
reproducing the original benchmark. Do not force-add the larger downloads or model
weights to Git. Back up raw downloads and local artifacts separately to retain that exact run.

## Commands

Run from the repository root using the isolated ML environment:

```sh
# Rebuild the original manifest after moving its data directory.
.venv-scanner/bin/python -m scanner.ml prepare --dataset top-down

# Build the reviewed active copy once. Existing versions cannot be overwritten.
.venv-scanner/bin/python -m scanner.ml curate

# Read-only comparison of the original and curated sources.
.venv-scanner/bin/python -m scanner.ml compare

# Tests; no hosted service or API key is needed.
.venv-scanner/bin/python -m pytest scanner/ml/tests
```

See [ML Instructions](ml/README.md), [Alignment Review](ml/CHESS_V2_ALIGNMENT.md),
the new [Chess V2 Model Card](ml/CHESS_V2_MODEL_CARD.md), and the original
[Model Card](ml/MODEL_CARD.md). The [Accuracy Tracker](ml/ACCURACY_TRACKER.md)
records dated metrics and chart-ready snapshots without confusing bounding-box
results with square accuracy. Local website recognition is connected through a
separate API on port 8001; game import and public inference hosting are not enabled.
To inspect uncertain examples:

```sh
open scanner/artifacts/curation/chess-v2-v3/index.html
```

Do not train using the raw Chess V2 export or edit it in place. The curated manifest
records new grouped splits, so scores on this dataset must not be represented as
directly comparable to the original Top Down test score. User-supplied photos
should remain local unless the user explicitly chooses to share them.
