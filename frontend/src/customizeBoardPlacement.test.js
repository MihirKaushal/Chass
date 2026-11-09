import assert from "node:assert/strict";
import test from "node:test";

import { boardPlacementRestriction } from "./customizeBoardPlacement.js";

function draft(overrides = {}) {
  return {
    boardRows: 8,
    boardCols: 8,
    barricadeCount: 1,
    enabledPieces: ["pawn", "king"],
    placements: [],
    victory: { mode: "checkmate" },
    customRules: { affinityEnabled: false },
    gambit: { enabled: false },
    ...overrides,
  };
}

test("pawn placement blocks only the opponent-side promotion rank", () => {
  const whitePawn = { kind: "piece", type: "pawn", color: "white" };
  const blackPawn = { kind: "piece", type: "pawn", color: "black" };
  assert.match(boardPlacementRestriction(draft(), whitePawn, 0, 3), /promotion rank/i);
  assert.equal(boardPlacementRestriction(draft(), whitePawn, 7, 3), "");
  assert.match(boardPlacementRestriction(draft(), blackPawn, 7, 3), /promotion rank/i);
  assert.equal(boardPlacementRestriction(draft(), blackPawn, 0, 3), "");
});

test("reserved and rule-significant center squares reject normal pieces", () => {
  const rook = { kind: "piece", type: "rook", color: "white" };
  const withBarricade = draft({ enabledPieces: ["king", "rook", "barricade"] });
  assert.match(boardPlacementRestriction(withBarricade, rook, 3, 3), /Barricade/i);

  const withAffinity = draft({
    enabledPieces: ["king", "rook"],
    customRules: { affinityEnabled: true },
  });
  assert.match(boardPlacementRestriction(withAffinity, rook, 3, 3), /center squares/i);
  assert.equal(boardPlacementRestriction(withAffinity, rook, 2, 3), "");
});

test("King placement prevents duplicates and touching opponents", () => {
  const whiteKing = { kind: "piece", type: "king", color: "white" };
  const blackKing = { kind: "piece", type: "king", color: "black" };
  const existingWhite = draft({
    placements: [{ row: 7, col: 4, type: "king", color: "white" }],
  });
  assert.match(boardPlacementRestriction(existingWhite, whiteKing, 6, 4), /current White King/i);

  const existingBlack = draft({
    placements: [{ row: 4, col: 4, type: "king", color: "black" }],
  });
  assert.match(boardPlacementRestriction(existingBlack, whiteKing, 5, 5), /touching squares/i);
  assert.equal(boardPlacementRestriction(existingBlack, whiteKing, 6, 6), "");
  assert.equal(boardPlacementRestriction(existingBlack, blackKing, 4, 4), "");
});

test("eraser actions remain available on otherwise restricted squares", () => {
  const state = draft({
    enabledPieces: ["king", "barricade"],
    customRules: { affinityEnabled: true },
  });
  assert.equal(
    boardPlacementRestriction(state, { kind: "erase" }, 3, 3),
    ""
  );
});
