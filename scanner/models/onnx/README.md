# Chass Scanner Serving Models

Release: **merged-data-2026-11-08**, promoted November 9, 2026.
Float32 ONNX exports of SSDLite and ResNet18, both fine-tuned on curated
**Chess V2 + Chess Top Down**. The training sampler uses a 75/25 source mixture
with class-balanced classifier crops. Detection threshold **0.15** and duplicate
overlap **0.40** were selected on validation before test evaluation.

`manifest.json` records SHA-256 checksums, training fingerprint, class order,
preprocessing and checkpoint provenance. Server and browser use the same graphs.
Raw photos, datasets, credentials and environment files are not included.

## Data Credits

- [Chess V2 by Public Wspace](https://universe.roboflow.com/public-wspace/chess-v2-qqtmk), Roboflow Universe, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- [Chess Top Down by chess](https://universe.roboflow.com/chess-gftva/chess-top-down), Roboflow Universe, [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

Chass curated labels/orientation, deduplicated and grouped related images, and
excluded one added validation image related to test. Original photos and split
assignments were preserved. Models use TorchVision pretrained backbones.

## Results And Limits

Across 355 regression photos / 6,376 annotated pieces, 5,721 pieces were correctly
located and classified by type and color (**89.73%**). Source-specific recall:
**89.78% Chess V2**, **86.02% Top Down**. Equal-source mean typed F1: **89.58%**.
The added-source gain is substantial; pooled recall ties the equal-budget V2-only
control within one piece. These are reused box-level benchmarks, not fresh
unseen-set, empty-square or whole-board accuracy. Top Down test has only 17 photos.
Always review all 64 squares, including empty ones.

Protocol, model hashes, class metrics, graphs, ONNX parity and local runtime:
`scanner/ml/benchmarks/merged-data-2026-11-08/`. Forty validation images retained
identical board/review decisions and top-three labels in Torch-to-ONNX verification.

## Rollback

The previous three deployment files and model card remain in Git commit
`b8fb05c`. Restore them together and update the frontend's immutable model revision
when rolling back; never mix a manifest with another release's weights.
