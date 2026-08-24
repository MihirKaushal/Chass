const CLASSIC_TYPES = ["pawn", "knight", "bishop", "rook", "queen", "king"];
const CLASSIC_POINTS = { pawn: 1, knight: 3, bishop: 3, rook: 5, queen: 9, king: 0 };
const BACK_RANK = ["rook", "knight", "bishop", "queen", "king", "bishop", "knight", "rook"];
const OPENING_CALIBRATION_PLIES = 6;

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

export function isExactClassicDraft(draft) {
  if (!draft) return false;
  if (draft.presetId !== "classic" || draft.formationId !== "classic") return false;
  if (draft.boardRows !== 8 || draft.boardCols !== 8) return false;
  if (draft.victory?.mode !== "checkmate") return false;
  if (draft.gambit?.enabled || draft.customRules?.affinityEnabled) return false;
  if (draft.specialAbilities?.enabled) return false;

  const enabled = [...(draft.enabledPieces || [])].sort();
  if (enabled.join("|") !== [...CLASSIC_TYPES].sort().join("|")) return false;
  if (CLASSIC_TYPES.some((type) => Number(draft.pointValues?.[type] ?? 0) !== CLASSIC_POINTS[type])) {
    return false;
  }
  if (CLASSIC_TYPES.some((type) => Object.keys(draft.pieceParameters?.[type] || {}).length)) {
    return false;
  }
  return placementSignature(draft.placements) === CLASSIC_PLACEMENT_SIGNATURE;
}

export function outcomePercentages(outcome, moveCount = 0) {
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
  const engineWeight = decisive
    ? 1
    : Math.min(1, completedPlies / OPENING_CALIBRATION_PLIES);
  const calibratedWhite = 50 + ((rawWhite - 50) * engineWeight);
  const white = Math.max(0, Math.min(100, Math.round(calibratedWhite)));
  return { white, black: 100 - white };
}

export function analysisMatchesGame(analysis, game) {
  return Boolean(
    analysis
    && game
    && analysis.gameId === game.id
    && analysis.gameVersion === game.version
  );
}
