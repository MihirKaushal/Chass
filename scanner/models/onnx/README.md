# Chass Scanner Serving Models

Float32 ONNX exports of the validation-selected SSDLite detector and ResNet18
piece-crop classifier. These are the same trained weights, not a newly trained or
quantized model. SHA-256 checksums, class order, and preprocessing settings are in
`manifest.json`. Public sharing of these deployment weights was approved by the
project owner. Raw photos, datasets, credentials, and environment files are not included.

Training data attribution: **Chess V2 by Public Wspace**, Roboflow Universe,
licensed **CC BY 4.0**. Source:
https://universe.roboflow.com/public-wspace/chess-v2-qqtmk
License: https://creativecommons.org/licenses/by/4.0/

The data was reviewed, deduplicated, relabeled, and split by capture group before
training. Models were fine-tuned using TorchVision pretrained backbones. See
`scanner/ml/IMPROVEMENTS.md` and `scanner/ml/CHESS_V2_MODEL_CARD.md` for provenance,
measured results, limitations, and the original training/export procedures.

Recognition is experimental. Users must verify all 64 squares. Export parity is
not a claim of perfect recognition or proven accuracy on unseen physical boards.
