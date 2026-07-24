# Chass!

Chass! is a browser-based chess platform for classic games and configurable variants. It
supports same-device play and anonymous, invite-link multiplayer without putting chess
rules in the networking or service layer.

## Features

- Local hot-seat games with automatic board flipping
- Private online rooms with one-use invite links
- Authenticated white and black seats without requiring accounts
- REST commands plus live WebSocket state synchronization
- Automatic reconnect, heartbeat, presence, and full-state recovery
- Atomic state versions that reject stale or duplicate moves
- Real check, checkmate, stalemate, scoring, and score-target variants
- Variable boards, configurable pieces, modular rules, and custom layouts
- SQLite locally and PostgreSQL/Supabase in production
- Expiring games and invites, hashed credentials, CORS restrictions, and rate limits

## Architecture

```text
React / Vite
  |-- REST commands (create, join, move, customize)
  |-- WebSocket events (state, presence, reconnect)
  v
FastAPI application
  |-- session authorization and optimistic concurrency
  |-- pluggable RuleEngine
  v
SQLAlchemy repository
  |-- SQLite for local development
  `-- PostgreSQL / Supabase for deployment
```

Multiplayer only decides whether a player may submit a command and whether its version is
current. The `RuleEngine` remains the only authority on whether a chess move is legal.

## Run Locally

Requirements:

- Python 3.11+
- Node.js 20+
- npm

Start everything with:

```bash
./run.sh
```

The script creates or reuses `.venv`, installs missing dependencies, and starts:

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

Optional environment overrides can be placed in a root `.env` using
[`.env.example`](.env.example).

## Test and Build

```bash
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
pytest

cd frontend
npm install
npm run build
```

## Game Sessions

### Local

`POST /game/create` with `"mode": "local"` creates an unauthenticated hot-seat game.
Both players use the same browser.

### Online

`POST /game/create` with `"mode": "online"` returns:

- The initial game state
- A private white host token
- A one-use invite token and URL

Opening the invite calls `POST /game/join`, assigns black, and gives that browser its own
private player token. The raw credentials are returned once and only hashes are stored in
the database.

Online mutations require:

```http
Authorization: Bearer <player-token>
```

Move and customization requests also carry `expectedVersion`. The backend atomically
updates only that version, preventing two browsers from overwriting each other.

## API

- `POST /game/create`
- `POST /game/join`
- `GET /game/{id}`
- `POST /game/{id}/move`
- `POST /game/{id}/rules`
- `POST /game/{id}/pieces`
- `POST /game/{id}/layout`
- `POST /game/{id}/reset`
- `POST /game/{id}/invite`
- `WS /game/ws/{id}` followed by an authentication event

`GET` and mutation endpoints require the seat token for online games. Only the host may
reset or customize an online game.

## Extending Chass!

The project deliberately separates extension points:

- `backend/rules`: validation, effects, and end-state evaluators
- `backend/models/domain.py`: board, piece, move, and rule-engine state
- `backend/repositories`: persistence and concurrency, independent of chess behavior
- `backend/services`: application workflows and session authorization
- `frontend/src/components/CustomizationPanel.jsx`: variant-building UI

To add a rule, implement the shared `Rule` contract and register it in
`backend/rules/builtin_rules.py`. Multiplayer, routes, and database tables do not need to
change.

To add a custom piece, add or submit a `PieceDefinition` with movement patterns. Piece
movement remains data-driven.

Future infrastructure changes have clear boundaries:

- Add account IDs to `game_players` without changing `GameState`.
- Add a spectator role without changing move validation.
- Replace in-memory WebSocket broadcasting with Redis/Upstash pub-sub when running more
  than one backend worker.
- Normalize selected portions of `state_json` only if query/reporting needs justify it.

## Free Deployment

The included deployment path is:

- React frontend: Vercel Hobby
- FastAPI backend: Render Free Web Service
- PostgreSQL: Supabase Free

### 1. Create Supabase Database

1. Create a free [Supabase](https://supabase.com/) project.
2. In the project dashboard, select **Connect**.
3. Copy the **Session pooler** connection string on port `5432`. Render is IPv4-only, so
   do not use Supabase's IPv6-only direct connection.
4. Replace the password placeholder with the database password. Percent-encode special
   characters if you construct the URL manually.
5. Keep this value private; it becomes Render's `DATABASE_URL`.

The backend creates the required tables at startup. Supabase may pause an inactive free
project; it can be resumed from the Supabase dashboard.

### 2. Deploy FastAPI to Render

1. Push the repository to GitHub.
2. In [Render](https://render.com/), choose **New > Blueprint** and select the repository.
3. Render reads [`render.yaml`](render.yaml).
4. Provide `DATABASE_URL` from Supabase.
5. Temporarily set `FRONTEND_URL` and `ALLOWED_ORIGINS` to
   `https://example.invalid`.
6. Deploy and note the resulting URL, such as
   `https://chass-api.onrender.com`.

`TOKEN_SECRET` is generated by Render. Do not replace it after games have been created,
because existing player tokens depend on it.

### 3. Deploy React to Vercel

1. Import the same GitHub repository into [Vercel](https://vercel.com/).
2. Set the project **Root Directory** to `frontend`.
3. Confirm the framework preset is Vite.
4. Add `VITE_API_URL=https://your-api.onrender.com`.
5. Deploy and note the Vercel frontend URL.

[`frontend/vercel.json`](frontend/vercel.json) sends direct invite and game URLs to
`index.html`, allowing `/join/...` and `/game/...` to load after refresh.

### 4. Finish CORS and Invite URLs

Return to the Render service and set:

```text
FRONTEND_URL=https://your-project.vercel.app
ALLOWED_ORIGINS=https://your-project.vercel.app
```

If you later add a custom domain, update both variables. Multiple allowed origins are
comma-separated. Redeploy or restart the Render service after changing them.

## Free-Tier Limitations

- Render free services sleep when idle, so the first visit may take about a minute.
- Supabase free projects can pause after low activity.
- The WebSocket room manager is intentionally single-process. Do not add multiple Uvicorn
  workers until a shared pub-sub adapter is introduced.
- Anonymous seat credentials live in that browser's local storage. Clearing site data
  loses the seat because there are no user accounts yet.
- Free Supabase projects do not provide the same backup guarantees as paid production
  plans.

These tradeoffs are suitable for a personal portfolio project and can be upgraded behind
the existing repository and real-time interfaces later.
