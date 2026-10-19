export const SCANNER_PIECES = [
  { type: "king", name: "King", symbols: { white: "♔", black: "♚" } },
  { type: "queen", name: "Queen", symbols: { white: "♕", black: "♛" } },
  { type: "rook", name: "Rook", symbols: { white: "♖", black: "♜" } },
  { type: "bishop", name: "Bishop", symbols: { white: "♗", black: "♝" } },
  { type: "knight", name: "Knight", symbols: { white: "♘", black: "♞" } },
  { type: "pawn", name: "Pawn", symbols: { white: "♙", black: "♟" } },
];

export const EXAMPLE_REVIEW_SQUARES = [
  { row: 2, col: 2, label: "c6" },
  { row: 4, col: 2, label: "c4" },
];

export function scannerPreviewPiece(type, color, row, col) {
  const definition = SCANNER_PIECES.find((piece) => piece.type === type);
  return {
    pieceId: `scanner-preview-${row}-${col}`,
    type,
    name: definition.name,
    color,
    symbol: definition.symbols[color],
    isCustom: false,
  };
}

export function createScannerExample() {
  const ranks = [
    "r.bq.rk.",
    "pppp.ppp",
    "..n..n..",
    "..b.p...",
    "..B.P...",
    "...P.N..",
    "PPP..PPP",
    "RNBQ.RK.",
  ];
  const types = {
    k: "king",
    q: "queen",
    r: "rook",
    b: "bishop",
    n: "knight",
    p: "pawn",
  };

  return ranks.map((rank, row) =>
    Array.from(rank, (symbol, col) =>
      symbol === "."
        ? null
        : scannerPreviewPiece(
            types[symbol.toLowerCase()],
            symbol === symbol.toUpperCase() ? "white" : "black",
            row,
            col,
          ),
    ),
  );
}
