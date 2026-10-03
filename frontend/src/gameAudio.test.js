import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_SOUND_VOLUME,
  SOUND_PREFERENCE_STORAGE_KEY,
  confirmsOptimisticMove,
  gameSoundSnapshot,
  normalizeSoundPreferences,
  optimisticMoveSoundToken,
  outcomeSoundForSnapshot,
  readSoundPreferences,
  soundForGameTransition,
  writeSoundPreferences,
} from "./gameAudio.js";

class MemoryStorage {
  constructor() {
    this.values = new Map();
  }

  getItem(key) {
    return this.values.get(key) ?? null;
  }

  setItem(key, value) {
    this.values.set(key, String(value));
  }
}

test("sound preferences clamp volume and preserve mute state", () => {
  assert.deepEqual(normalizeSoundPreferences({ volume: 4, muted: false }), {
    volume: 1,
    muted: false,
  });
  assert.deepEqual(normalizeSoundPreferences({ volume: -1, muted: false }), {
    volume: 0,
    muted: true,
  });
  assert.deepEqual(normalizeSoundPreferences({ volume: "invalid" }), {
    volume: DEFAULT_SOUND_VOLUME,
    muted: false,
  });
});

test("sound preferences persist across games", () => {
  const storage = new MemoryStorage();
  writeSoundPreferences(storage, { volume: 0.35, muted: true });

  assert.deepEqual(readSoundPreferences(storage), { volume: 0.35, muted: true });
  assert.match(storage.getItem(SOUND_PREFERENCE_STORAGE_KEY), /0.35/);
});

test("outcome sounds follow the online or bot player seat", () => {
  assert.equal(outcomeSoundForSnapshot({ mode: "online", playerColor: "white", winner: "white" }), "win");
  assert.equal(outcomeSoundForSnapshot({ mode: "online", playerColor: "black", winner: "white" }), "lose");
  assert.equal(outcomeSoundForSnapshot({ mode: "bot", playerColor: "black", winner: "black" }), "win");
  assert.equal(outcomeSoundForSnapshot({ mode: "online", playerColor: null, winner: "white" }), null);
});

test("local hot-seat games use one celebratory outcome sound", () => {
  assert.equal(outcomeSoundForSnapshot({ mode: "local", winner: "white" }), "win");
  assert.equal(outcomeSoundForSnapshot({ mode: "local", winner: "black" }), "win");
});

test("confirmed movement produces one move sound without replaying on reload", () => {
  const initial = gameSoundSnapshot({
    id: "game-1",
    mode: "local",
    winner: null,
    history: [],
    historyPagination: { totalMoves: 0 },
  });
  const moved = gameSoundSnapshot({
    id: "game-1",
    mode: "local",
    winner: null,
    history: [{ moveNumber: 1, actionType: "move" }],
    historyPagination: { totalMoves: 1 },
  });

  assert.equal(soundForGameTransition(null, moved), null);
  assert.equal(soundForGameTransition(initial, moved), "move");
  assert.equal(soundForGameTransition(moved, moved), null);
});

test("non-movement actions do not use the piece movement sound", () => {
  const previous = { gameId: "game-1", moveCount: 3, winner: null };
  const scorch = {
    gameId: "game-1",
    moveCount: 4,
    winner: null,
    lastActionType: "scorch",
  };
  const barricadeMove = {
    ...scorch,
    lastActionType: "move_barricade",
  };

  assert.equal(soundForGameTransition(previous, scorch), null);
  assert.equal(soundForGameTransition(previous, barricadeMove), "move");
});

test("a decisive result takes precedence over the final move sound", () => {
  const previous = {
    gameId: "game-1",
    mode: "online",
    playerColor: "black",
    moveCount: 20,
    winner: null,
  };
  const finished = {
    ...previous,
    moveCount: 21,
    lastActionType: "move",
    winner: "white",
  };

  assert.equal(soundForGameTransition(previous, finished), "lose");
});

test("optimistic move audio identifies the exact visible move", () => {
  const snapshot = gameSoundSnapshot({
    id: "game-1",
    mode: "online",
    version: 4,
    currentPlayer: "white",
    history: [],
  });
  const pendingMove = {
    id: 7,
    baseVersion: 4,
    move: {
      from: { row: 6, col: 4 },
      to: { row: 4, col: 4 },
    },
  };

  assert.deepEqual(optimisticMoveSoundToken(snapshot, pendingMove), {
    gameId: "game-1",
    pendingId: 7,
    baseMoveCount: 0,
    signature: "move:white:6:4:4:4",
  });
  assert.equal(
    optimisticMoveSoundToken({ ...snapshot, version: 5 }, pendingMove),
    null
  );
});

test("only the matching backend move consumes optimistic move audio", () => {
  const previous = gameSoundSnapshot({
    id: "game-1",
    mode: "online",
    version: 4,
    currentPlayer: "white",
    history: [],
  });
  const token = optimisticMoveSoundToken(previous, {
    id: 7,
    baseVersion: 4,
    move: {
      from: { row: 6, col: 4 },
      to: { row: 4, col: 4 },
    },
  });
  const confirmed = gameSoundSnapshot({
    id: "game-1",
    mode: "online",
    version: 5,
    currentPlayer: "black",
    history: [{
      moveNumber: 1,
      actionType: "move",
      player: "white",
      from: { row: 6, col: 4 },
      to: { row: 4, col: 4 },
    }],
  });
  const differentMove = {
    ...confirmed,
    lastMovementSignature: "move:white:6:3:4:3",
  };

  assert.equal(confirmsOptimisticMove(token, previous, confirmed), true);
  assert.equal(confirmsOptimisticMove(token, previous, differentMove), false);
  assert.equal(confirmsOptimisticMove(token, confirmed, confirmed), false);
});
