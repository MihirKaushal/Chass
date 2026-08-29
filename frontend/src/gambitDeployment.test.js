import assert from "node:assert/strict";
import test from "node:test";

import { gambitPieceAvailability } from "./gambitDeployment.js";

function availability(overrides = {}) {
  return gambitPieceAvailability({
    pieceType: "rook",
    cost: 5,
    pointsRemaining: 12,
    pieceCount: 4,
    maxPieces: 16,
    placedCount: 1,
    pieceCap: 2,
    ...overrides,
  });
}

test("deployment pieces remain available within budget and army limits", () => {
  assert.deepEqual(availability(), { available: true, label: "", reason: "" });
  assert.equal(availability({ cost: 0, pointsRemaining: 0 }).available, true);
});

test("deployment pieces become unavailable when their configured cap is reached", () => {
  const queen = availability({ pieceType: "queen", placedCount: 2, pieceCap: 2 });
  assert.equal(queen.available, false);
  assert.equal(queen.label, "Limit reached");

  const king = availability({ pieceType: "king", placedCount: 1, pieceCap: 1 });
  assert.equal(king.available, false);
  assert.equal(king.label, "King placed");
});

test("deployment pieces become unavailable when the army is full", () => {
  const result = availability({ pieceCount: 16, maxPieces: 16 });
  assert.equal(result.available, false);
  assert.equal(result.label, "Army full");
});

test("deployment pieces become unavailable when their cost exceeds remaining points", () => {
  const result = availability({ cost: 9, pointsRemaining: 8 });
  assert.equal(result.available, false);
  assert.equal(result.label, "Unaffordable");
  assert.match(result.reason, /9 points/i);
});

test("Draft Gambit reports exhausted drafted inventory distinctly", () => {
  const result = availability({
    placedCount: 1,
    pieceCap: 1,
    draftEnabled: true,
  });
  assert.equal(result.available, false);
  assert.equal(result.label, "Draft used");
  assert.match(result.reason, /drafted copy/i);
});
