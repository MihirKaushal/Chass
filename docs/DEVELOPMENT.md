# Development & Operations

[Back to the project overview](../README.md)

Commands below run from the repository root unless noted otherwise.

## Run Locally

Requirements:

- Python 3.11+
- Node.js 22.12+ (recommended) or 20.19+
- npm
- `curl`, `tar`, `make`, and a C++ compiler for the one-time engine installation

Start the frontend and backend together:

```bash
./run.sh
```

Local addresses:

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- API documentation: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

Local development uses SQLite and does not require Firebase. Press `Ctrl+C` to stop both
services. The first run installs checksum-verified Stockfish 18 and Fairy-Stockfish engines
into the ignored `.stockfish/` directory; later starts reuse them.

## Test and Build

```bash
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
pytest
ruff check backend

cd frontend
npm ci
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

The Rulebook and Game Customizer render from a bundled reference catalog, without
waiting for the game server. Customizer edits stay available during a server cold
start; launching a game still requires live backend validation. After changing
piece, ability, rule, or preset definitions, regenerate the catalog from the
repository root with `.venv/bin/python scripts/export_rulebook.py` and commit the
updated JSON. Backend tests and `scripts/export_rulebook.py --check` detect drift.

GitHub Actions additionally runs an isolated Firestore emulator lifecycle test, launches the
real Stockfish/Fairy binaries, verifies the ONNX scanner response contract, and uploads
browser screenshots/traces and a native-engine benchmark. No production credentials are needed.
Browser recognition uses a deterministic fixture; that suite does not measure ML accuracy.

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Minimal public liveness check |
| `GET` | `/internal/diagnostics` | Server-only bearer-authenticated engine status and aggregate metrics |
| `GET` | `/game/catalog` | Load pieces, abilities, victories, and presets |
| `POST` | `/game/validate` | Validate a complete configuration and return incompatible options |
| `POST` | `/game/create` | Create a local, online, or engine-routed bot game |
| `POST` | `/game/join` | Join through an invitation |
| `GET` | `/game/{id}` | Load game state |
| `GET` | `/game/{id}/history` | Load an earlier page of move history |
| `GET` | `/game/{id}/analysis` | Load or schedule the current position estimate |
| `POST` | `/game/{id}/move` | Submit a move |
| `POST` | `/game/{id}/action` | Use a custom piece or special-ability action |
| `POST` | `/game/{id}/ability` | Lock a private player ability |
| `POST` | `/game/{id}/setup/handoff` | Continue a local private ability handoff |
| `POST` | `/game/{id}/gambit/deployment` | Place, remove, clear, or undo a hidden army edit |
| `POST` | `/game/{id}/gambit/ready` | Lock a private deployment and reveal when both are legal |
| `POST` | `/game/{id}/gambit/handoff` | Continue a local privacy handoff |
| `POST` | `/game/{id}/gambit/power` | Use Reinforce, Evolve, or Stronghold |
| `POST` | `/game/{id}/rules` | Update game rules |
| `POST` | `/game/{id}/pieces` | Customize pieces |
| `POST` | `/game/{id}/layout` | Update the board layout |
| `POST` | `/game/{id}/rematch` | Request, approve, decline, or cancel a restart |
| `POST` | `/game/{id}/invite` | Replace an unused invitation |
| `WS` | `/game/ws/{id}` | Receive live game updates |

## Environment Variables

Use `.env.example` as the local template.

| Variable | Purpose |
| --- | --- |
| `PERSISTENCE_BACKEND` | Selects `sql` locally or `firestore` in production |
| `DATABASE_URL` | Local SQLite or optional SQL fallback connection string |
| `FIREBASE_PROJECT_ID` | Firebase project used by the backend |
| `FIREBASE_CREDENTIALS_BASE64` | Base64-encoded server service-account JSON |
| `FRONTEND_URL` | Frontend address used for invite links |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins |
| `ENVIRONMENT` | `development` or `production` |
| `TOKEN_SECRET` | Private session-token hashing secret |
| `INVITE_TTL_HOURS` | Invitation expiration time |
| `GAME_IDLE_TTL_HOURS` | Hours after the last game change before deletion |
| `GAME_CLEANUP_INTERVAL_MINUTES` | Cleanup frequency while FastAPI is awake |
| `MATCH_PREDICTOR_ENGINE_ENABLED` | Enables or disables server-side engine analysis |
| `STOCKFISH_PATH` | Optional path to a Stockfish executable |
| `STOCKFISH_MOVETIME_MS` | Engine search time per position; default `180` |
| `STOCKFISH_HASH_MB` | Memory assigned to the engine hash; default `32` |
| `STOCKFISH_THREADS` | Engine worker threads; default `1` |
| `STOCKFISH_STARTUP_TIMEOUT_SECONDS` | Seconds allowed for each cold-start attempt; default `15` |
| `STOCKFISH_STARTUP_ATTEMPTS` | Engine startup attempts before reporting unavailable; default `2` |
| `FAIRY_STOCKFISH_PATH` | Optional path to a largeboard Fairy-Stockfish executable |
| `FAIRY_STOCKFISH_MOVETIME_MS` | Fairy search time per position; default `180` |
| `FAIRY_STOCKFISH_HASH_MB` | Memory assigned to the Fairy hash; default `16` |
| `FAIRY_STOCKFISH_THREADS` | Fairy worker threads; default `1` |
| `FAIRY_STOCKFISH_MAX_PROFILES` | Generated profiles retained by one engine process; default `256` |
| `CHASS_ENGINE_MOVETIME_MS` | Native Chass search budget per position; default `180` |
| `TRUSTED_PROXY_HOPS` | Proxies that append to `X-Forwarded-For`; rate limits read the client address that many entries from the right. Default `0` uses the socket peer |
| `VITE_API_URL` | Public backend address used by React |

Do not commit `.env`, database passwords, or production secrets.

## Deployment

The repository includes configuration for a free personal-project deployment:

- **Frontend:** Import the repository into Vercel, set the Root Directory to `frontend`,
  and set `VITE_API_URL` to the Render backend URL.
- **Backend:** Create a Render Blueprint from `render.yaml`, add the Firebase server
  credentials, and set `PERSISTENCE_BACKEND=firestore`. The Blueprint installs the pinned
  Stockfish and Fairy-Stockfish engines during the build.
- **Database:** Create a free Firebase project and its default Cloud Firestore database.

See [Firebase Setup](FIREBASE_SETUP.md) for the exact credential, migration, Render,
security-rule, rollback, and verification steps.
See [Match Analysis](MATCH_ANALYSIS.md) for eligibility, architecture, tuning,
deployment, and troubleshooting details.
See [Chess Bots](BOTS.md) for engine compatibility, difficulty profiles, safety
boundaries, and future extension points.

After Vercel deploys, set both Render values to the production frontend URL:

```text
FRONTEND_URL=https://playchass.vercel.app
ALLOWED_ORIGINS=https://playchass.vercel.app
```

Render services may sleep when idle, but Firestore does not require manual unpausing.
