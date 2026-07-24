# Chass!

Chass! is a full-stack, browser-based chess platform where the rules are part of the
product. Players can start a familiar local chess match, invite a friend to a private
online room, or build a variant with a different board, movement system, scoring model,
and win condition.

The project is designed around one central constraint: chess behavior belongs in a
pluggable rule engine, not in API routes, database code, or multiplayer networking. That
separation keeps the classic game reliable while making new variants straightforward to
add.

## What Chass! Demonstrates

- Full-stack application development with React, FastAPI, and PostgreSQL
- Server-authoritative real-time multiplayer over WebSockets
- Domain modeling for boards, pieces, movement patterns, moves, rules, and game states
- Optimistic concurrency control across multiple browsers
- A modular rule engine with simulated-move validation for check and checkmate
- Secure anonymous sessions with expiring, one-use invitation links
- Environment-based deployment across Vercel, Render, and Supabase
- Automated API tests and reproducible frontend production builds

## Product Highlights

### Play

- Local hot-seat games for two players on one device
- Private online games through shareable invitation links
- Automatic board flipping after each move, with manual and automatic controls
- Legal-move highlighting, move history, captured pieces, scores, and endgame dialogs
- Piece metadata tooltips with names, colors, point values, and custom attributes
- Real check, checkmate, and stalemate evaluation

### Customize

- Independent board row and column dimensions
- Visual starting-layout editor
- Rule toggles and quick presets
- Configurable piece point values and data-driven movement patterns
- Score-target mode, including a configurable target such as 21 points
- Example variant rule where a rook can capture two aligned pieces
- Structured basic, piece, rule-builder, and raw configuration layers

### Connect

- Authenticated White and Black seats without requiring user accounts
- REST commands for actions and WebSockets for live state updates
- Presence updates, heartbeats, automatic reconnect, and full-state recovery
- One-use invites that can expire, be replaced, and cannot overfill a room
- Persistent games backed by SQLite locally or PostgreSQL in production

## Technology Stack

| Layer | Technology | How it is used |
| --- | --- | --- |
| Languages | Python, JavaScript/JSX, CSS, SQL, Bash | Backend domain logic, React UI, styling, relational persistence, and local automation |
| Frontend | React 18 | Functional components and hooks for game, lobby, customization, and routing state |
| Frontend tooling | Vite 5, `@vitejs/plugin-react` | Fast local development and optimized production bundles |
| Backend | FastAPI | Typed REST endpoints, dependency-friendly routing, CORS, and WebSocket handling |
| Application server | Uvicorn | ASGI server for HTTP and WebSocket traffic |
| Validation | Pydantic 2 | API contracts, aliases, domain validation, serialization, and legacy-state migration |
| Persistence | SQLAlchemy 2 | Repository-based database access, transactions, constraints, and atomic updates |
| Local database | SQLite | Zero-configuration development and automated test storage |
| Production database | PostgreSQL via Supabase | Durable hosted game, player, invitation, and move data |
| PostgreSQL driver | Psycopg 3 | SQLAlchemy connectivity to Supabase/PostgreSQL |
| Real-time transport | Native WebSocket API and FastAPI WebSockets | Low-latency state, presence, authentication, heartbeat, and sync events |
| Testing | Pytest and HTTPX | API, authorization, invite lifecycle, concurrency, and WebSocket integration tests |
| Code quality | Ruff | Python linting and consistency checks |
| Deployment | Vercel, Render Blueprint, Supabase | Free-tier frontend, backend, and PostgreSQL hosting |

The frontend intentionally uses standard CSS rather than a component framework. This
keeps the blueprint-inspired visual system, responsive board layout, and interaction
states fully controlled by the project.

## Architecture

```text
React + Vite
  |-- REST: create, join, move, customize, reset
  |-- WebSocket: authenticate, sync, presence, game events
  v
FastAPI routes
  v
GameService
  |-- session authorization
  |-- command orchestration
  |-- no embedded chess rules
  +----------------------+----------------------+
  v                                             v
RuleEngine                                    GameRepository
  |-- validate                                |-- atomic versions
  |-- apply                                   |-- player seats
  |-- evaluate                                |-- expiring invites
  |-- simulate legal moves                    |-- move audit records
  v                                             v
Pydantic domain models                       SQLAlchemy
                                                |-- SQLite
                                                `-- PostgreSQL / Supabase
