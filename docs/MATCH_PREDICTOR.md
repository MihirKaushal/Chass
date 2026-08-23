# Classic Match Predictor

Chass! analyzes untouched Classic games with a local Stockfish 18 process. It displays
White-win, draw, and Black-win estimates, a White-perspective evaluation, a short engine
line, and transparent comparisons for material, King safety, legal mobility, pawn
structure, and center control.

No hosted chess service, API key, or paid dependency is required.

## Exact Classic Eligibility

The setting starts enabled only when all of these conditions are true:

- The mode and formation are `classic`.
- The board is exactly 8x8.
- The starting layout is the standard 32-piece position.
- Only standard pieces are enabled, with their default values and movement behavior.
- The victory condition is Classic checkmate.
- Check, checkmate, and stalemate rules remain enabled.
- Variant rules, affinity squares, special abilities, and custom terrain are disabled.
- Both Kings and only standard piece types remain in the live position.

Changing any compatible setting in Customize automatically turns the preference off. The
backend repeats the same validation and does not trust the browser flag. Returning to the
Classic Chass preset restores compatibility, after which the player can keep the default or
turn the predictor off explicitly.

Stockfish itself supports standard chess and Chess960 rather than Chass!'s custom rules, so
the strict gate prevents plausible-looking but invalid variant estimates.

## Runtime Design

1. FastAPI returns and broadcasts the authoritative move first.
2. The analysis service snapshots the matching game version.
3. Chass! serializes the position as FEN and calculates explainable board factors off the
   event loop.
4. A persistent UCI process searches for the configured amount of time and returns score,
   principal variation, and W/D/L values.
5. Results are normalized to White's perspective, cached by a SHA-256 position key, and
   broadcast over the existing game WebSocket.
6. The React client accepts only a result whose game ID and version match the current board.
   A short REST polling fallback covers missed WebSocket messages.

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
4. Create an untouched Classic game and confirm the predictor appears in the left Effects
   panel and updates after a move.

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
