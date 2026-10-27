# Scanner MVP Verification

Date: 2026-10-27. These are integration checks, not new model-accuracy measurements.

## Automated Checks

| Suite | Result |
| --- | --- |
| Backend (`.venv/bin/python -m pytest backend/tests -o addopts='' -q`) | 329 passed, 1 skipped |
| Frontend (`npm test --prefix frontend`) | 197 passed |
| Scanner (`.venv-scanner/bin/python -m pytest scanner/ml/tests -o addopts='' -q`) | 132 passed |
| Production frontend (`npm run build --prefix frontend`) | Passed |
| Ruff checks on changed Python files; `bash -n run.sh`; `git diff --check` | Passed |

The skipped backend test requires a Firestore emulator, which was not running.
The scanner suite reports a third-party Starlette/httpx TestClient deprecation warning.

Coverage includes side-to-move validation, legal in-check imports, impossible and
finished positions, opt-in castling, en passant for both colors and expiry,
halfmove/fullmove counters, persistence round-trips, restart restoration, online
seat authorization, gateway failures, image limits, private service authentication,
ranked review alternatives, malformed responses, and launch confirmation guards.

## Smoke Checks

- Real model recognition through the local game-API gateway, followed by scripted
  correction to a known sample position, local import, and a legal move.
- The same corrected position imported online, joined through its invite, and played
  using the existing authorized game API. All smoke games used an isolated SQLite
  test database, not the public Firestore database.
- Exported `scanner/artifacts/deployment-mvp/` loaded its selected model weights and
  performed authenticated CPU inference from its own directory. No training data
  or environment files are required by the bundle.
- Scanner landing page inspected in Chrome: recognition connected, shared navigation,
  initial photo-only layout, and no captured browser errors.

## Not Yet Verified

- Browser automation could not upload a file because the browser extension lacked
  file-URL access. Interactive upload-to-game browser QA still needs a manual pass;
  API smoke checks and rendered component tests do not replace that pass.
- Docker was not installed. The Linux container, chosen host's package availability,
  memory limits, cold starts, and public Vercel/Render deployment need verification.
- Camera hardware was not exercised during this pass. Camera lifecycle tests passed.
- Recognition accuracy is unchanged. Missed pieces and wrong square assignments
  remain possible; confirmation of all 64 squares is required. See the existing
  accuracy tracker rather than interpreting these passing tests as detection accuracy.
