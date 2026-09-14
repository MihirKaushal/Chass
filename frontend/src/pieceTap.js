export function pieceTapIntent({
  detailsMode,
  hasPiece,
  clickCount,
  squareKey,
  pendingSquareKey,
}) {
  if (
    detailsMode === "double-tap"
    && hasPiece
    && (clickCount >= 2 || pendingSquareKey === squareKey)
  ) {
    return "details";
  }
  return "activate";
}
