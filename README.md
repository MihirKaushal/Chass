# Chass!

Chass! is a full-stack browser chess platform for classic games and configurable chess
variants. It supports local two-player games, private link-or-code multiplayer, custom
boards and pieces, modular rules, and real-time synchronization.

**Live site:** [https://playchass.vercel.app](https://playchass.vercel.app)

## Features

- Classic chess movement, captures, turns, check, checkmate, and stalemate
- Auto-routed Stockfish and Fairy-Stockfish Match Analysis for compatible static games
- Local hot-seat and private online multiplayer
- Two-player restart approval for local and online matches
- Chass Gambit with maximum-budget hidden deployment, center affinity, and command powers
- Maharani, Catapult, Barricade, Hypnotizer, Diplomat, Cannibal, and Elephant custom pieces
- Seven optional player abilities, including persistent Scorch terrain, with private pre-game selection
- Checkmate, King Capture, Timed, Point Race, Elimination, and Royal Score victories
- Shareable, one-use game invitation links and invite codes
- Live WebSocket updates, reconnect, presence, and state recovery
- Board dimensions from 4x4 through 16x16 and editable starting layouts
- Configurable piece metadata, nonnegative point values, and composition limits
- Toggleable rules, score-target games, and custom rule presets
- Public effect countdowns, detailed piece tooltips, and an in-app Rulebook
- Legal moves, captured pieces, history, scores, clocks, and contextual endgame dialogs
- Manual or automatic board flipping
- Automatic cleanup after 24 hours without game activity
- Responsive React interface for desktop and mobile

## Tech Stack

| Area | Tools |
| --- | --- |
| Languages | Python, JavaScript/JSX, CSS, SQL, Bash |
| Frontend | React 18, React Hooks, Vite 5, native WebSocket API |
| Backend | FastAPI, Uvicorn, Pydantic 2 |
| Analysis | Stockfish 18, Fairy-Stockfish, UCI, NNUE, W/D/L statistics, parity validation |
| Database | Cloud Firestore, Firebase Admin SDK, SQLAlchemy 2, SQLite |
| Testing and quality | Pytest, HTTPX, Ruff, Vite production builds |
| Hosting | Vercel, Render, Firebase |

### Main Packages

- **React:** Component-based frontend and application state management.
- **Vite:** Frontend development server and production bundler.
- **FastAPI:** REST API, WebSocket endpoints, CORS, and generated OpenAPI documentation.
- **Pydantic:** Request validation, domain models, and JSON serialization.
- **Firebase Admin:** Secure server-side Firestore access and transactions.
- **SQLAlchemy:** Local SQLite persistence and an optional SQL fallback.
- **Uvicorn:** ASGI server for FastAPI HTTP and WebSocket traffic.
- **Stockfish and Fairy-Stockfish:** Local UCI engines for auto-routed position analysis;
  no hosted API or paid key.
- **Pytest and HTTPX:** Backend API and multiplayer integration testing.
- **Ruff:** Python linting and code-quality checks.

## Architecture

```text
React + Vite
  |-- REST API
  |-- WebSockets
  v
FastAPI
  |-- Game service
  |-- Modular rule engine
  |-- Async analysis router --> Stockfish 18 / Fairy-Stockfish
  v
Repository adapters
  |-- SQLAlchemy / SQLite locally
  `-- Firebase Admin / Firestore in production
```

Game rules are handled by a separate rule engine rather than API routes or database code.
The backend validates moves and remains authoritative during online games. Versioned
database updates prevent stale moves from one browser from overwriting newer game state.
The configuration API stores victory, formation, piece, ability, and Gambit settings as one
versioned contract. A declarative compatibility validator rejects impossible combinations
before game creation, while custom actions and passive effects remain separate rule modules.
Gambit deployments use seat-specific views and revisions so an opponent receives no piece,
count, edit, or timing data before the atomic reveal.
Game activity uses a renewable expiration lease, and both repository adapters cascade
inactive-game cleanup to player seats, invitation records, and move audits.

The Match Analysis system prefers Stockfish 18 for compatible standard-rule 8x8 positions and
routes validated static variants up to 10x12 to Fairy-Stockfish. Fairy profiles are generated
deterministically from typed Chass settings; raw engine syntax is rejected. Before enabling a
Fairy profile, the backend compares its legal moves and terminal outcome with the Chass Rule
Engine. Stateful pieces, abilities, terrain, Affinity, and Gambit setup remain intentionally
unsupported. Analysis runs after the move response, is cached by engine and position, and is
version-checked before a WebSocket result can update the UI.

## Project Structure

```text
backend/
  analysis/        Engine profiles, parity checks, FEN, factors, and asynchronous UCI service
  models/          Domain models and API schemas
  repositories/    Firestore and SQL persistence adapters
  routes/          REST and WebSocket endpoints
  rules/           Movement and game rules
  services/        Game and session workflows
  tests/           Backend integration tests
  main.py           FastAPI application

frontend/
  public/           Static assets
  src/
    api/            Backend communication
    components/     Board, lobby, history, and customization UI
    hooks/          WebSocket connection management
    pages/          Home, play, join, and customize pages
    styles/         Responsive CSS

render.yaml         Render backend configuration
run.sh              Local startup script
```

## Run Locally

Requirements:

- Python 3.11+
- Node.js 20+
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
npm run build
```

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Service health check |
| `GET` | `/game/catalog` | Load pieces, abilities, victories, and presets |
| `POST` | `/game/validate` | Validate a complete configuration and return incompatible options |
| `POST` | `/game/create` | Create a local or online game |
| `POST` | `/game/join` | Join through an invitation |
| `GET` | `/game/{id}` | Load game state |
| `GET` | `/game/{id}/history` | Load an earlier page of move history |
| `GET` | `/game/{id}/analysis` | Load or schedule the current compatible position estimate |
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

See [Firebase Setup](docs/FIREBASE_SETUP.md) for the exact credential, migration, Render,
security-rule, rollback, and verification steps.
See [Match Analysis](docs/MATCH_ANALYSIS.md) for eligibility, architecture, tuning,
deployment, and troubleshooting details.

After Vercel deploys, set both Render values to the production frontend URL:

```text
FRONTEND_URL=https://playchass.vercel.app
ALLOWED_ORIGINS=https://playchass.vercel.app
```

Render services may sleep when idle, but Firestore does not require manual unpausing.
