# Match Analysis

Chass! analyzes compatible games with local UCI engines. It displays a White/Black outcome
estimate, a White-perspective evaluation, and explainable comparisons for material, King
safety, legal mobility, pawn structure, and center control.

No hosted chess service, API key, or paid dependency is required. Chass automatically picks
the strongest compatible engine; players can enable or disable analysis but cannot force
an engine that does not model their rules.

## Engine Routing

### Stockfish 18

Stockfish is always preferred when the position is compatible with standard chess:

- The board is exactly 8x8.
- Only standard White and Black pieces use unchanged movement and capture behavior.
- Checkmate is the win condition, including check and stalemate rules.
- Variant rules, Affinity, abilities, terrain, and Gambit setup are disabled.
- Both sides have one King and use standard-representable material.
- Unmoved Pawns and castling rights can be represented exactly in standard FEN.

The formation may be asymmetric or omit pieces. Custom point labels are allowed because
they do not alter legal moves; engine evaluation and the Material factor continue to use
standard chess values.

Stockfish provides the strongest and most mature estimate in Chass. Its standard NNUE and
W/D/L output are used. Only the untouched Classic opening receives Chass's temporary neutral
opening calibration: the UI begins at 50/50 and phases in the engine estimate over six plies.
Other formations show the raw position estimate immediately.

### Fairy-Stockfish

Fairy-Stockfish is selected when Stockfish is incompatible and the configuration can still
be represented as a deterministic static variant:

- The board has at most 10 rows and 12 columns.
- Only standard pieces with unchanged movement are present.
- If Pawns are present, every standard promotion piece remains enabled.
- Checkmate, Royal Center, and Check Race win conditions are supported.
- Symmetric nonstandard castling geometry may be encoded when it matches Chass behavior.
- Starting formations and nonstandard army sizes may differ from standard chess.

Fairy-Stockfish uses its largeboard engine with NNUE disabled for generated variants. Its
W/D/L values are useful experimental position estimates, but they are not calibrated on
Chass games and should not be presented as equal in reliability to Stockfish's standard
chess estimates.

The following systems remain incompatible because their state cannot be expressed faithfully
by the current Fairy profile format:

- Custom pieces or customized movement
- Special Abilities
- Affinity Squares and command powers
- Scorched terrain or Barricades
- Chass Gambit and Draft Gambit setup
- Point scoring, clocks, elimination, and multi-turn Dominion
- Boards larger than 10x12, including 16x16

## Safe Profile Generation

The browser never sends Fairy INI. FastAPI rejects raw Fairy profile, variant, definition,
or INI fields. The backend compiler reads only validated typed settings, serializes a stable
signature, hashes it into a safe variant name, and emits a deterministic definition.

Generated profiles contain only bounded board dimensions, board-aware Pawn home and promotion
ranks, known win-condition fields, and validated castling files or center squares. They are
stored in a process-local temporary registry. The provider retains a bounded number of profiles
and recycles the UCI process when that limit is reached.

## Rule-Engine Parity

The Chass Rule Engine remains authoritative. A Fairy profile is not declared compatible on
syntax alone:

1. Chass generates all legal moves for the position through the Rule Engine.
2. Fairy-Stockfish independently returns its legal moves with `perft 1`.
3. Chass compares normalized source and destination coordinates.
4. Terminal positions are probed independently and the winner or draw must agree.
5. A mismatch disables analysis for that position while gameplay continues normally.

Parity results are cached by profile and position hash. The test suite also exercises the
real pinned largeboard binary when it is installed, covering legal moves and Checkmate,
Royal Center, and Check Race terminal outcomes.

## Runtime Design

1. FastAPI returns and broadcasts the authoritative move first.
2. The analysis service snapshots the matching game version.
3. The backend selects Stockfish or a generated Fairy profile.
4. Chass serializes the position and computes board-size-aware factors off the event loop.
5. The selected persistent UCI process returns a score and W/D/L values.
6. Results are normalized to White's perspective and cached by engine profile and position.
7. The current version is broadcast over the game WebSocket; stale results are ignored.

