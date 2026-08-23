import test from "node:test";
import assert from "node:assert/strict";

import {
  analysisMatchesGame,
  isExactClassicDraft,
  outcomePercentages,
} from "./matchPredictor.js";

const backRank = ["rook", "knight", "bishop", "queen", "king", "bishop", "knight", "rook"];

function classicDraft() {
  return {
    presetId: "classic",
    formationId: "classic",
    boardRows: 8,
    boardCols: 8,
    enabledPieces: ["pawn", "knight", "bishop", "rook", "queen", "king"],
    pointValues: { pawn: 1, knight: 3, bishop: 3, rook: 5, queen: 9, king: 0 },
    pieceParameters: {},
    victory: { mode: "checkmate" },
    customRules: { affinityEnabled: false },
    specialAbilities: { enabled: false },
    gambit: { enabled: false },
    placements: backRank.flatMap((type, col) => [
      { row: 0, col, type, color: "black" },
      { row: 1, col, type: "pawn", color: "black" },
      { row: 6, col, type: "pawn", color: "white" },
      { row: 7, col, type, color: "white" },
    ]),
  };
}

test("only the exact untouched Classic draft is predictor-compatible", () => {
  const exact = classicDraft();
  assert.equal(isExactClassicDraft(exact), true);

  const customizations = [
    { ...exact, boardRows: 10 },
    { ...exact, pointValues: { ...exact.pointValues, queen: 10 } },
    { ...exact, customRules: { affinityEnabled: true } },
    { ...exact, specialAbilities: { enabled: true } },
    { ...exact, placements: exact.placements.slice(1) },
    { ...exact, pieceParameters: { rook: { range: 3 } } },
  ];
  customizations.forEach((draft) => assert.equal(isExactClassicDraft(draft), false));
});

test("outcome percentages are normalized and always total 100", () => {
  const percentages = outcomePercentages({ whiteWin: 41, draw: 40, blackWin: 19 });
  assert.deepEqual(percentages, { white: 41, draw: 40, black: 19 });
  assert.equal(Object.values(percentages).reduce((sum, value) => sum + value, 0), 100);
  assert.equal(outcomePercentages({ whiteWin: 0, draw: 0, blackWin: 0 }), null);
});

test("analysis is accepted only for the current game version", () => {
  const game = { id: "classic-1", version: 7 };
  assert.equal(analysisMatchesGame({ gameId: "classic-1", gameVersion: 7 }, game), true);
  assert.equal(analysisMatchesGame({ gameId: "classic-1", gameVersion: 6 }, game), false);
  assert.equal(analysisMatchesGame({ gameId: "other", gameVersion: 7 }, game), false);
});
