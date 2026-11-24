import assert from "node:assert/strict";
import test from "node:test";

import { fallbackPollDelayMs, socketShouldReconnect } from "./socketPolicy.js";

test("rejected sessions stop reconnecting while transient drops retry", () => {
  assert.equal(socketShouldReconnect(1008, null), false);
  assert.equal(socketShouldReconnect(1006, 410), false);
  assert.equal(socketShouldReconnect(1006, 403), false);
  assert.equal(socketShouldReconnect(1006, null), true);
  assert.equal(socketShouldReconnect(1011, 503), true);
  assert.equal(socketShouldReconnect(1000, null), true);
});

test("fallback polling slows down while the socket delivers updates", () => {
  assert.ok(fallbackPollDelayMs("botTurn", "connected") > fallbackPollDelayMs("botTurn", "reconnecting"));
  assert.ok(fallbackPollDelayMs("analysis", "connected") > fallbackPollDelayMs("analysis", "offline"));
  // Analysis polling must stay under the server's 120 requests per minute limit.
  assert.ok(60000 / fallbackPollDelayMs("analysis", "offline") < 120);
  assert.throws(() => fallbackPollDelayMs("unknown", "connected"));
});
