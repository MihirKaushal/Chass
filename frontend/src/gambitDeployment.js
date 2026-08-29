export const GAMBIT_ERASER_TOOL = "eraser";

export function gambitPieceAvailability({
  pieceType,
  cost,
  pointsRemaining,
  pieceCount,
  maxPieces,
  placedCount,
  pieceCap,
  draftEnabled = false,
}) {
  if (placedCount >= pieceCap) {
    if (pieceType === "king") {
      return {
        available: false,
        label: "King placed",
        reason: "Your required King is already on the board.",
      };
    }
    return {
      available: false,
      label: draftEnabled ? "Draft used" : "Limit reached",
      reason: draftEnabled
        ? "Every drafted copy of this piece is already on the board."
        : "You reached this piece's configured army limit.",
    };
  }

  if (pieceCount >= maxPieces) {
    return {
      available: false,
      label: "Army full",
      reason: `Your army already contains the maximum of ${maxPieces} pieces.`,
    };
  }

  if (cost > pointsRemaining) {
    return {
      available: false,
      label: "Unaffordable",
      reason: `This piece costs ${cost} points, but only ${pointsRemaining} remain.`,
    };
  }

  return { available: true, label: "", reason: "" };
}
