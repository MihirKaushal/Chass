import { useEffect, useRef, useState } from "react";

import PieceGlyph from "./PieceGlyph";
import PieceTooltip from "./PieceTooltip";

const DOUBLE_TAP_WINDOW_MS = 500;

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
  objectiveSquares = [],
  editableRows = [],
  foggedRows = [],
  showCoordinates = false,
  pieceDetailsMode = "hover",
}) {
  const [hoveredPiece, setHoveredPiece] = useState(null);
  const pendingPieceTapRef = useRef(null);
  const onSquareClickRef = useRef(onSquareClick);
  onSquareClickRef.current = onSquareClick;
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
  const objectiveSquareSet = new Set(
    objectiveSquares.map((square) => `${square.row}-${square.col}`)
  );
  const editableRowSet = new Set(editableRows);
  const foggedRowSet = new Set(foggedRows);
  const longEdge = "var(--board-long-edge, min(68vh, 680px))";
  const boardWidth = cols >= rows ? longEdge : `calc(${longEdge} * ${cols / rows})`;
  const boardHeight = rows >= cols ? longEdge : `calc(${longEdge} * ${rows / cols})`;

  useEffect(() => {
    if (pendingPieceTapRef.current) {
      window.clearTimeout(pendingPieceTapRef.current.timer);
      pendingPieceTapRef.current = null;
    }
    setHoveredPiece(null);
  }, [board, boardFlipped]);

  useEffect(() => () => {
    if (pendingPieceTapRef.current) {
      window.clearTimeout(pendingPieceTapRef.current.timer);
    }
  }, []);

  const activateSquare = (row, col) => {
    setHoveredPiece(null);
    onSquareClickRef.current(row, col);
  };

  const showPieceDetails = (squareKey, details) => {
    const pending = pendingPieceTapRef.current;
    if (pending) {
      window.clearTimeout(pending.timer);
      pendingPieceTapRef.current = null;
    }
    setHoveredPiece({ ...details, key: squareKey });
  };

  const handleSquareClick = (row, col, piece, details, clickCount) => {
    if (!interactive) return;
    if (pieceDetailsMode !== "double-tap" || !piece) {
      const pending = pendingPieceTapRef.current;
      if (pending) {
        window.clearTimeout(pending.timer);
        pendingPieceTapRef.current = null;
        activateSquare(pending.row, pending.col);
        window.setTimeout(() => activateSquare(row, col), 0);
      } else {
        activateSquare(row, col);
      }
      return;
    }

    const squareKey = `${row}-${col}`;
    const pending = pendingPieceTapRef.current;
    if (clickCount >= 2 || pending?.key === squareKey) {
      showPieceDetails(squareKey, details);
      return;
    }
    if (pending) {
      window.clearTimeout(pending.timer);
      pendingPieceTapRef.current = null;
      activateSquare(pending.row, pending.col);
    }

    setHoveredPiece(null);
    const timer = window.setTimeout(() => {
      if (pendingPieceTapRef.current?.timer !== timer) return;
      pendingPieceTapRef.current = null;
      activateSquare(row, col);
    }, DOUBLE_TAP_WINDOW_MS);
    pendingPieceTapRef.current = { key: squareKey, row, col, timer };
  };

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
            const isObjectiveSquare = objectiveSquareSet.has(`${rowIndex}-${colIndex}`);
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
              isObjectiveSquare ? "objective-square" : "",
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
                onClick={(event) => handleSquareClick(rowIndex, colIndex, piece, { piece, visibleRowIndex, visibleColIndex, tooltipPlacement, tooltipEdge }, event.detail)}
                onDoubleClick={(event) => {
                  if (pieceDetailsMode !== "double-tap" || !piece) return;
                  event.preventDefault();
                  showPieceDetails(`${rowIndex}-${colIndex}`, { piece, visibleRowIndex, visibleColIndex, tooltipPlacement, tooltipEdge });
                }}
                onMouseEnter={() => pieceDetailsMode === "hover" && piece && setHoveredPiece({ piece, visibleRowIndex, visibleColIndex, tooltipPlacement, tooltipEdge })}
                onMouseLeave={() => pieceDetailsMode === "hover" && setHoveredPiece(null)}
                onFocus={() => pieceDetailsMode === "hover" && piece && setHoveredPiece({ piece, visibleRowIndex, visibleColIndex, tooltipPlacement, tooltipEdge })}
                onBlur={() => pieceDetailsMode === "hover" && setHoveredPiece(null)}
                aria-disabled={!interactive}
                aria-label={`${String.fromCharCode(97 + colIndex)}${rows - rowIndex}${
                  piece ? `, ${piece.color} ${piece.name}` : ""
                }${piece && pieceDetailsMode === "double-tap" ? ", double tap for details" : ""}`}
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
                {isObjectiveSquare ? (
                  <span className="objective-marker" aria-hidden="true">C</span>
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
            onClose={pieceDetailsMode === "double-tap" ? () => setHoveredPiece(null) : null}
          />
        </div>
      ) : null}
    </div>
  );
}

export default ChessBoard;
