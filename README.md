# Chass!

Chass! is a full-stack browser chess platform for classic games and configurable chess
variants. It supports local two-player games, private invite-link multiplayer, custom
boards and pieces, modular rules, and real-time synchronization.

## Features

- Classic chess movement, captures, turns, check, checkmate, and stalemate
- Local hot-seat and private online multiplayer
- Shareable, one-use game invitation links
- Live WebSocket updates, reconnect, presence, and state recovery
- Variable board dimensions and editable starting layouts
- Configurable piece movement, metadata, and point values
- Toggleable rules, score-target games, and custom rule presets
- Legal-move highlighting, captured pieces, history, scores, and endgame dialogs
- Manual or automatic board flipping
- Responsive React interface for desktop and mobile

## Tech Stack

| Area | Tools |
| --- | --- |
| Languages | Python, JavaScript/JSX, CSS, SQL, Bash |
| Frontend | React 18, React Hooks, Vite 5, native WebSocket API |
| Backend | FastAPI, Uvicorn, Pydantic 2 |
| Database | SQLAlchemy 2, SQLite, PostgreSQL, Psycopg 3 |
| Testing and quality | Pytest, HTTPX, Ruff, Vite production builds |
| Hosting | Vercel, Render, Supabase |

### Main Packages

- **React:** Component-based frontend and application state management.
- **Vite:** Frontend development server and production bundler.
- **FastAPI:** REST API, WebSocket endpoints, CORS, and generated OpenAPI documentation.
- **Pydantic:** Request validation, domain models, and JSON serialization.
- **SQLAlchemy:** Database models, queries, transactions, and persistence abstraction.
- **Psycopg:** PostgreSQL driver used for Supabase deployments.
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
SQLAlchemy
  |-- SQLite locally
  `-- PostgreSQL / Supabase in production
```

Game rules are handled by a separate rule engine rather than API routes or database code.
The backend validates moves and remains authoritative during online games. Versioned
database updates prevent stale moves from one browser from overwriting newer game state.

## Project Structure

```text
backend/
  models/          Domain models and API schemas
  repositories/    SQLAlchemy persistence
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

Local development uses SQLite and does not require Supabase. Press `Ctrl+C` to stop both
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
| `DATABASE_URL` | SQLite or PostgreSQL connection string |
| `FRONTEND_URL` | Frontend address used for invite links |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins |
| `ENVIRONMENT` | `development` or `production` |
| `TOKEN_SECRET` | Private session-token hashing secret |
| `INVITE_TTL_HOURS` | Invitation expiration time |
| `GAME_TTL_DAYS` | Online game expiration time |
| `VITE_API_URL` | Public backend address used by React |

Do not commit `.env`, database passwords, or production secrets.

## Deployment

The repository includes configuration for a free personal-project deployment:

- **Frontend:** Import the repository into Vercel, set the Root Directory to `frontend`,
  and set `VITE_API_URL` to the Render backend URL.
- **Backend:** Create a Render Blueprint from `render.yaml` and provide `DATABASE_URL`,
  `FRONTEND_URL`, and `ALLOWED_ORIGINS`.
- **Database:** Create a Supabase PostgreSQL project and use its Session pooler connection
  string on port `5432` as `DATABASE_URL`.

After Vercel deploys, set both Render values to the production frontend URL:

```text
FRONTEND_URL=https://your-project.vercel.app
ALLOWED_ORIGINS=https://your-project.vercel.app
```

Render services may sleep when idle, and inactive Supabase free projects may need to be
resumed from the Supabase dashboard.
