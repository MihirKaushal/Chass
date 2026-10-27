const TYPES = new Set(["pawn", "knight", "bishop", "rook", "queen", "king"]);

export function defaultScannerDetails() {
  return {
    currentPlayer: "white",
    castlingRights: {
      whiteKing: false,
      whiteQueen: false,
      blackKing: false,
      blackQueen: false,
    },
    enPassant: null,
    halfmoveClock: 0,
    fullmoveNumber: 1,
  };
}

export function pieceFromLabel(label) {
  if (typeof label !== "string") return null;
  const [color, type, extra] = label.split("-");
  return ["white", "black"].includes(color) && TYPES.has(type) && !extra
    ? { color, type }
    : null;
}

export function squareAlternatives(scan, square) {
  if (!square) return [];
  const entry = scan?.squareCandidates?.find(
    ({ row, col }) => row === square.row && col === square.col,
  );
  const ranked = new Map();
  for (const candidate of entry?.candidates || []) {
    for (const option of [
      {
        label: candidate.class,
        score: candidate.classifierScore ?? candidate.score,
      },
      ...(candidate.alternatives || []),
    ]) {
      if (!option) continue;
      const piece = pieceFromLabel(option.label);
      if (
        !piece ||
        !Number.isFinite(option.score) ||
        option.score < 0 ||
        option.score > 1
      )
        continue;
      const old = ranked.get(option.label);
      if (!old || option.score > old.score)
        ranked.set(option.label, {
          ...piece,
          label: option.label,
          score: option.score,
        });
    }
  }
  return [...ranked.values()].sort((a, b) => b.score - a.score).slice(0, 4);
}

export function scannerImportPayload(
  board,
  details,
  { mode = "local", confirmed = false } = {},
) {
  return {
    ...details,
    mode,
    reviewConfirmed: confirmed,
    board: board.map((rank) =>
      rank.map((piece) => (piece ? `${piece.color}-${piece.type}` : null)),
    ),
    halfmoveClock:
      details.halfmoveClock === "" ? 0 : Number(details.halfmoveClock),
    fullmoveNumber:
      details.fullmoveNumber === "" ? 1 : Number(details.fullmoveNumber),
  };
}

export function scannerDetailError(details) {
  for (const [key, min, max, label] of [
    ["halfmoveClock", 0, 99, "Halfmove clock"],
    ["fullmoveNumber", 1, 10000, "Move number"],
  ]) {
    if (details[key] === "") continue;
    const value = Number(details[key]);
    if (!Number.isInteger(value) || value < min || value > max)
      return `${label} must be a whole number from ${min} to ${max}.`;
  }
  return "";
}
