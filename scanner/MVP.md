# Scanner MVP

See [verification results and remaining QA](MVP_QA.md) for the tested scope.

## Workflow

1. Open **Scanner**. Upload a JPG, PNG or WebP under 10 MB, or take a photo. Use a top-down view, even lighting, centered pieces, and no hands over the board.
2. Rotate White's home rank to the bottom, drag the four corners onto the playing grid, and apply the crop. This saves a square image for recognition, without modifying the original.
3. Click **Recognize Pieces**. SSDLite finds piece boxes; ResNet18 classifies their crops; the current geometric assignment places the selected hypotheses on an 8x8 board.
4. Gold question marks need review. Click a square to see ranked alternatives, keep its current piece, mark it empty, or use the palette to replace it. Also inspect unmarked and empty squares. Undo and Restore Scan remain available.
5. Confirm the player to move and any known historical details. Defaults: White, no castling rights, no en passant target, halfmove clock 0, full-move number 1. Leave unknown history blank. No earlier move list or captures are invented.
6. Confirm all 64 squares. The backend validates the corrected position again, then **Start Local Game** or **Create Online Game** becomes available. Online hosts play White; guests get Black, including when Black moves first. The existing invite link/code, reconnect, move validation, and 24-hour inactivity cleanup apply. Bot imports remain disabled.

The default uncertainty thresholds are 0.70 for piece classification and 0.50 for detection. Boundary-adjacent boxes, oversized boxes, and multiple detections on a square are flagged too. Scores are **not calibrated accuracy probabilities**. This integration does not improve the model's measured accuracy or establish square-level accuracy.

## Import Rules

- Classic 8x8 pieces only, one King per color, at most 16 pieces / 8 Pawns per side, and enough missing Pawns for extra promoted material.
- No Pawns on either end rank. Correct a promotion to its final piece.
- The side to move may be in check. The side that just moved cannot already be in check. Already-finished positions cannot be continued.
- Castling rights require the relevant King and Rook on their original home squares. The user must know that neither moved; a photo cannot establish this. Obstructions or check can temporarily prevent castling without revoking the confirmed historical right.
- An en passant target must match the opponent's immediately preceding double Pawn move, with an empty origin and target. It expires after one move. The halfmove clock must be zero for this setup.
- Halfmove clock: 0-99, default 0. Full-move number: 1-10000, default 1; used in engine FEN analysis. Visible move history records only moves made on Chass.
- Restart approval restores the original scanned position, turn, rights, and counters, not the standard opening.
- This is consistency validation, not proof of every historical move's legality. Repetition history before import is unknown.

## Local Use

On this machine the trained models and `.venv-scanner` already exist:

```sh
./run.sh
```

The script now starts the scanner on port 8001 when its models/environment are present. `SCANNER_ENABLED=false ./run.sh` skips that service. Do not also run a second scanner on the same port. If the game and frontend are already running, start only `./scanner/run-local.sh`.

On a fresh checkout, restore the three validated model artifacts and install `scanner/requirements-service.txt` in `.venv-scanner`. Weights and raw datasets are intentionally not committed. See `ml/IMPROVEMENTS.md` for training/artifact provenance.

## Public Website Setup

The browser uses the existing `VITE_API_URL` and calls `/scanner/health` and `/scanner/scan` on the game API. The game API proxies photos to a separate model service. **Publishing the frontend alone does not host the models.**

The public deployment now has a separate free Render service at
`https://chass-scanner.onrender.com`. It uses the same validated weights exported to
ONNX, avoiding PyTorch's memory overhead. `render.yaml` manages both services and
the shared private token through the `chass-scanner-auth` environment group. No
token belongs in Vercel. See [ONNX serving and update instructions](deploy/ONNX.md).
This does not require keeping this computer running. Free-tier cold starts and
shared workspace quotas still apply.

The steps below describe alternate hosts or rebuilding the deployment from scratch:

1. Push the code and redeploy Vercel and Render. Keep `VITE_API_URL` pointing at your game API. Remove any old direct `VITE_SCANNER_API_URL` override unless deliberately testing a separate service.
2. Choose a host for the model service. Keep PyTorch separate from the lightweight game service; confirm the host's memory limits and pricing before deploying. A portable, allowlisted bundle is prepared at `scanner/artifacts/deployment-mvp/`, including the selected weights and Dockerfile. Docker is not installed here, so its container build needs verification on the chosen Linux host.
3. To export a fresh bundle after future changes, use a new destination: `python3 -m scanner.prepare_deployment --output scanner/artifacts/deployment-next`. The exporter refuses to overwrite an existing directory. It includes model code and weights, not raw photos, datasets, Firebase credentials, or `.env` files. Review the bundle and model/data licensing before uploading it.
4. Generate a random secret locally, for example `openssl rand -hex 32`. Set that value as `SCANNER_SERVICE_TOKEN` on both the model service and Render. Never use a `VITE_` variable for this secret, paste it in chat, or commit it. The supplied container requires the token and runs one model worker on port 7860.
5. Set Render's `SCANNER_SERVICE_URL` to the model service's HTTPS base URL, without `/scan`. Save and redeploy. The gateway rejects insecure/missing-token production configuration. No new Firebase configuration is needed.
6. Open Scanner and verify **Recognition Connected**, then test a real photo and a local/online import. Check both service logs if it stays offline. Cold hosts may need time to start; retry the connection or scan.

### No-hosting-fee Development Demo

For a temporary demo, run the model on your own computer and expose only port 8001 through a Cloudflare Quick Tunnel. It creates a temporary HTTPS URL without an account or domain, but is explicitly a testing service without an uptime guarantee. The URL changes on restart and stops when the tunnel exits. [Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)

1. Stop any existing scanner process. Export a strong `SCANNER_SERVICE_TOKEN` in the terminal that starts `./scanner/run-local.sh`; set `SCANNER_REQUIRE_TOKEN=true` too. Keep the same token in Render, not in frontend variables.
2. Install `cloudflared` using the [official installation guide](https://developers.cloudflare.com/tunnel/downloads/), then run `cloudflared tunnel --url http://127.0.0.1:8001` in another terminal. This exposes the **token-protected model API**, not the whole development site.
3. Put the printed HTTPS URL in Render's `SCANNER_SERVICE_URL`, then redeploy. Leave your computer awake with both processes running during the demo. This is not always-on hosting; use a properly hosted service or a stable managed tunnel for regular public use.

Do not assume Hugging Face Docker Spaces are unconditionally free: the current overview says CPU Basic has no hourly charge but creating a compute Space requires a paid plan. Verify account eligibility/pricing before choosing it. [Hugging Face Spaces overview](https://huggingface.co/docs/hub/spaces-overview)

## Safety And Limits

- Photos are processed in memory and not saved to Firestore/SQLite. Only the reviewed game position and optional history details are persisted.
- The model service uses token authentication when configured, validates image format/size/pixels, and allows one inference at a time. The gateway adds per-IP limits, two request slots, size limits, timeouts, and does not follow redirects carrying its token.
- Model outages do not stop existing games. Manual corrections require confirmation; stale scan/validation responses are discarded, and controls lock during game creation.
- Game import uses the existing session and invitation system. No new account feature, bot import, or automatic model training is introduced.
- Hosting costs, cold starts, and model generalization still need deployment testing. The server-side token is not a replacement for monitoring or abuse controls at larger scale.
