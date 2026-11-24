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

test("recent cards keep three moves, status and bot level without storing the board", () => {
  const storage = memoryStorage();
  const history = Array.from({ length: 5 }, (_, index) => ({
    moveNumber: index + 1, player: "white", piece: "pawn",
    from: { row: 14, col: 15 }, to: { row: 12, col: 15 }, actionType: "move",
  }));
  recordRecentGame(storage, {
    gameId: "variant", mode: "bot", game: {
      boardRows: 16, boardCols: 16, currentPlayer: "black", phase: "play", gameStatus: "check",
      bot: { targetElo: 800 }, history, board: "private-board-data", token: "private-token",
    },
  }, 1000);
  const [entry] = resumableGames(storage, 1001);
  assert.equal(entry.summary, "16 x 16 | Black to move (in check) | Bot ~800 Elo");
  assert.deepEqual(entry.recentMoves, [3, 4, 5].map((number) => `${number}. White Pawn p2-p4`));
  assert.ok(!storage.getItem(RECENT_GAMES_KEY).includes("private-"));
});

test("setup cards describe the phase without leaking hidden histories", () => {
  const storage = memoryStorage();
  for (const mode of ["local", "online", "bot"]) {
    recordRecentGame(storage, { gameId: mode, mode, game: {
      phase: "deployment", history: [{ explanation: "secret" }], boardRows: 10, boardCols: 8,
    } }, 1000);
  }
  const entries = resumableGames(storage, 1001);
  assert.equal(entries.length, 3);
  assert.ok(entries.every((entry) => entry.summary === "10 x 8 | Placing pieces" && entry.recentMoves.length === 0));
});

test("old entries still load and malformed timestamps are ignored", () => {
  const storage = memoryStorage();
  storage.setItem(RECENT_GAMES_KEY, JSON.stringify([
    { gameId: "old", mode: "local", updatedAt: 1000 },
    { gameId: "bad", updatedAt: "not a date" },
  ]));
  assert.deepEqual(resumableGames(storage, 1001).map((entry) => entry.gameId), ["old"]);
});

test("all eight recent unfinished games are available to the carousel", () => {
  const storage = memoryStorage();
  for (let index = 0; index < 10; index++) recordRecentGame(storage, { gameId: `game-${index}` }, 1000 + index);
  assert.deepEqual(resumableGames(storage, 2000).map((entry) => entry.gameId),
    [9, 8, 7, 6, 5, 4, 3, 2].map((index) => `game-${index}`));
});
