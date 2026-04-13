# Chass!

Chass! is a browser-based chess variant platform with a modular FastAPI backend and React frontend.

## MVP Highlights

- Classic chess rules with real `check`, `checkmate`, and `stalemate` detection
- Rule-engine-based validation and state evaluation (`no hardcoded move logic in services`)
- Variable board sizes (4x4 to 16x16)
- Piece metadata support (`name`, `points`, `isCustom`, `customAttributes`)
- Board flip UI, move highlighting, active rules, score, winner, and game status display
- Layered customization UI (basic setup, piece attributes, advanced rule editing)
- SQLite default persistence with `DATABASE_URL` config for future Postgres/Supabase adapter wiring
- Optional real-time sync via WebSocket

## Project Structure

```text
/backend
  /models
  /routes
  /rules
  /services
  main.py
/frontend
  /src/components
  /src/pages
  /src/styles
```

## Backend

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload
```

Backend runs at `http://localhost:8000`.

### Endpoints

- `POST /game/create`
- `GET /game/{id}`
- `POST /game/{id}/move`
- `POST /game/{id}/rules`
- `POST /game/{id}/pieces`
- `POST /game/{id}/reset`
- `WS /game/ws/{id}`

### Response State

Game responses include:

- `board`
- `currentPlayer`
- `validMoves`
- `rules`
- `winner`
- `gameStatus` (`active | check | checkmate | stalemate`)
- `score` (`{ white, black }`)

## Frontend

### Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173` and calls backend at `http://localhost:8000`.

Set a custom API URL if needed:

```bash
VITE_API_URL=http://localhost:8000 npm run dev
```

## Deployment Notes (Free-Friendly)

- Frontend: deploy `frontend` on Vercel or Netlify.
- Backend: deploy FastAPI on Render/Fly/railway free tier or personal host.
- Database default is SQLite; set `DATABASE_URL` for future Postgres/Supabase adapter integration.

## Rule Engine

Rules implement a shared contract:

- `validate(state, move, helper, params)`
- `apply(state, move, context, helper, params)`
- `evaluate_state(state, helper, params)`

`classic_chess_rules` includes bounds, turn, movement, capture, check, checkmate, stalemate, and score rules.
