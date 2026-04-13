function PieceTooltip({ piece }) {
  if (!piece) {
    return null;
  }

  const customRules =
    piece.customAttributes?.customRules ||
    piece.customAttributes?.rules ||
    [];

  return (
    <div className="piece-tooltip" role="tooltip">
      <strong>{piece.name}</strong>
      <span>Color: {piece.color}</span>
      <span>Points: {piece.points ?? "-"}</span>
      {customRules.length ? (
        <span>Custom rules: {customRules.join(", ")}</span>
      ) : (
        <span>Custom rules: none</span>
      )}
    </div>
  );
}

function ChessBoard({
  board,
  boardSize,
  selectedSquare,
  validMoves,
  lastMove,
  onSquareClick,
  boardFlipped,
}) {
  const activeTargets = validMoves
    .filter(
      (move) =>
        selectedSquare &&
        move.from.row === selectedSquare.row &&
        move.from.col === selectedSquare.col
    )
    .map((move) => `${move.to.row}-${move.to.col}`);

  const activeTargetSet = new Set(activeTargets);

  return (
    <div className="board-wrap">
      <div
        className="board-grid"
        style={{
          gridTemplateColumns: `repeat(${boardSize}, minmax(38px, 1fr))`,
          gridTemplateRows: `repeat(${boardSize}, minmax(38px, 1fr))`,
        }}
      >
        {Array.from({ length: boardSize }).map((_, visibleRowIndex) =>
          Array.from({ length: boardSize }).map((__, visibleColIndex) => {
            const rowIndex = boardFlipped ? boardSize - 1 - visibleRowIndex : visibleRowIndex;
            const colIndex = boardFlipped ? boardSize - 1 - visibleColIndex : visibleColIndex;

            const piece = board[rowIndex][colIndex];
            const key = `${visibleRowIndex}-${visibleColIndex}`;
            const isLight = (rowIndex + colIndex) % 2 === 0;
            const isSelected =
              selectedSquare?.row === rowIndex && selectedSquare?.col === colIndex;
            const isValidTarget = activeTargetSet.has(`${rowIndex}-${colIndex}`);
            const isLastMoveSquare =
              lastMove &&
              ((lastMove.from.row === rowIndex && lastMove.from.col === colIndex) ||
                (lastMove.to.row === rowIndex && lastMove.to.col === colIndex));

            const className = [
              "square",
              isLight ? "light" : "dark",
              isSelected ? "selected" : "",
              isValidTarget ? "valid-target" : "",
              isLastMoveSquare ? "last-move" : "",
              piece?.isCustom ? "custom-square" : "",
            ]
              .filter(Boolean)
              .join(" ");

            const pieceClassName = [
              piece ? "piece" : "piece ghost",
              piece?.isCustom ? "custom-piece" : "default-piece",
            ]
              .filter(Boolean)
              .join(" ");

            return (
              <button
                type="button"
                key={key}
                className={className}
                onClick={() => onSquareClick(rowIndex, colIndex)}
              >
                <span className={pieceClassName}>{piece?.symbol || ""}</span>
                {isValidTarget ? <span className="move-dot" /> : null}
                {piece ? <PieceTooltip piece={piece} /> : null}
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}

export default ChessBoard;
