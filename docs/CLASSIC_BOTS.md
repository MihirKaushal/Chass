# Classic Bots

Chass supports computer opponents for exact Classic 8x8 games. Bot games use the same REST,
WebSocket, persistence, history, cleanup, checkmate, and rematch paths as other games.

## Difficulty Profiles

| Estimated Elo | Label | Selection method |
| --- | --- | --- |
| 500 | Beginner | Broad stochastic choice from Stockfish-ranked legal moves |
| 800 | Learner | Stochastic choice with fewer severe errors |
| 1000 | Developing | Narrower candidate set and stronger ranking preference |
| 1200 | Intermediate | Mostly solid Stockfish-ranked choices |
| 1500 | Advanced | Stockfish native UCI Elo limiting |
| 2000 | Expert | Stockfish native UCI Elo limiting |
| 2500 | Master | Stockfish native UCI Elo limiting |

The ratings are estimates, not certified player ratings. Stockfish's native strength range
does not cover the four lowest targets, so those profiles use deterministic per-game variation
over engine-ranked candidates. The game ID and version seed that selection, producing
repeatable server behavior without making every game use the same opening.

## Rule Safety

The bot adapter does not own chess rules:

1. The Chass Rule Engine generates the complete legal move set.
2. Only those moves are sent to Stockfish through UCI `searchmoves`.
3. Stockfish ranks or selects one candidate according to the difficulty profile.
4. The Rule Engine validates the selected move again.
5. `GameService` applies and persists it through the normal version-checked transaction.

This keeps check, checkmate, castling, en passant, promotion, history, and future rule fixes in
one authoritative implementation.

## Compatibility

Bot launch is currently enabled only when all of these are true:

- Classic variant on an 8x8 board
- Standard starting formation and all six Classic piece types
- Standard Classic movement, values, rules, and checkmate victory
- No custom pieces, custom rules, terrain, Gambit setup, or special abilities

`POST /game/validate` returns a separate `bot` compatibility result so Customize can disable
bot launch without coupling bot eligibility to Match Analysis eligibility.

## Runtime Lifecycle

- `mode: "bot"` and the selected profile are persisted in `GameState`.
- The human may choose White, Black, or Random; the server resolves Random once at creation.
- A scheduler permits one bot task per game ID and expected game version.
- Human moves return immediately while the bot works in the background.
- Bot replies arrive through the existing WebSocket and are persisted before broadcast.
- Loading a pending bot turn safely reschedules it if no task is running.
- A rematch resets immediately and retains the selected side and profile.
- The normal 24-hour inactivity lease deletes abandoned bot games and move history.

## Launch Contract

```json
{
  "mode": "bot",
  "variant": "classic",
  "boardRows": 8,
  "boardCols": 8,
  "bot": {
    "profileId": "stockfish-800",
    "humanColor": "white"
  }
}
```

Available profiles are published by `GET /game/catalog` under `botProfiles`.

## Local And Production Setup

No paid API or new external account is required. `run.sh` installs and reuses the local
Stockfish 18 binary. Render already installs the same pinned engine during its build through
`scripts/install_stockfish.sh`.

Keep these settings enabled in production:

```text
MATCH_PREDICTOR_ENGINE_ENABLED=true
STOCKFISH_PATH=<optional executable override>
```

The `/health` response reports `classicBot: "ready"` when the shared engine process is ready.

## Extension Path

The bot interface accepts a `BotTurnContext` and returns a `BotDecision`. Future
Fairy-Stockfish or native Chass bot adapters can implement that boundary while continuing to
use the same scheduler, persistence model, API, and Rule Engine validation pipeline.
