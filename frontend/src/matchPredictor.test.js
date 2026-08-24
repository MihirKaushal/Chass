import test from "node:test";
import assert from "node:assert/strict";

import {
  analysisMatchesGame,
  evaluationLabel,
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

test("outcome percentages split draws between White and Black", () => {
  const percentages = outcomePercentages(
    { whiteWin: 41, draw: 40, blackWin: 19 },
    6
  );
  assert.deepEqual(percentages, { white: 61, black: 39 });
  assert.equal(Object.values(percentages).reduce((sum, value) => sum + value, 0), 100);
  assert.equal(outcomePercentages({ whiteWin: 0, draw: 0, blackWin: 0 }), null);
});

test("opening calibration starts at 50/50 and fades over six plies", () => {
  const whiteBiasedOpening = { whiteWin: 9, draw: 91, blackWin: 0 };
  assert.deepEqual(outcomePercentages(whiteBiasedOpening, 0), { white: 50, black: 50 });
  assert.deepEqual(outcomePercentages(whiteBiasedOpening, 3), { white: 52, black: 48 });
  assert.deepEqual(outcomePercentages(whiteBiasedOpening, 6), { white: 55, black: 45 });
  assert.deepEqual(
    outcomePercentages({ whiteWin: 1, draw: 0, blackWin: 0 }, 0),
    { white: 100, black: 0 }
  );
});

test("opening evaluation stays neutral until the first move", () => {
  const analysis = {
    status: "ready",
    outcome: { whiteWin: 0.1, draw: 0.89, blackWin: 0.01 },
    evaluation: { centipawns: 62, mateIn: null },
  };
  assert.equal(evaluationLabel(analysis, 0), "-");
  assert.equal(evaluationLabel(analysis, 1), "+0.62 White");
});

test("analysis is accepted only for the current game version", () => {
  const game = { id: "classic-1", version: 7 };
  assert.equal(analysisMatchesGame({ gameId: "classic-1", gameVersion: 7 }, game), true);
  assert.equal(analysisMatchesGame({ gameId: "classic-1", gameVersion: 6 }, game), false);
  assert.equal(analysisMatchesGame({ gameId: "other", gameVersion: 7 }, game), false);
});
