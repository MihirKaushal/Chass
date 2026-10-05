import assert from "node:assert/strict";
import test from "node:test";

import {
  DEFAULT_SOUND_VOLUME,
  SOUND_ASSETS,
  SOUND_PREFERENCE_STORAGE_KEY,
  clockSoundPlan,
  confirmsOptimisticMove,
  gameSoundSnapshot,
  normalizeSoundPreferences,
  optimisticMoveSoundCues,
  optimisticMoveSoundToken,
  outcomeSoundForSnapshot,
  readSoundPreferences,
  soundForGameTransition,
  soundsForGameTransition,
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

test("every named game cue has a sound asset", () => {
  assert.deepEqual(Object.keys(SOUND_ASSETS).sort(), [
    "armyLockedIn",
    "capture",
    "check",
    "clock",
    "draw",
    "error",
    "explosion",
    "gameStart",
    "heavyMovement",
    "lose",
    "move",
    "scorch",
    "transformation",
    "win",
  ]);
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

test("special actions use dedicated sounds instead of the piece movement sound", () => {
  const previous = { gameId: "game-1", moveCount: 3, winner: null };
  const scorch = {
    gameId: "game-1",
    moveCount: 4,
    winner: null,
    lastActionType: "scorch",
    lastRecord: { actionType: "scorch", piece: "scorch", captures: [] },
  };
  const barricadeMove = {
    ...scorch,
    lastActionType: "move_barricade",
    lastRecord: { actionType: "move_barricade", piece: "barricade", captures: [] },
  };

  assert.deepEqual(soundsForGameTransition(previous, scorch), ["scorch"]);
  assert.deepEqual(soundsForGameTransition(previous, barricadeMove), ["heavyMovement"]);
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
    cues: ["move"],
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

test("optimistic moves select immediate capture and transformation cues", () => {
  assert.deepEqual(optimisticMoveSoundCues({
    pieceType: "pawn",
    promotion: "queen",
    move: { captures: [{ row: 0, col: 1 }] },
  }), ["capture", "transformation"]);
  assert.deepEqual(optimisticMoveSoundCues({
    pieceType: "pawn",
    promotion: "kamikaze",
    move: { captures: [] },
  }), ["explosion"]);
  assert.deepEqual(optimisticMoveSoundCues({
    pieceType: "elephant",
    move: { captures: [{ row: 3, col: 2 }] },
  }), ["heavyMovement", "capture"]);
});

test("capture and check cues layer on the same confirmed action", () => {
  const previous = gameSoundSnapshot({
    id: "game-1",
    mode: "online",
    phase: "play",
    gameStatus: "active",
    currentPlayer: "white",
    board: [],
    history: [],
  }, "white");
  const current = gameSoundSnapshot({
    id: "game-1",
    mode: "online",
    phase: "play",
    gameStatus: "check",
    currentPlayer: "black",
    board: [],
    history: [{
      moveNumber: 1,
      actionType: "move",
      player: "white",
      piece: "bishop",
      from: { row: 7, col: 2 },
      to: { row: 3, col: 6 },
      captures: [{ row: 3, col: 6, reason: null }],
    }],
  }, "white");

  assert.deepEqual(soundsForGameTransition(previous, current), ["capture", "check"]);
});

test("Kamikaze layers an explosion with the confirmed outcome", () => {
  const previous = gameSoundSnapshot({
    id: "game-1",
    mode: "online",
    phase: "play",
    gameStatus: "active",
    currentPlayer: "white",
    board: [[{ pieceId: "pawn-1", type: "pawn", color: "white" }]],
    history: [],
  }, "white");
  const current = gameSoundSnapshot({
    id: "game-1",
    mode: "online",
    phase: "finished",
    gameStatus: "checkmate",
    currentPlayer: "black",
    winner: "white",
    result: { reasonCode: "kamikaze" },
    board: [[null]],
    history: [{
      moveNumber: 1,
      actionType: "move",
      player: "white",
      piece: "pawn",
      from: { row: 0, col: 0 },
      to: { row: 0, col: 0 },
      captures: [],
    }],
  }, "white");

  assert.deepEqual(soundsForGameTransition(previous, current), ["explosion", "win"]);
});

test("piece state changes and special actions use their dedicated cues", () => {
  const previous = gameSoundSnapshot({
    id: "game-1",
    mode: "local",
    phase: "play",
    gameStatus: "active",
    currentPlayer: "white",
    board: [[{ pieceId: "piece-1", type: "pawn", color: "white", runtime: {} }]],
    history: [],
  });
  const promoted = gameSoundSnapshot({
    id: "game-1",
    mode: "local",
    phase: "play",
    gameStatus: "active",
    currentPlayer: "black",
    board: [[{ pieceId: "piece-1", type: "queen", color: "white", runtime: {} }]],
    history: [{
      moveNumber: 1,
      actionType: "move",
      player: "white",
      piece: "pawn",
      from: { row: 1, col: 0 },
      to: { row: 0, col: 0 },
      captures: [],
    }],
  });

  assert.deepEqual(
    soundsForGameTransition(previous, promoted),
    ["move", "transformation"]
  );

  const scorched = {
    ...promoted,
    moveCount: promoted.moveCount + 1,
    lastRecord: {
      actionType: "scorch",
      piece: "scorch",
      captures: [],
    },
    lastActionType: "scorch",
  };
  assert.deepEqual(soundsForGameTransition(promoted, scorched), ["scorch"]);
});

test("Gambit lock-in, game start, and neutral endings have dedicated cues", () => {
  const deployment = gameSoundSnapshot({
    id: "game-1",
    mode: "local",
    phase: "deployment",
    gameStatus: "active",
    board: [],
    history: [],
    gambit: { deploymentReady: { white: false, black: true } },
  });
  const started = gameSoundSnapshot({
    id: "game-1",
    mode: "local",
    phase: "play",
    gameStatus: "active",
    board: [],
    history: [],
    gambit: { deploymentReady: { white: true, black: true } },
  });
  const drawn = { ...started, phase: "finished", gameStatus: "stalemate" };

  assert.deepEqual(
    soundsForGameTransition(deployment, started),
    ["armyLockedIn", "gameStart"]
  );
  assert.deepEqual(soundsForGameTransition(started, drawn), ["draw"]);
  assert.deepEqual(
    soundsForGameTransition(null, started, { announceInitialStart: true }),
    ["gameStart"]
  );
  assert.deepEqual(
    soundsForGameTransition(null, { ...started, moveCount: 2 }, { announceInitialStart: true }),
    []
  );
});

test("clock plans use strict starting thresholds and exact warning durations", () => {
  const startedAt = Date.parse("2026-10-04T12:00:00Z");
  const game = {
    id: "game-1",
    phase: "play",
    gameStatus: "active",
    historyPagination: { epoch: 2 },
    clock: {
      initialSeconds: 120,
      remainingSeconds: { white: 120, black: 120 },
      activeColor: "white",
      turnStartedAt: new Date(startedAt).toISOString(),
    },
  };
  const plan = clockSoundPlan(game, startedAt);

  assert.deepEqual(plan.events.map((event) => ({
    seconds: event.seconds,
    delayMs: event.delayMs,
    durationMs: event.durationMs,
    loop: event.loop,
  })), [
    { seconds: 60, delayMs: 60000, durationMs: 5000, loop: false },
    { seconds: 30, delayMs: 90000, durationMs: 5000, loop: false },
    { seconds: 10, delayMs: 110000, durationMs: 10000, loop: true },
  ]);

  const oneMinuteGame = {
    ...game,
    clock: {
      ...game.clock,
      initialSeconds: 60,
      remainingSeconds: { white: 60, black: 60 },
    },
  };
  assert.deepEqual(
    clockSoundPlan(oneMinuteGame, startedAt).events.map((event) => event.seconds),
    [30, 10]
  );
});

test("the final clock cue loops only for the active remaining seconds", () => {
  const startedAt = Date.parse("2026-10-04T12:00:00Z");
  const game = {
    id: "game-1",
    phase: "play",
    gameStatus: "active",
    historyPagination: { epoch: 0 },
    clock: {
      initialSeconds: 120,
      remainingSeconds: { white: 120, black: 120 },
      activeColor: "white",
      turnStartedAt: new Date(startedAt).toISOString(),
    },
  };
  const plan = clockSoundPlan(game, startedAt + 112000);
  const finalCue = plan.events.find((event) => event.seconds === 10);

  assert.equal(finalCue.crossed, true);
  assert.equal(finalCue.loop, true);
  assert.equal(finalCue.activeDurationMs, 8000);
  assert.equal(finalCue.endAtMs, startedAt + 120000);
  assert.equal(clockSoundPlan({ ...game, gameStatus: "time", winner: "black" }), null);

  const tenSecondGame = {
    ...game,
    clock: {
      ...game.clock,
      initialSeconds: 10,
      remainingSeconds: { white: 10, black: 10 },
    },
  };
  assert.deepEqual(clockSoundPlan(tenSecondGame, startedAt).events, []);
});
