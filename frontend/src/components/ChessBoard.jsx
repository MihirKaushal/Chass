function PieceTooltip({ piece, placement = "above", edge = "center" }) {
  if (!piece) {
    return null;
  }

  const customRules =
    piece.customAttributes?.customRules ||
    piece.customAttributes?.rules ||
    [];

  return (
    <div
      className={`piece-tooltip piece-tooltip--${placement} piece-tooltip--${edge}`}
      role="tooltip"
    >
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
  boardRows,
  boardCols,
  boardSize,
  selectedSquare,
  validMoves,
  lastMove,
  onSquareClick,
  boardFlipped,
}) {
  const rows = boardRows ?? boardSize ?? board.length;
  const cols = boardCols ?? boardSize ?? (board[0] ? board[0].length : 0);

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
    <div
      className="board-wrap"
      style={{
        aspectRatio: `${cols} / ${rows}`,
      }}
    >
      <div
        className="board-grid"
        style={{
          gridTemplateColumns: `repeat(${cols}, minmax(38px, 1fr))`,
          gridTemplateRows: `repeat(${rows}, minmax(38px, 1fr))`,
        }}
      >
        {Array.from({ length: rows }).map((_, visibleRowIndex) =>
          Array.from({ length: cols }).map((__, visibleColIndex) => {
            const rowIndex = boardFlipped ? rows - 1 - visibleRowIndex : visibleRowIndex;
            const colIndex = boardFlipped ? cols - 1 - visibleColIndex : visibleColIndex;

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

            const tooltipPlacement = rowIndex === 0 ? "below" : "above";
            const tooltipEdge =
              colIndex === 0 ? "left" : colIndex === cols - 1 ? "right" : "center";

            return (
              <button
                type="button"
                key={key}
                className={className}
                onClick={() => onSquareClick(rowIndex, colIndex)}
              >
                <span className={pieceClassName}>{piece?.symbol || ""}</span>
                {isValidTarget ? <span className="move-dot" /> : null}
                {piece ? (
                  <PieceTooltip
                    piece={piece}
                    placement={tooltipPlacement}
                    edge={tooltipEdge}
                  />
                ) : null}
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}

export default ChessBoard;
