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

The Render service URL is `https://chass-scanner.onrender.com`; the browser continues
to use `https://chass-api.onrender.com/scanner`, not the private service token.
Render builds the Linux container from the repository. Recheck readiness and a real
recognition request after every model/runtime update. If it cannot fit the free
plan, stop and investigate; do not silently move to paid compute or put the model
into the game server. Production accepts prepared crops up to 2048 x 2048 pixels
to bound decoding memory; the website's crop editor already emits images within
that limit.

## Public Deployment Check (2026-10-28)

- Website: `https://playchass.vercel.app/scanner`, showing Recognition Connected.
- Public game gateway health: ready, configured, experimental; images not stored.
- A real dataset photo sent through the public gateway returned HTTP 200 in
  6.48 seconds, with 64 squares, 28 piece proposals, and review alternatives.
  This is one warm-service request, not a latency or accuracy benchmark.
- The model service's unauthenticated `/health` and `/scan` requests returned 401.
  Only `/ready` exposes minimal public health information.
- A reviewed-position validation request returned a valid active position.
  No persistent public test game was created.
- Automated checks: 329 backend tests passed (one emulator-dependent test skipped),
  137 scanner tests passed, and 197 frontend tests passed; production frontend built.
- Initial browser readiness allows 150 seconds because the game API and model
  service may wake sequentially. Free-service cold starts can still require retrying.

Recognition remains experimental. Users must review the board before importing it;
the public runtime does not improve the trained model's recognition accuracy.
