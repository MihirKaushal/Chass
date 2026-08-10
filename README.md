# Chass!

Chass! is a full-stack browser chess platform for classic games and configurable chess
variants. It supports local two-player games, private invite-link multiplayer, custom
boards and pieces, modular rules, and real-time synchronization.

**Live site:** [https://chass-rho.vercel.app](https://chass-rho.vercel.app)

## Features

- Classic chess movement, captures, turns, check, checkmate, and stalemate
- Local hot-seat and private online multiplayer
- Chass Gambit: private 39-point army deployment, center affinity, and command powers
- Shareable, one-use game invitation links
- Live WebSocket updates, reconnect, presence, and state recovery
- Variable board dimensions and editable starting layouts
- Configurable piece movement, metadata, and point values
- Toggleable rules, score-target games, and custom rule presets
- Legal-move highlighting, captured pieces, history, scores, and endgame dialogs
- Manual or automatic board flipping
- Automatic cleanup after 24 hours without game activity
- Responsive React interface for desktop and mobile

## Tech Stack

| Area | Tools |
| --- | --- |
| Languages | Python, JavaScript/JSX, CSS, SQL, Bash |
| Frontend | React 18, React Hooks, Vite 5, native WebSocket API |
| Backend | FastAPI, Uvicorn, Pydantic 2 |
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
  v
Repository adapters
  |-- SQLAlchemy / SQLite locally
  `-- Firebase Admin / Firestore in production
```

Game rules are handled by a separate rule engine rather than API routes or database code.
The backend validates moves and remains authoritative during online games. Versioned
database updates prevent stale moves from one browser from overwriting newer game state.
Gambit deployments use seat-specific views and revisions so an opponent receives no piece,
count, edit, or timing data before the atomic reveal.
Game activity uses a renewable expiration lease, and both repository adapters cascade
inactive-game cleanup to player seats, invitation records, and move audits.

## Project Structure

```text
backend/
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
services.

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
| `POST` | `/game/create` | Create a local or online game |
| `POST` | `/game/join` | Join through an invitation |
| `GET` | `/game/{id}` | Load game state |
| `POST` | `/game/{id}/move` | Submit a move |
| `POST` | `/game/{id}/gambit/deployment` | Place, remove, clear, or undo a hidden army edit |
| `POST` | `/game/{id}/gambit/ready` | Lock a private deployment and reveal when both are legal |
| `POST` | `/game/{id}/gambit/handoff` | Continue a local privacy handoff |
| `POST` | `/game/{id}/gambit/power` | Use Reinforce, Evolve, or Stronghold |
| `POST` | `/game/{id}/rules` | Update game rules |
| `POST` | `/game/{id}/pieces` | Customize pieces |
| `POST` | `/game/{id}/layout` | Update the board layout |
| `POST` | `/game/{id}/reset` | Reset the game |
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
| `VITE_API_URL` | Public backend address used by React |

Do not commit `.env`, database passwords, or production secrets.

## Deployment

The repository includes configuration for a free personal-project deployment:

- **Frontend:** Import the repository into Vercel, set the Root Directory to `frontend`,
  and set `VITE_API_URL` to the Render backend URL.
- **Backend:** Create a Render Blueprint from `render.yaml`, add the Firebase server
  credentials, and set `PERSISTENCE_BACKEND=firestore`.
- **Database:** Create a free Firebase project and its default Cloud Firestore database.

See [Firebase Setup](docs/FIREBASE_SETUP.md) for the exact credential, migration, Render,
security-rule, rollback, and verification steps.

After Vercel deploys, set both Render values to the production frontend URL:

```text
FRONTEND_URL=https://chass-rho.vercel.app
ALLOWED_ORIGINS=https://chass-rho.vercel.app
```

Render services may sleep when idle, but Firestore does not require manual unpausing.
