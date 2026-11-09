import { barricadeSquares, significantCenterSquares } from "./boardGeometry.js";

function occupies(piece, row, col) {
  return piece.row === row && piece.col === col;
}

export function boardPlacementRestriction(draft, tool, row, col) {
  if (!draft || !tool || tool.kind === "erase" || draft.gambit?.enabled) return "";
  if (
    !Number.isInteger(row)
    || !Number.isInteger(col)
    || row < 0
    || row >= draft.boardRows
    || col < 0
    || col >= draft.boardCols
  ) {
    return "Choose a square inside the board.";
  }

  const reservedForBarricade = (
    draft.enabledPieces?.includes("barricade")
    && barricadeSquares(
      draft.boardRows,
      draft.boardCols,
      draft.barricadeCount
    ).some((square) => occupies(square, row, col))
  );
  if (reservedForBarricade && tool.type !== "barricade") {
    return "That square is reserved for a starting Barricade.";
  }

  const significantCenter = significantCenterSquares(
    draft.boardRows,
    draft.boardCols,
    {
      victoryMode: draft.victory?.mode,
      affinityEnabled: Boolean(draft.customRules?.affinityEnabled),
      affinitySquareCount: draft.customRules?.affinitySquareCount ?? 4,
    }
  ).some((square) => occupies(square, row, col));
  if (significantCenter && tool.type !== "barricade") {
    return "Rule-significant center squares must start empty except for Barricades.";
  }

  if (
    tool.type === "pawn"
    && (
      (tool.color === "white" && row === 0)
      || (tool.color === "black" && row === draft.boardRows - 1)
    )
  ) {
    return "Pawns cannot begin on the opponent-side promotion rank.";
  }

  if (tool.type === "king") {
    const otherPieces = (draft.placements || []).filter(
      (piece) => !occupies(piece, row, col)
    );
    if (otherPieces.some((piece) => (
      piece.type === "king" && piece.color === tool.color
    ))) {
      return `Erase the current ${tool.color === "white" ? "White" : "Black"} King before placing another.`;
    }
    if (otherPieces.some((piece) => (
      piece.type === "king"
      && piece.color !== tool.color
      && piece.color !== "neutral"
      && Math.max(Math.abs(piece.row - row), Math.abs(piece.col - col)) <= 1
    ))) {
      return "The two Kings cannot begin on touching squares.";
    }
  }

  return "";
}
