// The rules engine reports check on the side to move and checkmate with a winner,
// so the threatened King belongs to the side to move or to the losing side.
export function checkedKingColor(game) {
  if (!game) return null;
  if (game.gameStatus === "check") return game.currentPlayer || null;
  if (game.gameStatus === "checkmate" && ["white", "black"].includes(game.winner)) {
    return game.winner === "white" ? "black" : "white";
  }
  return null;
}
