export const PIECE_FILTERS = [
  { id: "all", label: "All" },
  { id: "enabled", label: "Enabled" },
  { id: "classic", label: "Classic" },
  { id: "custom", label: "Custom" },
];

export function visibleCustomizePieces(pieces = [], enabledTypes = [], filter = "all") {
  const enabled = new Set(enabledTypes);
  return pieces
    .map((piece, index) => ({ piece, index }))
    .filter(({ piece }) => {
      if (filter === "enabled") return enabled.has(piece.type);
      if (filter === "classic") return !piece.isCustom;
      if (filter === "custom") return Boolean(piece.isCustom);
      return true;
    })
    .sort((left, right) => (
      Number(enabled.has(right.piece.type)) - Number(enabled.has(left.piece.type))
      || left.index - right.index
    ))
    .map(({ piece }) => piece);
}