Suggested lines, depth, node counts, and timing diagnostics stay server-side. Older work is
cancelled when a newer position arrives. An engine failure never blocks a move or ends a
game; the card reports that analysis is unavailable while play continues.

These probabilities are engine estimates, not a model trained by this repository. A future
self-play dataset and calibrated probability layer are intentionally deferred.

## Local Setup

`./run.sh` installs both engines automatically on supported macOS ARM64, macOS x86-64, and
Linux x86-64 systems. Downloads are pinned and verified with SHA-256 before installation.
Fairy-Stockfish is built with largeboard support from pinned source.

Install either engine manually when needed:

```bash
./scripts/install_stockfish.sh
./scripts/install_fairy_stockfish.sh
```

The binaries are stored under `.stockfish/` and excluded from Git. On another platform,
build compatible executables and set:

```text
STOCKFISH_PATH=/absolute/path/to/stockfish
FAIRY_STOCKFISH_PATH=/absolute/path/to/fairy-stockfish
```

## Configuration

```text
MATCH_PREDICTOR_ENGINE_ENABLED=true
STOCKFISH_PATH=.stockfish/stockfish
STOCKFISH_MOVETIME_MS=180
STOCKFISH_HASH_MB=32
STOCKFISH_THREADS=1
STOCKFISH_STARTUP_TIMEOUT_SECONDS=15
STOCKFISH_STARTUP_ATTEMPTS=2
FAIRY_STOCKFISH_PATH=.stockfish/fairy-stockfish
FAIRY_STOCKFISH_MOVETIME_MS=180
FAIRY_STOCKFISH_HASH_MB=16
FAIRY_STOCKFISH_THREADS=1
FAIRY_STOCKFISH_MAX_PROFILES=256
```

The defaults favor responsive free-tier deployment. Raise search time, threads, or hash
memory only after checking backend CPU and memory use.

## Render Deployment

`render.yaml` installs both verified engines and supplies conservative free-tier defaults.
After pushing this change:

1. Redeploy the Render service or allow the Blueprint to deploy the commit.
2. Confirm the build log reports both verified engine installations.
3. Open `/health` and inspect `matchPredictorEngines.stockfish` and
   `matchPredictorEngines.fairyStockfish`.
4. Create an 8x8 standard-rule game and confirm Stockfish is selected.
5. Create a compatible 10x10 standard-piece game and confirm Fairy-Stockfish is selected and
   marked parity verified in Customize.

Fairy-Stockfish starts lazily on its first compatible validation or game. Before that first
use, its detailed health value may be `not_started`. No new Vercel variable is required.

Overall health values:

- `ready`: at least one configured engine process is ready.
- `starting`: an enabled engine has not started yet.
- `unavailable`: configured engines failed to start.
- `disabled`: `MATCH_PREDICTOR_ENGINE_ENABLED` is off.

Free-tier cold starts receive two startup attempts. Failed position analysis expires from
the negative cache after a short delay and can also be retried from the UI.

## Upstream

- [Stockfish 18 release](https://github.com/official-stockfish/Stockfish/releases/tag/sf_18)
- [Stockfish W/D/L documentation](https://official-stockfish.github.io/docs/stockfish-wiki/Useful-data.html)
- [Stockfish GPLv3 license](https://github.com/official-stockfish/Stockfish/blob/master/Copying.txt)
- [Fairy-Stockfish repository](https://github.com/fairy-stockfish/Fairy-Stockfish)
- [Fairy-Stockfish variants documentation](https://fairy-stockfish.github.io/)
- [Pinned Fairy-Stockfish source](https://github.com/fairy-stockfish/Fairy-Stockfish/tree/6d9d0f5724677dc3aba3c577b0b482b6ec11e44a)
- [Fairy-Stockfish GPLv3 license](https://github.com/fairy-stockfish/Fairy-Stockfish/blob/master/LICENSE)
