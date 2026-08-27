import assert from "node:assert/strict";
import test from "node:test";

import {
  loadPersistedGameSession,
  mergeHistoryRecords,
  persistGameSession,
  playerHasAbility,
  projectPendingMove,
} from "./gameSession.js";

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

test("online tabs retain separate seats when either page reloads", () => {
  const gameId = "shared-browser-game";
  const persistentStorage = new MemoryStorage();
  const whiteTabStorage = new MemoryStorage();
  const blackTabStorage = new MemoryStorage();

  persistGameSession(
    gameId,
    { gameId, mode: "online", color: "white", token: "white-token", role: "host" },
    whiteTabStorage,
    persistentStorage
  );
  persistGameSession(
    gameId,
    { gameId, mode: "online", color: "black", token: "black-token", role: "player" },
    blackTabStorage,
    persistentStorage
  );

  const reloadedWhite = loadPersistedGameSession(
    gameId,
    whiteTabStorage,
    persistentStorage
  );
  const reloadedBlack = loadPersistedGameSession(
    gameId,
    blackTabStorage,
    persistentStorage
  );
  const recoveredSeat = loadPersistedGameSession(
    gameId,
    new MemoryStorage(),
    persistentStorage
  );

  assert.deepEqual(
    [reloadedWhite.color, reloadedWhite.token],
    ["white", "white-token"]
  );
  assert.deepEqual(
    [reloadedBlack.color, reloadedBlack.token],
    ["black", "black-token"]
  );
  assert.deepEqual(
    [recoveredSeat.color, recoveredSeat.token],
    ["white", "white-token"]
  );
});

test("playerHasAbility reads list-shaped selections", () => {
  const game = {
    abilities: {
      selected: {
        white: ["getaway", "kamikaze"],
        black: ["episcopal"],
      },
    },
  };

  assert.equal(playerHasAbility(game, "white", "kamikaze"), true);
  assert.equal(playerHasAbility(game, "black", "kamikaze"), false);
});

test("playerHasAbility supports legacy single selections", () => {
  const game = { abilities: { selected: { white: "kamikaze" } } };

  assert.equal(playerHasAbility(game, "white", "kamikaze"), true);
  assert.equal(playerHasAbility(game, "black", "kamikaze"), false);
});

test("mergeHistoryRecords orders pages and removes overlap", () => {
  const merged = mergeHistoryRecords(
    [{ moveNumber: 2, explanation: "older" }, { moveNumber: 3 }],
    [{ moveNumber: 1 }, { moveNumber: 2, explanation: "newer" }]
  );

  assert.deepEqual(merged.map((record) => record.moveNumber), [1, 2, 3]);
  assert.equal(merged[1].explanation, "newer");
});

test("projectPendingMove applies server-provided movement and captures", () => {
  const pawn = { pieceId: "white-pawn", type: "pawn", color: "white" };
  const enemy = { pieceId: "black-pawn", type: "pawn", color: "black" };
  const game = {
    board: [
      [null, null, null],
      [null, enemy, null],
      [null, pawn, null],
    ],
  };

  const projected = projectPendingMove(game, {
    from: { row: 2, col: 1 },
    to: { row: 1, col: 1 },
    captures: [{ row: 1, col: 1, piece: enemy }],
  });

  assert.equal(projected.board[2][1], null);
  assert.equal(projected.board[1][1].pieceId, "white-pawn");
  assert.equal(projected.board[1][1].isOptimistic, true);
  assert.equal(game.board[2][1], pawn);
  assert.equal(game.board[1][1], enemy);
});

test("projectPendingMove previews promotion without mutating authoritative state", () => {
  const pawn = { pieceId: "pawn", type: "pawn", name: "Pawn", color: "white" };
  const game = {
    board: [[null], [pawn]],
    pieceDefinitions: [
      {
        type: "queen",
        name: "Queen",
        points: 9,
        symbols: { white: "Q" },
        icon: "Q",
        description: "Queen movement.",
        movement: "Slides in every direction.",
        isCustom: false,
      },
    ],
  };

  const projected = projectPendingMove(
    game,
    { from: { row: 1, col: 0 }, to: { row: 0, col: 0 }, captures: [] },
    "queen"
  );

  assert.equal(projected.board[0][0].type, "queen");
  assert.equal(projected.board[0][0].name, "Queen");
  assert.equal(game.board[1][0].type, "pawn");
});

test("projectPendingMove previews both pieces when castling", () => {
  const king = { pieceId: "king", type: "king", color: "white" };
  const rook = { pieceId: "rook", type: "rook", color: "white" };
  const game = {
    board: [[null, null, null, null, king, null, null, rook]],
  };

  const projected = projectPendingMove(game, {
    from: { row: 0, col: 4 },
    to: { row: 0, col: 6 },
    captures: [],
  });

  assert.equal(projected.board[0][4], null);
  assert.equal(projected.board[0][5].pieceId, "rook");
  assert.equal(projected.board[0][6].pieceId, "king");
  assert.equal(projected.board[0][7], null);
  assert.equal(game.board[0][4], king);
  assert.equal(game.board[0][7], rook);
});
