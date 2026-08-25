# Stockfish Match Predictor

Chass! analyzes compatible 8x8 standard-chess positions with a local Stockfish 18 process.
It displays a White/Black outcome estimate, a White-perspective evaluation, and transparent
comparisons for material, King safety, legal mobility, pawn structure, and center control.

No hosted chess service, API key, or paid dependency is required.

## Compatibility Rules

The setting starts enabled only when all of these conditions are true:

- The board is exactly 8x8.
- Only standard White and Black pieces are enabled and placed.
- Every enabled piece retains standard movement and capture behavior.
- The victory condition is Classic checkmate.
- Check, checkmate, and stalemate rules remain enabled.
- Variant rules, affinity squares, special abilities, and custom terrain are disabled.
- Both sides have exactly one King and fit within legal standard material limits.
- Unmoved Pawns begin on their home ranks and retain every standard promotion option.
- Unmoved King and Rook arrangements use only standard castling squares.

The starting formation does not need to be the standard 32-piece layout. Balanced or
asymmetric custom formations remain eligible when they satisfy the rules above. Customized
point labels are also allowed because they do not change a Checkmate game's legal moves or
result; analysis and the Material factor continue to use Stockfish's standard piece values.

Changing an incompatible setting in Customize automatically turns the preference off. The
backend independently repeats the compatibility checks and does not trust the browser flag.
Returning to a compatible configuration allows the player to enable the predictor again.

Stockfish itself supports standard chess and Chess960 rather than Chass!'s custom rules, so
the strict gate prevents plausible-looking but invalid variant estimates.

## Runtime Design

1. FastAPI returns and broadcasts the authoritative move first.
2. The analysis service snapshots the matching game version.
3. Chass! serializes the position as FEN and calculates explainable board factors off the
   event loop.
4. A persistent UCI process searches for the configured amount of time and returns score
   and W/D/L values. Suggested engine lines and search diagnostics stay server-side.
5. Results are normalized to White's perspective, cached by a SHA-256 position key, and
   broadcast over the existing game WebSocket.
6. The React client accepts only a result whose game ID and version match the current board.
   It splits draw likelihood evenly between the players. The exact Classic opening gradually
   phases in the engine estimate over the first six plies so it begins at 50/50; every other
   formation displays the raw position-based estimate immediately. A short REST polling
   fallback covers missed WebSocket messages.

Older work is cancelled when a newer position arrives. Engine failure never blocks a move
or ends a game; the card reports that analysis is unavailable while play continues.

Stockfish's W/D/L output is a position-based engine estimate, not a promise about the final
result or a model trained by this repository. Stockfish uses its own NNUE network; Chass!
adds the integration, strict compatibility layer, data normalization, caching, real-time
delivery, and interpretable factors.

## Local Setup

`./run.sh` installs the pinned engine automatically on supported macOS ARM64, macOS x86-64,
and Linux x86-64 systems. The download is verified against the digest published with the
official release.

Install it manually when needed:

```bash
./scripts/install_stockfish.sh
```

The binary is stored at `.stockfish/stockfish` and excluded from Git. On another platform,
install a compatible Stockfish build and set:

```text
STOCKFISH_PATH=/absolute/path/to/stockfish
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
```

The defaults favor a responsive free-tier deployment. Raise search time or threads only
after checking backend CPU and memory use. Match analysis is cached, so repeated positions
do not trigger another engine search.

## Render Deployment

`render.yaml` runs the verified installer during the backend build and supplies conservative
free-tier defaults. After this change is pushed:

1. Redeploy the Render service or allow the Blueprint to deploy the commit.
2. Confirm the build log ends with `Installed verified Stockfish 18`.
3. Open `/health` on the backend and confirm `matchPredictor` is `ready`.
4. Create a Classic game and a compatible custom 8x8 formation. Confirm the predictor appears
   in the left Effects panel, gives the custom formation an immediate estimate, and updates
   after a move.

No Vercel environment variable is needed beyond the existing `VITE_API_URL`.

Health values:

- `ready`: Stockfish started successfully.
- `starting`: the service is still initializing.
- `unavailable`: the path or executable failed; gameplay still works.
- `disabled`: `MATCH_PREDICTOR_ENGINE_ENABLED` is off.

Free-tier cold starts receive two longer engine startup attempts. If one position still
fails, Chass! retries it automatically after a short delay and also displays a manual
`Retry Analysis` button instead of caching the failure for the rest of the game.

## Upstream

- [Stockfish 18 release](https://github.com/official-stockfish/Stockfish/releases/tag/sf_18)
- [Stockfish W/D/L documentation](https://official-stockfish.github.io/docs/stockfish-wiki/Useful-data.html)
- [Stockfish FAQ and supported variants](https://official-stockfish.github.io/docs/stockfish-wiki/Stockfish-FAQ.html)
- [Stockfish GPLv3 license](https://github.com/official-stockfish/Stockfish/blob/master/Copying.txt)
