import { useEffect, useState } from "react";

import PieceGlyph from "./PieceGlyph";
import PieceTooltip from "./PieceTooltip";

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
  interactive = true,
  extraTargets = [],
  affinitySquares = {},
  editableRows = [],
  foggedRows = [],
  showCoordinates = false,
}) {
  const [hoveredPiece, setHoveredPiece] = useState(null);
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
  const extraTargetSet = new Set(
    extraTargets.map((target) => `${target.row}-${target.col}`)
  );
  const affinityMap = new Map();
  Object.entries(affinitySquares).forEach(([color, squares]) => {
    squares.forEach((square) => affinityMap.set(`${square.row}-${square.col}`, color));
  });
  const editableRowSet = new Set(editableRows);
  const foggedRowSet = new Set(foggedRows);
  const longEdge = "var(--board-long-edge, min(68vh, 680px))";
  const boardWidth = cols >= rows ? longEdge : `calc(${longEdge} * ${cols / rows})`;
  const boardHeight = rows >= cols ? longEdge : `calc(${longEdge} * ${rows / cols})`;

  useEffect(() => {
    setHoveredPiece(null);
  }, [board, boardFlipped]);

  return (
    <div
      className="board-wrap"
      style={{
        width: boardWidth,
        height: boardHeight,
        "--piece-size": `${Math.max(0.58, Math.min(2.35, 18 / Math.max(rows, cols)))}rem`,
      }}
    >
      <div
        className="board-grid"
        style={{
          gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`,
          gridTemplateRows: `repeat(${rows}, minmax(0, 1fr))`,
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
            const isExtraTarget = extraTargetSet.has(`${rowIndex}-${colIndex}`);
            const affinityColor = affinityMap.get(`${rowIndex}-${colIndex}`);
            const isLastMoveSquare =
              lastMove &&
              ((lastMove.from.row === rowIndex && lastMove.from.col === colIndex) ||
                (lastMove.to.row === rowIndex && lastMove.to.col === colIndex));

            const className = [
              "square",
              isLight ? "light" : "dark",
              isSelected ? "selected" : "",
              isValidTarget ? "valid-target" : "",
              isExtraTarget ? "command-target" : "",
              isLastMoveSquare ? "last-move" : "",
              affinityColor ? `affinity-square affinity-${affinityColor}` : "",
              editableRowSet.has(rowIndex) ? "deployment-zone" : "",
              foggedRowSet.has(rowIndex) ? "fogged-square" : "",
              piece?.isCustom ? "custom-square" : "",
              !interactive ? "readonly" : "",
            ]
              .filter(Boolean)
              .join(" ");

            const pieceClassName = [
              piece ? "piece" : "piece ghost",
              piece?.isCustom ? "custom-piece" : "default-piece",
              piece ? `piece-${piece.color}` : "",
            ]
              .filter(Boolean)
              .join(" ");

            const tooltipPlacement = visibleRowIndex < rows / 2 ? "below" : "above";
            const tooltipEdge =
              visibleColIndex < cols / 3
                ? "left"
                : visibleColIndex >= (cols * 2) / 3
                  ? "right"
                  : "center";

            return (
              <button
                type="button"
                key={key}
                className={className}
                onClick={() => interactive && onSquareClick(rowIndex, colIndex)}
                onMouseEnter={() => piece && setHoveredPiece({ piece, visibleRowIndex, visibleColIndex, tooltipPlacement, tooltipEdge })}
                onMouseLeave={() => setHoveredPiece(null)}
                onFocus={() => piece && setHoveredPiece({ piece, visibleRowIndex, visibleColIndex, tooltipPlacement, tooltipEdge })}
                onBlur={() => setHoveredPiece(null)}
                aria-disabled={!interactive}
                aria-label={`${String.fromCharCode(97 + colIndex)}${rows - rowIndex}${
                  piece ? `, ${piece.color} ${piece.name}` : ""
                }`}
              >
                {showCoordinates && visibleColIndex === 0 ? (
                  <span className="board-coordinate board-rank">{rows - rowIndex}</span>
                ) : null}
                {showCoordinates && visibleRowIndex === rows - 1 ? (
                  <span className="board-coordinate board-file">
                    {String.fromCharCode(97 + colIndex)}
                  </span>
                ) : null}
                {affinityColor ? (
                  <span className="affinity-marker" aria-hidden="true">
                    {affinityColor === "white" ? "W" : "B"}
                  </span>
                ) : null}
                <span className={pieceClassName}>
                  {piece ? <PieceGlyph piece={piece} /> : null}
                </span>
                {isValidTarget ? <span className="move-dot" /> : null}
                {isExtraTarget ? <span className="command-target-ring" /> : null}
              </button>
            );
          })
        )}
      </div>
      {hoveredPiece ? (
        <div
          className="board-tooltip-anchor"
          style={{
            top: `${(hoveredPiece.visibleRowIndex / rows) * 100}%`,
            left: `${(hoveredPiece.visibleColIndex / cols) * 100}%`,
            width: `${100 / cols}%`,
            height: `${100 / rows}%`,
          }}
        >
          <PieceTooltip
            piece={hoveredPiece.piece}
            placement={hoveredPiece.tooltipPlacement}
            edge={hoveredPiece.tooltipEdge}
          />
        </div>
      ) : null}
    </div>
  );
}

export default ChessBoard;
