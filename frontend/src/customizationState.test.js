import assert from "node:assert/strict";
import test from "node:test";

import {
  savedKingPointValue,
  synchronizeKingPointValue,
  updatePiecePointValue,
} from "./customizationState.js";

function draft() {
  return {
    presetId: "classic",
    pointValues: { pawn: 1, king: 0 },
    victory: { mode: "royal_score", kingPoints: 0 },
  };
}

test("editing the King piece value updates score-based victory settings", () => {
  const updated = updatePiecePointValue(draft(), "king", 7);
  assert.equal(updated.presetId, "custom");
  assert.equal(updated.pointValues.king, 7);
  assert.equal(updated.victory.kingPoints, 7);
});

test("editing another piece does not change the shared King value", () => {
  const updated = updatePiecePointValue(draft(), "pawn", 4);
  assert.equal(updated.pointValues.pawn, 4);
  assert.equal(updated.pointValues.king, 0);
  assert.equal(updated.victory.kingPoints, 0);
});

test("victory-side King edits use the same bounded value as Pieces", () => {
  const updated = synchronizeKingPointValue(draft(), 12, 10);
  assert.equal(updated.pointValues.king, 10);
  assert.equal(updated.victory.kingPoints, 10);
});

test("saved drafts preserve the value that governed their existing game", () => {
  assert.equal(
    savedKingPointValue({ mode: "royal_score", kingPoints: 5 }, { king: 9 }),
    5
  );
  assert.equal(
    savedKingPointValue({ mode: "checkmate", kingPoints: 0 }, { king: 9 }),
    9
  );
});
