# Verification And Diagnostics

## Application Checks

From the repository root, use Python matching `.python-version` and Node 22.12+:

```sh
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements-dev.txt
.venv/bin/ruff check backend scripts
.venv/bin/python scripts/export_rulebook.py --check
.venv/bin/pytest
cd frontend
npm ci
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

Playwright starts isolated services on ports 14173, 18100, and 18101. It uses temporary
SQLite and a deterministic recognition fixture, not your `.env` database or camera.
Chromium's fake-camera device tests capture and track cleanup. Review
`npm run test:e2e:report` for desktop/narrow screenshots and traces from failures.
Tests assert overflow, shared navigation/footer placement, and the desktop home footer's
visibility. Screenshot artifacts are not yet an approved cross-platform pixel-diff baseline.
The interactive browser connection is not required for these automated tests.

## Firestore Emulator

Install Java 21+ and Node 22. Run only with a demo project and loopback emulator:

```sh
FIREBASE_PROJECT_ID=demo-chass-ci FIRESTORE_EMULATOR_HOST=127.0.0.1:18080 \
  npx --yes firebase-tools@15.35.0 emulators:exec --only firestore \
  --project demo-chass-ci --config .ci/firebase.json \
  '.venv/bin/pytest backend/tests/test_firestore_emulator.py -q'
```

No Firebase login, service-account key, or billable database is used. The test deliberately
rejects non-demo project IDs and non-loopback hosts. It checks persistence, stale-write
rejection, a history page, and expiry cleanup of games, players, invites, and move records.
The regular suite skips this test when the emulator is absent; CI runs it in its own job.

## Engines And Scanner

```sh
bash scripts/install_stockfish.sh
bash scripts/install_fairy_stockfish.sh
.venv/bin/python scripts/engine_smoke.py
.venv/bin/python scripts/benchmark_chass.py --repeats 3 --budget-ms 180 \
  --output /tmp/chass-native-benchmark.json
```

The smoke test launches real binaries. Benchmark JSON reports full evaluation latency,
completed depth, nodes, and search-budget exhaustion; exhaustion is a fallback event,
not an HTTP timeout. Engine action preparation is outside the search budget. Compare
reports on the same hardware, workload, and load; these reports do not establish Elo.

For the real-weight scanner contract, use a separate ONNX environment:

```sh
python3 -m venv .venv-scanner-verify
.venv-scanner-verify/bin/pip install -r backend/requirements.txt \
  -r scanner/deploy/requirements-onnx.txt
.venv-scanner-verify/bin/python scripts/scanner_contract_smoke.py
```

This checks committed model hashes, ONNX inference, the real scanner HTTP wrapper, and the
Pydantic response schema using a generated test image. It does not score accuracy.
For actual model evaluation, use [the scanner quality workflow](../scanner/QUALITY.md).
Never install training dependencies into the production game backend.

## Private Diagnostics

`GET /health` returns only `{"status":"ok"}`. It is a liveness probe, not proof that engines
or Firestore are working. Detailed information moved to `GET /internal/diagnostics`.

Set `DIAGNOSTICS_TOKEN` to a separate random secret of at least 32 characters on the backend.
`render.yaml` generates it for Blueprint-managed deployments; sync an existing Blueprint or
add it in Render's Environment settings. Leaving it unset disables the endpoint with 404.
Wrong/missing credentials return 401. Successful responses are marked `Cache-Control: no-store`.
Never expose the token through a frontend `VITE_` variable or commit it.

```sh
# Set API_URL and DIAGNOSTICS_TOKEN privately in your shell first.
curl --fail -H "Authorization: Bearer $DIAGNOSTICS_TOKEN" \
  "$API_URL/internal/diagnostics"
```

Metrics include scanner/import HTTP outcomes and latency, analysis task outcomes and latency,
and `engine_fallback.chass` for Fairy parity fallback. Analysis latency includes debounce,
queueing, factor extraction, engine work, and publishing. Import schema rejections count as
errors. No IDs, uploaded content, credentials, or unbounded labels are recorded. Aggregates
reset per process restart; they are not durable, cross-worker, percentile, or browser metrics.

## Local Verification Record

Audit completed November 8, 2026. The commands are repeatable; counts can change as tests grow.

| Check | Result |
| --- | --- |
| Backend API/rule/property suite | 389 passed; emulator case skipped here and passed separately |
| Scanner ML/preparation suite | 157 passed |
| Frontend unit/presentation suite | 225 passed |
| Chromium workflows | 18 passed across desktop and narrow projects |
| Firestore emulator lifecycle | Passed, including conflict/history/cleanup |
| Real engines | Stockfish 18 and Fairy-Stockfish 250826 LB passed; 24 legal moves plus checkmate/stalemate matched on 10x10 fixtures |
| Scanner contract | Real ONNX wrapper passed; three local dataset-image outputs also validated |
| Frontend production build | Passed on Vite 7.3.7 |
| Dependency audit | No npm advisories reported after the toolchain update |

The GitHub Actions workflow is configured but still needs its first pushed remote run.
These local results do not verify Render cold-start latency, camera hardware on every browser,
all possible custom variants, or production Firestore quotas/credentials. After deployment,
check one scanner import, two-browser move/reconnect flow, and each engine selection on the
public site. Do not treat `/health` alone as an end-to-end deployment check.

## Tool References

- [Playwright managed web servers](https://playwright.dev/docs/test-webserver)
- [Playwright CI and reports](https://playwright.dev/docs/ci)
- [Playwright screenshot baseline considerations](https://playwright.dev/docs/test-snapshots)
- [Firestore emulator connections](https://firebase.google.com/docs/emulator-suite/connect_firestore)
- [Firebase emulator prerequisites](https://firebase.google.com/docs/emulator-suite/install_and_configure)
- [Vite 7 Node requirements](https://v7.vite.dev/guide/)
