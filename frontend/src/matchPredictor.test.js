import test from "node:test";
import assert from "node:assert/strict";

import {
  analysisMatchesGame,
  evaluationLabel,
  isClassicStartingLayout,
  outcomePercentages,
  shouldCalibrateClassicOpening,
} from "./matchPredictor.js";

const backRank = ["rook", "knight", "bishop", "queen", "king", "bishop", "knight", "rook"];

function classicLayout() {
  return backRank.flatMap((type, col) => [
    { row: 0, col, type, color: "black" },
    { row: 1, col, type: "pawn", color: "black" },
    { row: 6, col, type: "pawn", color: "white" },
    { row: 7, col, type, color: "white" },
  ]);
}

test("only the exact Stockfish Classic opening receives neutral opening calibration", () => {
  const exact = classicLayout();
  const custom = exact.filter((piece) => piece.type !== "queen");

  assert.equal(isClassicStartingLayout(exact), true);
  assert.equal(isClassicStartingLayout(custom), false);
  assert.equal(shouldCalibrateClassicOpening({ engineId: "stockfish" }, exact), true);
  assert.equal(shouldCalibrateClassicOpening({ engineId: "stockfish" }, custom), false);
  assert.equal(
    shouldCalibrateClassicOpening({ engineId: "fairy-stockfish" }, exact),
    false
  );
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

test("nonstandard formations use the raw engine estimate from move zero", () => {
  const whiteBiasedOpening = { whiteWin: 9, draw: 91, blackWin: 0 };
  assert.deepEqual(
    outcomePercentages(whiteBiasedOpening, 0, { calibrateOpening: false }),
    { white: 55, black: 45 }
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
  assert.equal(
    evaluationLabel(analysis, 0, { calibrateOpening: false }),
    "+0.62 White"
  );
});

test("mate evaluation identifies the winning side and distance", () => {
  assert.equal(
    evaluationLabel({ evaluation: { mateIn: -1 } }, 12),
    "Black mates in 1"
  );
});

test("analysis is accepted only for the current game version", () => {
  const game = { id: "classic-1", version: 7 };
  assert.equal(analysisMatchesGame({ gameId: "classic-1", gameVersion: 7 }, game), true);
  assert.equal(analysisMatchesGame({ gameId: "classic-1", gameVersion: 6 }, game), false);
  assert.equal(analysisMatchesGame({ gameId: "other", gameVersion: 7 }, game), false);
});
