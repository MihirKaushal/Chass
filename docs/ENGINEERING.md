# Chass: Engineering Case Study

Chass combines configurable chess, real-time multiplayer, computer opponents, and
photo-to-game recognition. Its central design constraint is keeping one source of truth
for legal play while allowing engines and recognition models to be replaced independently.

## Authority And Extensibility

```text
React browser
  |-- REST actions + versioned WebSocket updates
  |      FastAPI -> GameService -> RuleEngine -> SQL/Firestore repository
  |                               |
  |                               +-> engine router -> Stockfish / Fairy / Chass
  |
  +-- edited photo -> scanner gateway -> private ONNX service
  |                   strict schema       detector -> crop classifier -> square mapping
  +-- optional on-device ONNX worker (server fallback)
             -> human correction -> imported-position validation -> normal game
```

- **Rules, not engines, decide legality.** Bot suggestions pass through the same validation
  and versioned persistence path as human moves. Configuration includes movement, abilities,
  terrain, objectives, and setup constraints rather than branching directly inside routes.
- **Compatibility is verified.** Standard-compatible 8x8 positions prefer Stockfish 18.
  Typed settings generate deterministic Fairy variants; legal moves and terminal outcomes
  are compared with Chass before use. Dynamic mechanics use the original Chass evaluator
  and selective alpha-beta/quiescence search. Native advantage shares are not calibrated
  probabilities, and estimated bot ratings are not measured tournament ratings.
- **Concurrency is explicit.** Expected-version writes reject stale updates. Seat-specific
  snapshots protect hidden deployment, reconnect restores browser seats, and asynchronous
  bot/analysis results are checked against the current position before publication.

## Recognition Is A Review Workflow

The scanner combines SSDLite detection and ResNet18 crop classification. Camera/photo
preparation, perspective correction, model inference, uncertain-square review, and import
validation are separate stages. The game API never imports Torch; ONNX serving is isolated.

The gateway validates the complete 8x8 response, labels, candidates, finite scores,
coordinates, duplicate counts, and metadata. Malformed successful upstream responses become
502 errors. The browser also validates results and preserves the review workflow after failures.
Model confidence is not described as a calibrated accuracy probability. Corrections and
model fingerprints support debugging without silently using uploads as training data.

Cold starts are surfaced without blocking photo editing. Requests have cancellation and
timeouts; camera tracks are stopped after capture or dismissal. Optional local inference
avoids sending the photo to the server when it succeeds, with explicit server fallback.
The [accuracy tracker](../scanner/ml/ACCURACY_TRACKER.md) and
[quality guide](../scanner/QUALITY.md) distinguish detection, classification, square accuracy,
dataset bias, and domain-shift limitations. Integration tests are not evidence of recognition accuracy.

## Evidence, Not Just Feature Counts

| Layer | Verification |
| --- | --- |
| Rule engine | Reference FENs and generated legal playouts compared against python-chess; parent immutability, captures, bounds, and royal-state checks |
| External engines | Launch both configured binaries, obtain evaluations and legal bot moves, compare a 10x10 Fairy legal-move set |
| Database | Firestore emulator create/join, optimistic conflict rejection, history retrieval, and cascading expiry cleanup |
| Scanner API | Malformed-response regression cases, real HTTP wrapper, and an actual ONNX-weight contract smoke test |
| Browser | Local/online moves, reconnect, camera permission/capture, review correction, validation, and local/online imports |
| Layout | Desktop and narrow-width overflow/footer/navigation assertions plus reviewable screenshots and failure traces |

The [verification guide](VERIFICATION.md) records commands and the latest local results.
CI runs without Firebase credentials or production game data. Screenshots are review artifacts;
layout assertions are automatic, but cross-platform pixel baselines are not yet enforced.

## Operational Tradeoffs

Public liveness is deliberately minimal. Separate authenticated diagnostics expose engine
status and bounded process-local counts/mean/max latency for scans, analysis, and imports,
plus Fairy-to-Chass fallback counts. They contain no photo contents, player IDs, or tokens.
Metrics reset on restart, are not a distributed monitoring system, and exclude browser-only inference.

The [initial native-search benchmark](benchmarks/native-engine-2026-11-07.json) measures six
configurations with three runs each on a local ARM64 Mac. Mean full evaluation times ranged
from roughly 101 to 289 ms; completed depth was 1. The 180 ms allowance is a search budget,
not an end-to-end deadline: legal-action generation and terminal screening happen first.
These small opening-position samples are not production latency guarantees or strength tests.

Free hosting can sleep. SQLite simplifies local work; Firestore supports persistent public
rooms. Application-managed expiry avoids accumulating abandoned games, but deletion waits
until the backend next runs. The next evidence gaps are deployed-host latency, broader
real-board scanner data, calibrated bot/analysis strength, and approved pixel baselines.

## Attribution

Stockfish and Fairy-Stockfish are upstream engines, not original Chass neural networks.
The original engineering is the modular rules, native evaluator/search, compatibility and
bot routing, scanner training/serving/review integration, and application architecture.
Reproducible measurements and clear limitations are more useful portfolio evidence than
claiming universal accuracy or human-equivalent Elo.
