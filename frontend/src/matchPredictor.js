const BACK_RANK = ["rook", "knight", "bishop", "queen", "king", "bishop", "knight", "rook"];
const OPENING_CALIBRATION_PLIES = 6;
const NON_IMMEDIATE_MATE_LIMIT = 99;

function placementSignature(placements) {
  return (placements || [])
    .filter((piece) => piece.type !== "barricade")
    .map((piece) => `${piece.row}:${piece.col}:${piece.type}:${piece.color}`)
    .sort()
    .join("|");
}

function classicPlacementSignature() {
  return placementSignature(BACK_RANK.flatMap((type, col) => [
    { row: 0, col, type, color: "black" },
    { row: 1, col, type: "pawn", color: "black" },
    { row: 6, col, type: "pawn", color: "white" },
    { row: 7, col, type, color: "white" },
  ]));
}

const CLASSIC_PLACEMENT_SIGNATURE = classicPlacementSignature();

export function isClassicStartingLayout(placements) {
  return placementSignature(placements) === CLASSIC_PLACEMENT_SIGNATURE;
}

export function shouldCalibrateClassicOpening(analysis, placements) {
  return analysis?.engineId === "stockfish" && isClassicStartingLayout(placements);
}

export function outcomePercentages(
  outcome,
  moveCount = 0,
  { calibrateOpening = true, mateIn = null } = {}
) {
  const normalizedMate = Number(mateIn);
  if (normalizedMate === 1) return { white: 100, black: 0 };
  if (normalizedMate === -1) return { white: 0, black: 100 };
  if (!outcome) return null;
  const [whiteWin, draw, blackWin] = [outcome.whiteWin, outcome.draw, outcome.blackWin].map((value) => (
    Math.max(0, Number(value) || 0)
  ));
  const total = whiteWin + draw + blackWin;
  if (!total) return null;

  // Split draw likelihood evenly, then phase in Stockfish's opening estimate so
  // the untouched initial position starts from a neutral 50/50 prior.
  const rawWhite = ((whiteWin + (draw / 2)) / total) * 100;
  const completedPlies = Math.max(0, Math.floor(Number(moveCount) || 0));
  const decisive = draw === 0 && (whiteWin === 0 || blackWin === 0);
  const engineWeight = decisive || !calibrateOpening
    ? 1
    : Math.min(1, completedPlies / OPENING_CALIBRATION_PLIES);
  const calibratedWhite = 50 + ((rawWhite - 50) * engineWeight);
  const white = Math.max(
    100 - NON_IMMEDIATE_MATE_LIMIT,
    Math.min(NON_IMMEDIATE_MATE_LIMIT, Math.round(calibratedWhite))
  );
  return { white, black: 100 - white };
}

export function evaluationLabel(
  analysis,
  moveCount = 0,
  { calibrateOpening = true } = {}
) {
  if (calibrateOpening && Math.max(0, Number(moveCount) || 0) === 0) return "-";
  const evaluation = analysis?.evaluation;
  if (!evaluation) return analysis?.status === "ready" && analysis?.outcome
    ? "Final result"
    : "Position pending";
  if (evaluation.mateIn != null) {
    const winner = evaluation.mateIn > 0 ? "White" : "Black";
    return `${winner} mates in ${Math.abs(evaluation.mateIn)}`;
  }
  if (evaluation.centipawns == null) return "Balanced position";
  const pawns = evaluation.centipawns / 100;
  if (Math.abs(pawns) < 0.005) return "Even";
  return `${pawns > 0 ? "+" : ""}${pawns.toFixed(2)} ${pawns > 0 ? "White" : "Black"}`;
}

export function analysisMatchesGame(analysis, game) {
  return Boolean(
    analysis
    && game
    && analysis.gameId === game.id
    && analysis.gameVersion === game.version
  );
}
