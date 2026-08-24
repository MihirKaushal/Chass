function boundedInteger(value, maximum) {
  const number = Number(value);
  if (!Number.isFinite(number)) return 0;
  return Math.max(0, Math.min(maximum, Math.trunc(number)));
}

const VICTORY_OWNS_LEGACY_KING_VALUE = new Set([
  "point_race",
  "royal_score",
  "king_capture",
]);

export function savedKingPointValue(victory = {}, pointValues = {}) {
  if (
    VICTORY_OWNS_LEGACY_KING_VALUE.has(victory.mode)
    && victory.kingPoints != null
  ) {
    return victory.kingPoints;
  }
  return pointValues.king ?? victory.kingPoints ?? 0;
}

export function synchronizeKingPointValue(draft, value, maximum = 100000) {
  const kingPoints = boundedInteger(value, maximum);
  return {
    ...draft,
    pointValues: { ...draft.pointValues, king: kingPoints },
    victory: { ...draft.victory, kingPoints },
  };
}

export function updatePiecePointValue(draft, pieceType, value, maximum = 100000) {
  const points = boundedInteger(value, maximum);
  const updated = {
    ...draft,
    presetId: "custom",
    pointValues: { ...draft.pointValues, [pieceType]: points },
  };
  return pieceType === "king"
    ? synchronizeKingPointValue(updated, points, maximum)
    : updated;
}