```

### Rule Engine

Every enabled rule can participate in three phases:

1. `validate`: accept or reject a proposed move.
2. `apply`: modify state and record effects such as captures or score changes.
3. `evaluate_state`: determine check, checkmate, stalemate, or a variant win condition.

`CheckRule` simulates a proposed move before accepting it, preventing a player from
leaving their own king attacked. `CheckmateRule` and `StalemateRule` generate every legal
move for the current player and evaluate whether any move can escape the position. This
logic remains reusable because it depends on the shared rule and movement contracts, not
on HTTP or UI code.

The classic rule group currently includes bounds, piece presence, turn enforcement,
data-driven movement, capture behavior, king safety, checkmate, stalemate, and scoring.
Variant rules can be enabled alongside that group or selectively configured through the
customization interface.

### Multiplayer Consistency

The backend is authoritative. Browsers request moves, but only the server validates and
applies them.

Each saved game has a monotonically increasing `version`. A mutation includes the
browser's `expectedVersion`, and SQLAlchemy issues an atomic update constrained by both
the game ID and that version. If another browser has already changed the game, the stale
request receives a conflict instead of overwriting newer state.

WebSockets broadcast the accepted state after persistence succeeds. Reconnecting clients
request a complete state snapshot, so correctness does not depend on receiving every
individual event.

### Persistence Model

Chass! stores the game aggregate as validated JSON while keeping multiplayer and audit
concerns relational:

- `games`: serialized game state, mode, version, timestamps, and expiration
- `game_players`: unique color seats, roles, hashed credentials, and presence timestamps
- `game_invites`: one-use invitation hashes, expiration, use, and revocation state
- `moves`: append-only move metadata tied to a specific game version

This provides fast state reconstruction for customizable variants while preserving
constraints and queryable records for multiplayer behavior. The repository boundary also
allows the storage strategy to evolve without changing the rule engine.

### Security Model

- Online API and WebSocket access requires a private seat token.
- Raw player and invitation tokens are returned once; only HMAC-SHA256 hashes are stored.
- White and Black seats are unique at the database level.
- Only the online host can reset or customize a game.
- Invitation claims are transactional, one-use, replaceable, and time-limited.
- Production CORS is restricted to configured frontend origins.
- Sensitive endpoints use a lightweight sliding-window rate limiter.
- Secrets and database credentials are supplied through environment variables.

This is an anonymous-session model for a portfolio MVP, not a replacement for full user
identity. Account support can be added without moving chess rules into the authentication
layer.

## Repository Structure

```text
backend/
  models/          Pydantic domain objects and API schemas
  repositories/    SQLAlchemy persistence and concurrency control
  routes/          FastAPI REST and WebSocket endpoints
  rules/           Rule contracts, movement generation, and built-in rules
  services/        Application workflows and session authorization
  tests/           API and multiplayer integration tests
  config.py        Environment-based settings
  db.py            Database tables, engine, and session management
  main.py          FastAPI application and middleware

frontend/
  public/           Static brand assets
  src/
    api/            REST and WebSocket URL helpers
    components/     Board, lobby, navigation, history, and customization UI
    hooks/          Real-time connection lifecycle
    pages/          Home, play, join, and customize screens
    styles/         Responsive design system
  vercel.json       Single-page application routing for Vercel

render.yaml         Render backend Blueprint
run.sh              One-command local startup
```

## Run Locally

### Requirements

- Python 3.11 or newer
- Node.js 20 or newer
- npm

### One-command startup

```bash
./run.sh
```

The script creates or reuses `.venv`, installs missing dependencies, and starts both
applications:

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- Interactive API docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

Press `Ctrl+C` once to stop both services. Local development uses SQLite by default, so a
Supabase account is not required.

### Environment variables

Copy `.env.example` to `.env` only when local overrides are needed:

```bash
cp .env.example .env
```

| Variable | Purpose | Local default |
| --- | --- | --- |
| `DATABASE_URL` | SQLite or PostgreSQL connection URL | `sqlite:///backend/chass.db` |
| `FRONTEND_URL` | Canonical frontend used in invite links | `http://localhost:5173` |
| `ALLOWED_ORIGINS` | Comma-separated browser origins allowed by CORS | Local frontend |
| `ENVIRONMENT` | Enables development or production safeguards | `development` |
| `TOKEN_SECRET` | HMAC secret for seat and invite token hashes | Development-only value |
| `INVITE_TTL_HOURS` | Online invite lifetime | `24` |
| `GAME_TTL_DAYS` | Persisted online game lifetime | `30` |
| `VITE_API_URL` | Frontend's backend base URL | `http://localhost:8000` |

Never commit `.env`, database passwords, production token secrets, or raw session tokens.

## Test and Build

Run the backend test suite and linter:

```bash
source .venv/bin/activate
pip install -r backend/requirements-dev.txt
pytest
ruff check backend
```

Verify a clean frontend production build:

```bash
cd frontend
npm ci
npm run build
```

The integration suite covers local games, authenticated online seats, one-use and
replacement invites, host-only customization, stale-version rejection, and WebSocket
authentication.

