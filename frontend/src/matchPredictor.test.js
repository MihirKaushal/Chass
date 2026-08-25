import test from "node:test";
import assert from "node:assert/strict";

import {
  analysisMatchesGame,
  evaluationLabel,
  isClassicStartingLayout,
  isStockfishCompatibleDraft,
  outcomePercentages,
  stockfishDraftEligibility,
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

test("compatible 8x8 standard-piece formations can use Stockfish", () => {
  const exact = classicDraft();
  const withoutQueens = {
    ...exact,
    presetId: "custom",
    formationId: "custom",
    placements: exact.placements.filter((piece) => piece.type !== "queen"),
  };
  const customPointLabels = {
    ...withoutQueens,
    pointValues: { ...withoutQueens.pointValues, queen: 14, rook: 8 },
  };
  const reducedArmy = {
    ...withoutQueens,
    enabledPieces: ["rook", "king"],
    placements: withoutQueens.placements.filter((piece) => ["rook", "king"].includes(piece.type)),
  };

  assert.equal(isStockfishCompatibleDraft(exact), true);
  assert.equal(isStockfishCompatibleDraft(withoutQueens), true);
  assert.equal(isStockfishCompatibleDraft(customPointLabels), true);
  assert.equal(isStockfishCompatibleDraft(reducedArmy), true);
  assert.equal(isClassicStartingLayout(exact.placements), true);
  assert.equal(isClassicStartingLayout(withoutQueens.placements), false);
});

test("nonstandard rules, geometry, movement, and initial-state semantics remain incompatible", () => {
  const exact = classicDraft();
  const offRankPawn = exact.placements.map((piece) => (
    piece.type === "pawn" && piece.color === "white" && piece.col === 0
      ? { ...piece, row: 5 }
      : piece
  ));
  const shiftedRoyalPair = exact.placements.map((piece) => {
    if (piece.color !== "white" || piece.row !== 7) return piece;
    if (piece.type === "king") return { ...piece, col: 3 };
    if (piece.type === "queen") return { ...piece, col: 4 };
    return piece;
  });
  const customizations = [
    { ...exact, boardRows: 10 },
    { ...exact, victory: { mode: "point_race" } },
    { ...exact, customRules: { affinityEnabled: true } },
    { ...exact, specialAbilities: { enabled: true } },
    { ...exact, pieceParameters: { rook: { range: 3 } } },
    { ...exact, enabledPieces: [...exact.enabledPieces, "maharani"] },
    { ...exact, placements: offRankPawn },
    { ...exact, placements: shiftedRoyalPair },
  ];
  customizations.forEach((draft) => assert.equal(isStockfishCompatibleDraft(draft), false));
  assert.match(stockfishDraftEligibility(customizations[0]).reason, /8x8/);
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
