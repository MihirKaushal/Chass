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

### Chass Engine

Every valid configuration that cannot be represented safely by Stockfish or Fairy-Stockfish
uses the native Chass Engine:

| Estimated Elo | Label | Selection method |
| --- | --- | --- |
| 500 | Variant Explorer | Short rules-native search with controlled action variation |
| 800 | Variant Tactician | Wider action set, more replies, and deterministic best-action selection |

These are relative difficulty labels, not calibrated chess ratings. The native engine uses a
handcrafted evaluation and bounded alpha-beta search, so even the 800 profile is expected to be
weaker than the external engines. It understands the configured pieces, editable behavior,
abilities, terrain, Affinity, command powers, runtime effects, and active win condition.

## Compatibility

Stockfish remains preferred for compatible standard-rule 8x8 games. Other configurations are
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

If a configuration falls outside that scope, or Fairy parity verification fails, Chass routes
it to the native engine. This makes the bot option available for every otherwise valid game,
including Chass Gambit and Draft Gambit.

`POST /game/validate` returns the selected engine, its compatible profile list, status, and
reason. Customize therefore opens the correct difficulty list without making the browser
duplicate compatibility rules.

## Rule Safety

No bot engine owns gameplay rules:

1. Chass generates a deterministic Fairy profile from typed, validated settings. Raw user INI
   is never accepted.
2. For Fairy games, engine legal moves and terminal outcomes are compared with the Chass Rule
   Engine before launch and before every bot turn.
3. Stockfish and Fairy receive only Rule Engine-approved moves through UCI `searchmoves`.
4. The native bot generates moves, custom actions, abilities, and command powers through the
   Chass action space, which simulates each candidate with the Rule Engine.
5. The selected action is validated by the Rule Engine again.
6. `GameService` applies it through the normal version-checked persistence transaction.

This keeps check, checkmate, castling, en passant, promotion, alternate victories, and future
rule fixes authoritative in one implementation. A parity mismatch routes the game to the native
engine instead of allowing Fairy-Stockfish to act under different rules.

## Custom Setup And Actions

The Chass bot can complete every current setup phase without exposing hidden information:

- It chooses from enabled Special Abilities up to the configured player limit.
- It drafts from the shared legal pool and respects turn, budget, and cap rules.
- It builds a legal Gambit army with exactly one King, then deploys only inside its home zone.
- It does not score or counter-pick the human's hidden army. The server uses both completed
  layouts only for the mandatory opening-safety validation before reveal.
- During play it considers normal moves, custom-piece actions, Necromancy, Getaway, Eye for an
  Eye, Episcopal, Scorch, and available Affinity command powers.

All choices are heuristic. The bot can use active mechanics, but it does not yet plan long-term
ability combinations as deeply as a trained variant engine would.

## Runtime Lifecycle

- `mode: "bot"`, engine ID, profile, resolved side, and estimated Elo persist in `GameState`.
- The human may choose White, Black, or Random.
- One recoverable background task is permitted per game ID and expected version.
- Human move requests return before engine search completes.
- Bot replies arrive through the existing WebSocket after persistence succeeds.
- Reloading a pending turn safely reschedules it without duplicating a committed move.
- If an external engine fails or Fairy parity drifts later in a game, one atomic transaction
  switches the opponent to the closest conservative Chass profile instead of stalling play.
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

Custom-rule variant:

```json
{
  "mode": "bot",
  "boardRows": 8,
  "boardCols": 8,
  "rules": [
    {"id": "double_capture_rook", "enabled": true}
  ],
  "bot": {
    "profileId": "chass-800",
    "humanColor": "white"
  }
}
```

All profiles are published by `GET /game/catalog`. Configuration-specific profiles are also
returned by `POST /game/validate` under `bot.profiles`.

## Local And Production Setup

No paid API or new account is required. `run.sh` installs both pinned external binaries when
needed, and `render.yaml` runs both verified installation scripts during deployment. The native
Chass bot ships with the backend and needs no additional process or environment variable.

```text
MATCH_PREDICTOR_ENGINE_ENABLED=true
STOCKFISH_PATH=<optional executable override>
FAIRY_STOCKFISH_PATH=<optional executable override>
```

`/health` reports all three providers under `botEngines` while preserving `classicBot` for older
deployment checks.

## Extension Path

All three adapters accept a `BotTurnContext` and return a typed `BotDecision`. New engines or
stronger native search can replace one adapter without changing scheduling, persistence,
Rule Engine authority, or frontend launch flows. The next quality step is self-play evaluation
and calibrated difficulty data for representative Chass configurations.
