import assert from "node:assert/strict";
import test from "node:test";

import {
  RECENT_GAMES_KEY,
  RESUMABLE_WINDOW_MS,
  forgetRecentGame,
  lastPlayedLabel,
  recentGameLabel,
  recordRecentGame,
  resumableGames,
} from "./recentGames.js";

function memoryStorage() {
  const values = new Map();
  return {
    getItem: (key) => (values.has(key) ? values.get(key) : null),
    setItem: (key, value) => values.set(key, String(value)),
  };
}

test("unfinished games are listed newest first and finished ones are hidden", () => {
  const storage = memoryStorage();
  recordRecentGame(storage, { gameId: "a", mode: "local" }, 1000);
  recordRecentGame(storage, { gameId: "b", mode: "online", color: "black" }, 2000);
  recordRecentGame(storage, { gameId: "c", mode: "bot", color: "white", finished: true }, 3000);
  assert.deepEqual(resumableGames(storage, 4000).map((entry) => entry.gameId), ["b", "a"]);

  recordRecentGame(storage, { gameId: "a", mode: "local" }, 5000);
  assert.deepEqual(resumableGames(storage, 6000).map((entry) => entry.gameId), ["a", "b"]);
});

test("games past the server idle window and forgotten games drop out", () => {
  const storage = memoryStorage();
  recordRecentGame(storage, { gameId: "old" }, 0);
  recordRecentGame(storage, { gameId: "new" }, RESUMABLE_WINDOW_MS);
  assert.deepEqual(resumableGames(storage, RESUMABLE_WINDOW_MS + 1).map((e) => e.gameId), ["new"]);
  forgetRecentGame(storage, "new");
  assert.deepEqual(resumableGames(storage, RESUMABLE_WINDOW_MS + 1), []);
});

test("corrupt or unavailable storage never breaks Home", () => {
  const storage = memoryStorage();
  storage.setItem(RECENT_GAMES_KEY, "{not json");
  assert.deepEqual(resumableGames(storage), []);
  assert.deepEqual(resumableGames(null), []);
  assert.doesNotThrow(() => recordRecentGame(null, { gameId: "x" }));
  const full = { getItem: () => "[]", setItem: () => { throw new Error("quota"); } };
  assert.doesNotThrow(() => recordRecentGame(full, { gameId: "x" }));
});

test("the index keeps no seat tokens", () => {
  const storage = memoryStorage();
  recordRecentGame(storage, { gameId: "a", mode: "online", color: "white", token: "secret" });
  assert.ok(!storage.getItem(RECENT_GAMES_KEY).includes("secret"));
});

test("labels describe the room and seat in plain words", () => {
  assert.equal(recentGameLabel({ mode: "online", color: "black" }), "Online game as Black");
  assert.equal(recentGameLabel({ mode: "bot", color: "white" }), "Bot game as White");
  assert.equal(recentGameLabel({ mode: "local" }), "Game on this device");
  assert.equal(recentGameLabel({ mode: "local", variant: "gambit" }), "Chass Gambit on this device");
  assert.equal(lastPlayedLabel(0, 20_000), "Played just now");
  assert.equal(lastPlayedLabel(0, 5 * 60_000), "Played 5 min ago");
  assert.equal(lastPlayedLabel(0, 60 * 60_000), "Played 1 hour ago");
  assert.equal(lastPlayedLabel(0, 3 * 60 * 60_000), "Played 3 hours ago");
});
