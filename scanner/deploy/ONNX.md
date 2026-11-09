# Low-Memory Public Recognition

The public serving target is a separate **free Render Docker service** named
`chass-scanner`. The game API and its Firebase configuration stay separate.

## Runtime

- Uses ONNX Runtime CPU, not PyTorch, on the model server. Training remains PyTorch.
- Published float32 graphs are in `scanner/models/onnx/`; checksums and source-model
  fingerprints are verified at startup. Both models now use Chess V2 + Top Down;
  quantization and batching candidates were measured but not enabled.
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
.venv-scanner/bin/python -m scanner.ml.verify_onnx \
  --manifest scanner/artifacts/merged-2026-11-08/merged/manifest.json \
  --models scanner/artifacts/new-onnx --per-source --limit 20
```

The exporter refuses existing destinations and verifies numerical graph parity.
After validation, replace the three deployment files (`detector.onnx`,
`classifier.onnx`, `manifest.json`) together, then commit and deploy. Keep the model
attribution README. Do not upload raw photos, datasets, environment files or credentials.

## Initial Export Verification (Historical)

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

## Speed And Recognition Update (2026-11-06)

- The frontend wakes `/ready` on the scanner alongside the game API health request.
  `/ready` allows cross-origin GET without credentials and exposes readiness only.
  Authentication and origin checks on `/health` and `/scan` are unchanged.
- The normal server path stays single-thread, static FP32, batch 1. Crop-before-RGB
  conversion avoids repeated full-photo copies. Responses include `timings` for
  preparation, detector, crop, classifier, square mapping and proposal count.
- King-focused classifier and validation-selected threshold 0.20 improve the
  existing test benchmark; see `../ml/benchmarks/optimization-2026-11-06/README.md`.
- **Recognition Options** offers an opt-in on-device prototype. Models (~52 MiB)
  and runtime (~28 MiB) are downloaded only when requested. Model downloads are
  hash-verified and cached; old model versions are removed from that cache.
  Inference uses a worker. Unsupported/failed/timed-out inference falls back to the
  normal API with an explicit notice. Cancelling never starts a fallback upload.
- Frontend `predev`/`prebuild` stages the already-public weights plus the matching
  ONNX Web runtime. If Vercel receives only `frontend/`, the build downloads from
  an immutable public Git revision. No private tokens or raw photos are embedded.
- No new paid service, Firebase change, periodic keepalive, or environment variable
  is required for the existing public domains. Other deployments may set public
  `VITE_SCANNER_WAKE_URL=https://their-model-host/ready` (never a token).
- Locally, `./run.sh` / `./scanner/run-local.sh` prefer the published ONNX weights
  when `.venv-scanner` contains ONNX Runtime. An explicit `SCANNER_RUNTIME=torch`
  still allows research checkpoints. The default Torch paths now match the current
  merged serving release; explicit selection/checkpoint variables override them.

For a new classifier export, set `SCANNER_SELECTION` to the candidate's
`deployment-selection.json` and `SCANNER_CLASSIFIER` to its `best.pt` before running
the exporter and parity checker. The dated report explains the 0.005 classifier
confidence tolerance used for the November 6 export; exact labels and reviews must
still match. Keep previous deployment weights accessible for rollback.

Live verification after this update: model fingerprints matched, real public scans
returned 64 squares, and protected endpoints still rejected unauthenticated requests.
The three-request median was 10.364 -> 10.935 seconds, **not a server-speed win**;
new recall settings processed 62 rather than 59 proposals. See the dated benchmark
for every sample, the retained outlier, memory checks, and the browser QA limitation.

## Combined-Data Promotion (2026-11-09)

- The current graphs are the November 8 mixed-source candidate, threshold 0.15,
  overlap 0.40. Detector and classifier were both fine-tuned on the merged data.
- Forty validation photos (20 per source) passed exact board/review and top-three
  label parity against PyTorch. Maximum score difference 0.00000650; box-coordinate
  difference 0.00024414 pixels. No tolerance was relaxed for this export.
- Same-photo local CPU timing: median 139.8 ms, p95 222.3 ms, peak process memory
  442.6 MiB. This is not hosted or browser latency; free-host cold starts still apply.
- Public metrics are tied to the locked [experiment report](../ml/benchmarks/merged-data-2026-11-08/README.md).
  The prior model remains in Git commit `b8fb05c` for rollback.
- Promote all three files together and update the immutable revision in
  `frontend/scripts/scanner-assets.mjs`. Browser caches are keyed by model hashes,
  and the manifest is revalidated so existing visitors receive the new release.
- No new environment variables, Firebase changes, paid services, or model APIs
  are required. Push to the connected branch to trigger Vercel and the existing
  Render scanner service; verify a real `/scanner/scan` response's model hashes.

## Cold-Start Recovery (2026-11-06)

A live health check initially returned `ready: false`, then recovered after the
model service woke up. A one-shot browser check left the page incorrectly stuck
offline even though the service was available.

- The browser now retries readiness every three seconds within a 150-second
  total budget, cancelling any individual probe after 45 seconds.
- Temporary HTML/loading responses, network errors, and not-ready results show
  Starting Scanner while retrying. Configuration/authentication failures stop
  without exposing upstream details or credentials.
- Readiness is checked again before scanning, in case the photo editor was left
  open long enough for the model to sleep. Photo POSTs are never auto-retried.
- Retries stop on success, timeout, or navigation; there is no permanent keep-alive.
- Regression tests cover cold starts, request cancellation, retry deadlines,
  permanent failures, and the simplified scanner controls.