## API Overview

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Deployment health check |
| `POST` | `/game/create` | Create a local or online game |
| `POST` | `/game/join` | Claim an online invitation |
| `GET` | `/game/{id}` | Load the latest authorized game state |
| `POST` | `/game/{id}/move` | Validate and apply a versioned move |
| `POST` | `/game/{id}/rules` | Configure enabled rules and parameters |
| `POST` | `/game/{id}/pieces` | Update piece definitions and attributes |
| `POST` | `/game/{id}/layout` | Replace the board's starting layout |
| `POST` | `/game/{id}/reset` | Reset an authorized game |
| `POST` | `/game/{id}/invite` | Replace an unused host invitation |
| `WS` | `/game/ws/{id}` | Authenticate and receive live game events |

Online REST requests use:

```http
Authorization: Bearer <player-token>
```

Move and customization commands also include `expectedVersion` for optimistic
concurrency control. FastAPI exposes the complete request and response schemas through
OpenAPI at `/docs`.

## Online Game Flow

1. The host creates an online game and receives the White seat token plus a one-use invite.
2. The invitation URL opens the join screen and atomically assigns the Black seat.
3. Both browsers authenticate their WebSocket connections with their private seat tokens.
4. Each move is authorized, rule-validated, version-checked, persisted, and then broadcast.
5. A disconnected browser reconnects with exponential backoff and requests the latest state.

Seat tokens are stored in that browser's local storage. Clearing site data removes the
browser's ability to reclaim the anonymous seat because user accounts are not yet part of
the MVP.

## Adding New Variants

The extension points are intentionally narrow:

- Add a rule by implementing the shared `Rule` contract and registering it in
  `backend/rules/builtin_rules.py`.
- Add movement behavior through `MovePattern` data instead of route-level conditionals.
- Add a custom piece through a `PieceDefinition`, including symbols, points, patterns, and
  metadata.
- Add a new persistence backend behind `GameRepository` without changing chess behavior.
- Add a new client experience using the existing API schemas and WebSocket protocol.

For example, `ScoreTargetWinRule` adds a configurable points-based victory condition, and
`DoubleCaptureRookRule` demonstrates a move effect that can capture multiple pieces. Both
work through the same lifecycle as classic rules.

## Free Deployment

The included deployment path uses services with free personal-project tiers:

- React frontend: Vercel
- FastAPI backend: Render
- PostgreSQL database: Supabase

### 1. Supabase

1. Create a Supabase project.
2. Open **Connect**, then **Direct > Connection string**.
3. Select the **Session pooler** URI on port `5432`.
4. Replace the password placeholder with the URL-encoded database password.
5. Keep the URL private; it becomes Render's `DATABASE_URL`.

The backend creates its tables at startup. Session pooling is used because Render's free
service connects over IPv4.

### 2. Render

1. Push the repository to GitHub.
2. In Render, choose **New > Blueprint** and select the repository.
3. Render reads `render.yaml` and creates the `chass-api` service.
4. Enter the Supabase URL as `DATABASE_URL`.
5. Initially set `FRONTEND_URL` and `ALLOWED_ORIGINS` to `https://example.invalid`.
6. Deploy and verify `https://your-api.onrender.com/health`.

Render generates `TOKEN_SECRET`. Do not rotate it while active anonymous games still need
their existing seat tokens.

### 3. Vercel

1. Import the same GitHub repository.
2. Set the Root Directory to `frontend`.
3. Confirm the Vite framework preset.
4. Add `VITE_API_URL=https://your-api.onrender.com`.
5. Deploy and copy the stable production URL.

`frontend/vercel.json` rewrites client-side game and invitation routes to `index.html`, so
direct links continue to work after refresh.

### 4. Production origins

In the Render service's **Environment** page, replace the temporary values:

```text
FRONTEND_URL=https://your-project.vercel.app
ALLOWED_ORIGINS=https://your-project.vercel.app
```

Use exact HTTPS origins without trailing slashes. For a custom domain, use that domain as
`FRONTEND_URL` and add both origins to `ALLOWED_ORIGINS`, separated by commas.

## Current Tradeoffs and Roadmap

The MVP favors a simple, understandable deployment over premature infrastructure:

- Render free services can sleep when idle, making the first request slower.
- Supabase free projects can pause after sustained low activity and be resumed manually.
- WebSocket rooms are currently process-local, so production should run one backend worker.
- Horizontal scaling requires a shared pub-sub adapter such as Redis or managed messaging.
- The rate limiter is also process-local and should move to shared storage at larger scale.
- Free-tier database backups do not provide paid-production recovery guarantees.

Natural next steps include user accounts, spectators, rematches, saved variant templates,
matchmaking, shared Redis-backed presence, Alembic migrations, and an AI opponent. These
features can build on the existing service, repository, and rule interfaces instead of
requiring a rewrite.

## Design Principle

> Networking decides who may submit a command. The rule engine decides whether the move
> is legal.

That boundary is what allows Chass! to support both dependable chess and increasingly
creative variants as the project grows.
