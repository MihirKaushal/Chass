const CLASSIC_TYPES = ["pawn", "knight", "bishop", "rook", "queen", "king"];
const CLASSIC_POINTS = { pawn: 1, knight: 3, bishop: 3, rook: 5, queen: 9, king: 0 };
const BACK_RANK = ["rook", "knight", "bishop", "queen", "king", "bishop", "knight", "rook"];

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

export function outcomePercentages(outcome) {
  if (!outcome) return null;
  const rawValues = [outcome.whiteWin, outcome.draw, outcome.blackWin].map((value) => (
    Math.max(0, Number(value) || 0)
  ));
  const total = rawValues.reduce((sum, value) => sum + value, 0);
  if (!total) return null;
  const values = rawValues.map((value) => (value / total) * 100);
  const floors = values.map(Math.floor);
  let remainder = 100 - floors.reduce((total, value) => total + value, 0);
  values
    .map((value, index) => ({ index, fraction: value - floors[index] }))
    .sort((left, right) => right.fraction - left.fraction)
    .forEach(({ index }) => {
      if (remainder > 0) {
        floors[index] += 1;
        remainder -= 1;
      }
    });
  return { white: floors[0], draw: floors[1], black: floors[2] };
}

export function analysisMatchesGame(analysis, game) {
  return Boolean(
    analysis
    && game
    && analysis.gameId === game.id
    && analysis.gameVersion === game.version
  );
}
