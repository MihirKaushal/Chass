# Low-Memory Public Recognition

The public serving target is a separate **free Render Docker service** named
`chass-scanner`. The game API and its Firebase configuration stay separate.

## Runtime

- Uses ONNX Runtime CPU, not PyTorch, on the model server. Training remains PyTorch.
- Published float32 graphs are in `scanner/models/onnx/`; checksums and source-model
  fingerprints are verified at startup. No quantization or retraining was applied.
- One worker, one scan at a time, one classifier crop at a time, bounded image sizes.
- `/ready` exposes only readiness for Render. `/health` and `/scan` require the
  shared `SCANNER_SERVICE_TOKEN`. Render generates it in `chass-scanner-auth`;
  it must be linked to both services, never to Vercel or browser variables.
- The existing game API proxies images. Set its `SCANNER_SERVICE_URL` only after
  verifying the new service's actual public HTTPS URL in Render.

`render.yaml` defines the free service and secret group. The service uses
`scanner/deploy/Dockerfile.onnx`. Do not upgrade either service's compute plan.
Both free services share the workspace's included hours; cold starts and quota
limits still apply. See https://render.com/docs/free.

## Reproduce The Export

Install `onnx==1.23.2` and `onnxruntime==1.31.1` into the existing training environment.
The exporter needs the validated original checkpoints already used by local recognition.

```sh
.venv-scanner/bin/python -m scanner.ml.export_onnx --output scanner/artifacts/new-onnx
.venv-scanner/bin/python -m scanner.ml.verify_onnx --models scanner/artifacts/new-onnx --limit 40
```

The exporter refuses existing destinations and verifies numerical graph parity.
After validation, replace the three deployment files (`detector.onnx`,
`classifier.onnx`, `manifest.json`) together, then commit and deploy. Keep the model
attribution README. Do not upload raw photos, datasets, environment files or credentials.

## Verification Before Deployment

- 40 frozen validation images: identical board assignments, review flags, final
  labels, and top-three alternative labels versus the selected Torch pipeline.
- Maximum observed score difference: `0.00001085`; box difference: `0.000489` pixels.
- Dense 3000x3000 photo through the actual resizing/API path: HTTP 200, no Torch
  imported, approximately 357 MiB peak RSS on macOS. This is not a Linux memory guarantee.
- Linux CPython 3.13 ONNX Runtime wheel availability checked for `manylinux_2_28_x86_64`.
- No model accuracy claim is added: export parity is not an accuracy benchmark.

Public deployment health and end-to-end recognition must still be checked after
Render builds the Linux container. If it cannot fit the free plan, stop and investigate;
do not silently move to paid compute or put the model into the game server.
