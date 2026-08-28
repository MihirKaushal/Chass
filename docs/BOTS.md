# Chess Bots

Chass automatically chooses a bot engine from the validated game configuration. Bot games
reuse the normal REST, WebSocket, persistence, history, cleanup, terminal-state, and rematch
paths.

## Engines And Difficulty

### Stockfish 18

Exact 8x8 Classic Chass games offer seven estimated levels:

| Estimated Elo | Label | Selection method |
| --- | --- | --- |
| 500 | Beginner | Broad stochastic choice from Stockfish-ranked legal moves |
| 800 | Learner | Stochastic choice with fewer severe errors |
| 1000 | Developing | Narrower candidate set and stronger ranking preference |
| 1200 | Intermediate | Mostly solid Stockfish-ranked choices |
| 1500 | Advanced | Stockfish native UCI Elo limiting |
| 2000 | Expert | Stockfish native UCI Elo limiting |
| 2500 | Master | Stockfish native UCI Elo limiting |

The four lower profiles use deterministic per-game variation because Stockfish 18's native
Elo floor is higher. The game ID and version seed the selection without forcing every game to
repeat the same opening.

### Fairy-Stockfish

Verified static variants offer a deliberately smaller range:

| Estimated Elo | Label | Selection method |
| --- | --- | --- |
| 500 | Beginner | Fairy native UCI strength limiting |
| 800 | Variant Learner | Fairy native UCI strength limiting |
| 1000 | Variant Challenger | Fairy native UCI strength limiting |

The pinned Fairy build advertises a wider UCI Elo range, but ratings are not calibrated across
generated boards and victory conditions. Chass therefore exposes only 500, 800, and 1000 as
conservative relative-difficulty estimates until self-play data supports a broader range.

## Compatibility

Stockfish remains preferred for the exact Classic setup. Every other bot configuration is
offered to Fairy-Stockfish when all of these conditions hold:

- Board dimensions are between 4x4 and 10x12.
- Only standard chess pieces with unchanged movement are enabled.
- Starting formations and nonnegative display point values may be customized.
- The win condition is Checkmate, Royal Center, or Check Race.
- Required check, checkmate, and stalemate rules remain active.
- Pawns begin unmoved on their normal home rank and all promotion pieces remain available.
- Castling geometry is either disabled or can be translated symmetrically.
- Gambit, custom pieces, modified movement, Special Abilities, Affinity Squares, terrain, and
  variant capture rules remain disabled.

`POST /game/validate` returns the selected engine, its compatible profile list, status, and
reason. Customize therefore opens the correct difficulty list without making the browser
duplicate compatibility rules.

## Rule Safety

Neither engine owns gameplay rules:

1. Chass generates a deterministic Fairy profile from typed, validated settings. Raw user INI
   is never accepted.
2. For Fairy games, engine legal moves and terminal outcomes are compared with the Chass Rule
   Engine before launch and before every bot turn.
3. The Rule Engine generates the complete legal move set.
4. Only those moves are passed to the selected engine through UCI `searchmoves`.
5. The selected move is validated by the Rule Engine again.
6. `GameService` applies it through the normal version-checked persistence transaction.

This keeps check, checkmate, castling, en passant, promotion, alternate victories, and future
rule fixes authoritative in one implementation. A parity mismatch safely blocks the Fairy bot
instead of allowing it to make a move under different rules.

## Runtime Lifecycle

- `mode: "bot"`, engine ID, profile, resolved side, and estimated Elo persist in `GameState`.
- The human may choose White, Black, or Random.
- One recoverable background task is permitted per game ID and expected version.
- Human move requests return before engine search completes.
- Bot replies arrive through the existing WebSocket after persistence succeeds.
- Reloading a pending turn safely reschedules it without duplicating a committed move.
- Rematches retain the engine, profile, and human side.
- The normal 24-hour inactivity lease deletes abandoned bot games and move history.

## Launch Examples

Classic:

```json
{
  "mode": "bot",
  "boardRows": 8,
  "boardCols": 8,
  "bot": {
    "profileId": "stockfish-800",
    "humanColor": "white"
  }
}
```

Static 10x10 variant:

```json
{
  "mode": "bot",
  "boardRows": 10,
  "boardCols": 10,
  "bot": {
    "profileId": "fairy-stockfish-800",
    "humanColor": "black"
  }
}
```

All profiles are published by `GET /game/catalog`. Configuration-specific profiles are also
returned by `POST /game/validate` under `bot.profiles`.

## Local And Production Setup

No paid API or new account is required. `run.sh` installs both pinned binaries when needed,
and `render.yaml` runs both verified installation scripts during deployment.

```text
MATCH_PREDICTOR_ENGINE_ENABLED=true
STOCKFISH_PATH=<optional executable override>
FAIRY_STOCKFISH_PATH=<optional executable override>
```

`/health` reports both providers under `botEngines` while preserving `classicBot` for older
deployment checks.

## Extension Path

Both adapters accept a `BotTurnContext` and return a `BotDecision`. A future native Chass bot
can implement that same boundary for custom pieces, abilities, terrain, Affinity, Gambit, and
the remaining win conditions without replacing scheduling, persistence, or frontend flows.
