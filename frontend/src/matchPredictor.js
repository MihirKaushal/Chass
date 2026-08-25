const CLASSIC_TYPES = ["pawn", "knight", "bishop", "rook", "queen", "king"];
const CLASSIC_TYPE_SET = new Set(CLASSIC_TYPES);
const PROMOTION_TYPES = ["knight", "bishop", "rook", "queen"];
const CLASSIC_STARTING_COUNTS = {
  pawn: 8,
  knight: 2,
  bishop: 2,
  rook: 2,
  queen: 1,
  king: 1,
};
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

export function isClassicStartingLayout(placements) {
  return placementSignature(placements) === CLASSIC_PLACEMENT_SIGNATURE;
}

function placementCompatibilityReason(draft, enabledTypes) {
  const placements = draft.placements || [];
  const occupied = new Set();
  for (const piece of placements) {
    if (
      !CLASSIC_TYPE_SET.has(piece.type)
      || !["white", "black"].includes(piece.color)
      || !enabledTypes.has(piece.type)
    ) {
      return "Only enabled White and Black standard pieces can be analyzed.";
    }
    if (
      !Number.isInteger(piece.row)
      || !Number.isInteger(piece.col)
      || piece.row < 0
      || piece.row >= 8
      || piece.col < 0
      || piece.col >= 8
    ) {
      return "Every analyzed piece must be on the 8x8 board.";
    }
    const square = `${piece.row}:${piece.col}`;
    if (occupied.has(square)) return "Each analyzed square can contain only one piece.";
    occupied.add(square);
  }

  if (placements.some((piece) => piece.type === "pawn")) {
    if (PROMOTION_TYPES.some((type) => !enabledTypes.has(type))) {
      return "All standard promotion pieces must remain enabled while Pawns are in play.";
    }
  }

  for (const color of ["white", "black"]) {
    const colorPieces = placements.filter((piece) => piece.color === color);
    const counts = Object.fromEntries(
      CLASSIC_TYPES.map((type) => [
        type,
        colorPieces.filter((piece) => piece.type === type).length,
      ])
    );
    if (counts.king !== 1) return "Both sides must have exactly one King.";
    if (colorPieces.length > 16 || counts.pawn > CLASSIC_STARTING_COUNTS.pawn) {
      return "Each side must fit within standard chess material limits.";
    }

    const availablePromotions = CLASSIC_STARTING_COUNTS.pawn - counts.pawn;
    const requiredPromotions = PROMOTION_TYPES.reduce(
      (total, type) => total + Math.max(0, counts[type] - CLASSIC_STARTING_COUNTS[type]),
      0
    );
    if (requiredPromotions > availablePromotions) {
      return "The army contains more promoted material than standard chess permits.";
    }

    const pawnHomeRow = color === "white" ? 6 : 1;
    if (colorPieces.some((piece) => piece.type === "pawn" && piece.row !== pawnHomeRow)) {
      return "Starting Pawns must use their standard home rank for Stockfish analysis.";
    }

    const king = colorPieces.find((piece) => piece.type === "king");
    const homeRow = color === "white" ? 7 : 0;
    const nonstandardCastlePair = colorPieces.some((piece) => (
      piece.type === "rook"
      && piece.row === king.row
      && Math.abs(piece.col - king.col) >= 3
      && ((king.row !== homeRow || king.col !== 4) || ![0, 7].includes(piece.col))
    ));
    if (nonstandardCastlePair) {
      return "Starting Kings and Rooks must use standard castling squares.";
    }
  }

  return null;
}

export function stockfishDraftEligibility(draft) {
  if (!draft) return { eligible: false, reason: "Load a configuration first." };
  if (draft.boardRows !== 8 || draft.boardCols !== 8) {
    return { eligible: false, reason: "Match Predictor requires an 8x8 board." };
  }
  if (draft.victory?.mode !== "checkmate") {
    return { eligible: false, reason: "Choose Checkmate as the Win Condition." };
  }
  if (draft.gambit?.enabled) {
    return { eligible: false, reason: "Chass Gambit setup is not supported by Stockfish 18." };
  }
  if (draft.customRules?.affinityEnabled) {
    return { eligible: false, reason: "Turn off Affinity Squares for Stockfish analysis." };
  }
  if (draft.specialAbilities?.enabled) {
    return { eligible: false, reason: "Turn off Special Abilities for Stockfish analysis." };
  }

  const enabledTypes = new Set(draft.enabledPieces || []);
  if (!enabledTypes.size || !enabledTypes.has("king") || [...enabledTypes].some((type) => !CLASSIC_TYPE_SET.has(type))) {
    return { eligible: false, reason: "Enable only standard chess piece types." };
  }
  if ([...enabledTypes].some((type) => Object.keys(draft.pieceParameters?.[type] || {}).length)) {
    return { eligible: false, reason: "Restore standard piece movement for Stockfish analysis." };
  }

  const placementReason = placementCompatibilityReason(draft, enabledTypes);
  if (placementReason) return { eligible: false, reason: placementReason };
  return {
    eligible: true,
    reason: null,
    classicOpening: isClassicStartingLayout(draft.placements),
  };
}

export function isStockfishCompatibleDraft(draft) {
  return stockfishDraftEligibility(draft).eligible;
}

export function outcomePercentages(
  outcome,
  moveCount = 0,
  { calibrateOpening = true } = {}
) {
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
  const white = Math.max(0, Math.min(100, Math.round(calibratedWhite)));
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
