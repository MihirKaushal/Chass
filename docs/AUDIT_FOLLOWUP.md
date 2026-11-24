# Audit follow-up

Review date: November 24, 2026. Reviewed the 17 local application commits from
`40441ef` through `51734c0`, including the security, reliability, UI, draw,
takeback, FEN, and increment changes. This is local verification, not production
acceptance or a claim that every possible configuration has been tested.

## Corrections from this review

- Firestore takebacks now delete undone move documents in the same atomic write
  as the restored position. Previously, history pagination could return an undone
  move before replay, or lose page boundaries when duplicate move numbers were
  collapsed after fetching a limited page. Regression tests cover both
  revision-precondition batches and transactional writes.
- Restarts and layout replacement build a separate state rather than mutating
  the original record. This lets snapshot tracking detect a new history epoch
  and prevents takebacks from restoring positions from the preceding game.
- A rejected takeback no longer cancels a pending bot turn. Cancellation occurs
  only after a successful, version-checked restore.

## Verification

| Check | Result |
| --- | --- |
| Backend | 439 passed; 1 Firestore emulator test skipped |
| Frontend unit tests | 251 passed |
| Scanner ML tests | 170 passed; one dependency deprecation warning |
| Full browser suite | 56 passed, desktop and narrow layouts |
| Final focused browser checks | 8 passed: resignation, draw, takeback, increments |
| Frontend production build | Passed; separate Customizer, Scanner, Rulebook chunks |
| Ruff, generated catalog check, whitespace check | Passed |

The browser server disables rate limits only in `scripts/e2e_server.py`, after
constructing its temporary local SQLite environment. Production code has no
corresponding bypass; backend tests still exercise enforcement. These tests do
not exercise the deployed Render proxy or a live Firestore database.

## Remaining work

- After deployment, check authenticated `/internal/diagnostics` and confirm
  `rateLimiter.requestResolvedAs` matches the real caller. The trusted proxy-hop
  count must match the actual deployment; do not trust arbitrary forwarded
  headers when exposing the application directly. Keep diagnostic tokens private.
- Confirm the existing Firestore emulator CI job passes and verify production
  history-query indexes before release. The local fake-repository tests are not a
  substitute for this check.
- Drag-and-drop remains unimplemented. Preserve click, keyboard, promotion,
  special-action targeting, flipped boards, and server-authoritative validation
  when adding it.
- Keep Git LFS/model artifact migration separate: build downloads, scanner
  hosting, browser asset paths, and rollback need verification together. No model
  files or history were migrated in this review.
- A CSP needs an inventory of API/WebSocket origins, worker/WASM inference,
  model assets, fonts, and camera/image flows. Start with report-only testing;
  no untested blocking policy was added.
- Large-file extraction, design-token consolidation, and the 1300px side-panel
  breakpoint remain follow-ups. Avoid changing the breakpoint without checking
  board dimensions and panel readability on laptop viewports.
- Full PGN export still needs correct standard algebraic notation. FEN exports
  a position, not a complete game record.
- Local/bot game URLs remain access credentials by design. Device-bound tokens
  would require a compatibility and recovery plan for existing saved games.

No commits were pushed and no production settings were changed in this review.
