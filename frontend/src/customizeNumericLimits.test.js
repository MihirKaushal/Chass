import assert from "node:assert/strict";
import test from "node:test";

import {
  clampWholeNumber,
  customizeNumericBounds,
  normalizeCustomizeNumbers,
} from "./customizeNumericLimits.js";

function draft(overrides = {}) {
  return {
    boardRows: 8,
    boardCols: 8,
    barricadeCount: 1,
    enabledPieces: ["king", "queen", "rook"],
    pointValues: { king: 0, queen: 9, rook: 5 },
    pieceCaps: { king: 1, queen: 2, rook: 4 },
    victory: {
      targetPoints: 21,
      timeSeconds: 600,
      kingPoints: 0,
      dominionRounds: 3,
      checkTarget: 3,
    },
    customRules: {
      affinitySquareCount: 4,
      affinityControlRequired: 2,
      commandPointCap: 3,
    },
    specialAbilities: {
      allowed: ["getaway", "scorch"],
      maxPerPlayer: 1,
    },
    gambit: {
      budget: 39,
      maxPieces: 16,
      setupRows: 2,
      maxQueens: 2,
      draftPool: { king: 2, queen: 2, rook: 4 },
    },
    ...overrides,
  };
}

test("whole-number clamping rejects decimals and both out-of-range directions", () => {
  assert.equal(clampWholeNumber(-2, 1, 20), 1);
  assert.equal(clampWholeNumber(50, 1, 20), 20);
  assert.equal(clampWholeNumber(4.9, 1, 20), 4);
  assert.equal(clampWholeNumber("invalid", 1, 20), 1);
});

test("numeric bounds adapt Gambit limits to deployment space", () => {
  const bounds = customizeNumericBounds(draft({
    boardRows: 6,
    boardCols: 5,
    gambit: {
      budget: 39,
      maxPieces: 100,
      setupRows: 4,
      maxQueens: 99,
      draftPool: {},
    },
  }));

  assert.equal(bounds.gambitSetupRowsMaximum, 3);
  assert.equal(bounds.gambitMaxPiecesMaximum, 15);
  assert.equal(bounds.gambitMaxQueensMaximum, 14);
  assert.equal(bounds.draftPoolCountMaximum, 30);
  assert.equal(bounds.affinitySquareCountMaximum, 10);
  assert.equal(bounds.affinityControlRequiredMaximum, 2);
});

test("numeric normalization enforces linked limits and preserves meaningful zeroes", () => {
  const normalized = normalizeCustomizeNumbers(draft({
    boardRows: 6,
    boardCols: 5,
    barricadeCount: 9,
    enabledPieces: ["king", "queen", "rook", "barricade"],
    pointValues: { king: 7, queen: 0, rook: 5, barricade: 0 },
    pieceCaps: { king: 4, queen: 99, rook: 0 },
    victory: {
      targetPoints: 100001,
      timeSeconds: 30,
      kingPoints: 0,
      dominionRounds: 0,
      checkTarget: 101,
    },
    customRules: {
      affinitySquareCount: 32,
      affinityControlRequired: 16,
      commandPointCap: 0,
    },
    specialAbilities: {
      allowed: ["getaway", "scorch"],
      maxPerPlayer: 8,
    },
    gambit: {
      budget: 0,
      maxPieces: 100,
      setupRows: 4,
      maxQueens: 99,
      draftPool: { king: 9, queen: 99, rook: 0 },
    },
  }));

  assert.equal(normalized.barricadeCount, 2);
  assert.equal(normalized.pointValues.queen, 0);
  assert.equal(normalized.pieceCaps.rook, 0);
  assert.equal(normalized.victory.targetPoints, 100000);
  assert.equal(normalized.victory.timeSeconds, 60);
  assert.equal(normalized.victory.kingPoints, 7);
  assert.equal(normalized.victory.dominionRounds, 1);
  assert.equal(normalized.victory.checkTarget, 100);
  assert.equal(normalized.customRules.commandPointCap, 1);
  assert.equal(normalized.customRules.affinitySquareCount, 10);
  assert.equal(normalized.customRules.affinityControlRequired, 5);
  assert.equal(normalized.specialAbilities.maxPerPlayer, 2);
  assert.equal(normalized.gambit.budget, 7);
  assert.equal(normalized.gambit.setupRows, 3);
  assert.equal(normalized.gambit.maxPieces, 15);
  assert.equal(normalized.gambit.maxQueens, 14);
  assert.equal(normalized.pieceCaps.king, 1);
  assert.equal(normalized.pieceCaps.queen, 14);
  assert.equal(normalized.gambit.draftPool.king, 2);
  assert.equal(normalized.gambit.draftPool.queen, 30);
  assert.equal(normalized.gambit.draftPool.rook, 0);
});

test("global schema ceilings still apply on the largest board", () => {
  const bounds = customizeNumericBounds(draft({
    boardRows: 16,
    boardCols: 16,
    gambit: {
      budget: 39,
      maxPieces: 128,
      setupRows: 8,
      maxQueens: 32,
      draftPool: {},
    },
  }));

  assert.equal(bounds.gambitMaxPiecesMaximum, 128);
  assert.equal(bounds.gambitMaxQueensMaximum, 32);
  assert.equal(bounds.draftPoolCountMaximum, 256);
  assert.equal(bounds.affinitySquareCountMaximum, 32);
});
