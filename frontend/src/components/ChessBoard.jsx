import { useEffect, useMemo, useRef, useState } from "react";

import { boardFileLabel, boardSquareLabel } from "../boardGeometry";
import { boardActionsWithStandardMovePriority } from "../specialActionSelection";
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
  availableActions = [],
  onAction = null,
  onActionSelectionChange = null,
  countdowns = [],
  terrain = [],
  globalActions = [],
}) {
  const [hoveredPiece, setHoveredPiece] = useState(null);
  const [selectedActionSource, setSelectedActionSource] = useState(null);
  const pendingPieceTapRef = useRef(null);
  const onSquareClickRef = useRef(onSquareClick);
  const onActionRef = useRef(onAction);
  const onActionSelectionChangeRef = useRef(onActionSelectionChange);
  const actionsBySourceRef = useRef(new Map());
  const selectedSourceActionsRef = useRef([]);
  const globalActionMapRef = useRef(new Map());
  onSquareClickRef.current = onSquareClick;
  onActionRef.current = onAction;
  onActionSelectionChangeRef.current = onActionSelectionChange;
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
  const standardTargetsBySource = useMemo(() => {
    const grouped = new Map();
    validMoves.forEach((move) => {
      const sourceKey = `${move.from.row}-${move.from.col}`;
      const targets = grouped.get(sourceKey) || new Set();
      targets.add(`${move.to.row}-${move.to.col}`);
      grouped.set(sourceKey, targets);
    });
    return grouped;
  }, [validMoves]);
  const actionsBySource = useMemo(() => {
    const grouped = new Map();
    availableActions.forEach((action) => {
      if (!action.source || !action.target) return;
      const key = `${action.source.row}-${action.source.col}`;
      grouped.set(key, [...(grouped.get(key) || []), action]);
    });
    return new Map(
      [...grouped.entries()]
        .map(([sourceKey, actions]) => [
          sourceKey,
          boardActionsWithStandardMovePriority(
            actions,
            standardTargetsBySource.get(sourceKey) || new Set()
          ),
        ])
        .filter(([, actions]) => actions.length)
    );
  }, [availableActions, standardTargetsBySource]);
  const selectedActionSourceKey = selectedActionSource
    ? `${selectedActionSource.row}-${selectedActionSource.col}`
    : "";
  const selectedSourceActions = actionsBySource.get(selectedActionSourceKey) || [];
  actionsBySourceRef.current = actionsBySource;
  selectedSourceActionsRef.current = selectedSourceActions;
  const actionTargetMap = new Map();
  const globalActionMap = useMemo(
    () => new Map(
      globalActions
        .filter((action) => action.target)
        .map((action) => [`${action.target.row}-${action.target.col}`, action])
    ),
    [globalActions]
  );
  globalActionMapRef.current = globalActionMap;
  globalActionMap.forEach((action, key) => actionTargetMap.set(key, action));
  selectedSourceActions.forEach((action) => {
    actionTargetMap.set(`${action.target.row}-${action.target.col}`, action);
  });
  const effectsByPiece = useMemo(() => {
    const grouped = new Map();
    const addEffect = (pieceId, effect, role) => {
      if (!pieceId) return;
      grouped.set(pieceId, [...(grouped.get(pieceId) || []), { ...effect, role }]);
    };
    countdowns.forEach((effect) => {
      addEffect(effect.pieceId, effect, "source");
      if (effect.targetPieceId && effect.targetPieceId !== effect.pieceId) {
        addEffect(effect.targetPieceId, effect, "target");
      }
    });
    return grouped;
  }, [countdowns]);
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
  const terrainMap = new Map(
    terrain.map((feature) => [`${feature.row}-${feature.col}`, feature])
  );
  const longEdge = "var(--board-long-edge, min(68vh, 680px))";
  const boardWidth = cols >= rows ? longEdge : `calc(${longEdge} * ${cols / rows})`;
  const boardHeight = rows >= cols ? longEdge : `calc(${longEdge} * ${rows / cols})`;
  const visibleRows = Array.from(
    { length: rows },
    (_, index) => boardFlipped ? rows - 1 - index : index
  );
  const visibleCols = Array.from(
    { length: cols },
    (_, index) => boardFlipped ? cols - 1 - index : index
  );

  useEffect(() => {
    if (pendingPieceTapRef.current) {
      window.clearTimeout(pendingPieceTapRef.current.timer);
      pendingPieceTapRef.current = null;
    }
    setHoveredPiece(null);
    setSelectedActionSource(null);
    onActionSelectionChangeRef.current?.(null);
  }, [board, boardFlipped]);

  useEffect(() => {
    if (!selectedActionSource) return;
    const key = `${selectedActionSource.row}-${selectedActionSource.col}`;
    if (actionsBySource.has(key)) return;
    setSelectedActionSource(null);
    onActionSelectionChangeRef.current?.(null);
  }, [actionsBySource, selectedActionSource]);

  useEffect(() => () => {
    if (pendingPieceTapRef.current) {
      window.clearTimeout(pendingPieceTapRef.current.timer);
    }
  }, []);

  const activateSquare = (row, col) => {
    setHoveredPiece(null);
    const globalAction = globalActionMapRef.current.get(`${row}-${col}`);
    if (globalAction && onActionRef.current) {
      setSelectedActionSource(null);
      onActionSelectionChangeRef.current?.(null);
      onActionRef.current(globalAction);
      return;
    }
    const targetAction = selectedSourceActionsRef.current.find(
      (action) => action.target.row === row && action.target.col === col
    );
    if (targetAction && onActionRef.current) {
      setSelectedActionSource(null);
      onActionSelectionChangeRef.current?.(null);
      onActionRef.current(targetAction);
      return;
    }

    const sourceKey = `${row}-${col}`;
    const sourceActions = actionsBySourceRef.current.get(sourceKey) || [];
    if (sourceActions.length) {
      const nextSource = selectedActionSource?.row === row && selectedActionSource?.col === col
        ? null
        : { row, col };
      setSelectedActionSource(nextSource);
      onActionSelectionChangeRef.current?.(
        nextSource ? { source: nextSource, actions: sourceActions } : null
      );
    } else {
      setSelectedActionSource(null);
      onActionSelectionChangeRef.current?.(null);
    }
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
      {showCoordinates ? (
        <div className="board-coordinate-frame" aria-hidden="true">
          <div
            className="board-files board-files-top"
            style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}
          >
            {visibleCols.map((col) => <span key={col}>{boardFileLabel(col)}</span>)}
          </div>
          <div
            className="board-files board-files-bottom"
            style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}
          >
            {visibleCols.map((col) => <span key={col}>{boardFileLabel(col)}</span>)}
          </div>
          <div
            className="board-ranks board-ranks-left"
            style={{ gridTemplateRows: `repeat(${rows}, minmax(0, 1fr))` }}
          >
            {visibleRows.map((row) => <span key={row}>{rows - row}</span>)}
          </div>
          <div
            className="board-ranks board-ranks-right"
            style={{ gridTemplateRows: `repeat(${rows}, minmax(0, 1fr))` }}
          >
            {visibleRows.map((row) => <span key={row}>{rows - row}</span>)}
          </div>
        </div>
      ) : null}
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
            const terrainFeature = terrainMap.get(`${rowIndex}-${colIndex}`);
            const key = `${visibleRowIndex}-${visibleColIndex}`;
            const isLight = (rowIndex + colIndex) % 2 === 0;
            const isSelected =
              (selectedSquare?.row === rowIndex && selectedSquare?.col === colIndex) ||
              (selectedActionSource?.row === rowIndex && selectedActionSource?.col === colIndex);
            const isValidTarget = activeTargetSet.has(`${rowIndex}-${colIndex}`);
            const isExtraTarget = extraTargetSet.has(`${rowIndex}-${colIndex}`);
            const actionTarget = actionTargetMap.get(`${rowIndex}-${colIndex}`);
            const pieceEffects = piece ? effectsByPiece.get(piece.pieceId) || [] : [];
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
              actionTarget ? `board-action-target action-${actionTarget.boardMarker}` : "",
              pieceEffects.some((effect) => effect.kind === "pacified")
                ? "has-pacified-effect"
                : "",
              pieceEffects.some(
                (effect) => effect.kind === "recruitment" && effect.role === "target"
              )
                ? "has-recruitment-effect"
                : "",
              selectedActionSource?.row === rowIndex && selectedActionSource?.col === colIndex
                ? "action-source-selected"
                : "",
              isLastMoveSquare ? "last-move" : "",
              affinityColor ? `affinity-square affinity-${affinityColor}` : "",
              isObjectiveSquare ? "objective-square" : "",
              editableRowSet.has(rowIndex) ? "deployment-zone" : "",
              foggedRowSet.has(rowIndex) ? "fogged-square" : "",
              piece?.isCustom ? "custom-square" : "",
              terrainFeature?.kind === "scorched" ? "scorched-square" : "",
              !interactive ? "readonly" : "",
            ]
              .filter(Boolean)
              .join(" ");

            const pieceClassName = [
              piece ? "piece" : "piece ghost",
              piece?.isCustom ? "custom-piece" : "default-piece",
              piece ? `piece-${piece.color}` : "",
              piece?.isOptimistic ? "piece-optimistic" : "",
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
                aria-label={`${boardSquareLabel({ row: rowIndex, col: colIndex }, rows)}${
                  piece ? `, ${piece.color} ${piece.name}` : ""
                }${terrainFeature?.kind === "scorched" ? ", scorched and impassable" : ""}${
                  actionTarget ? `, ${actionTarget.label}` : ""}${
                  piece && pieceDetailsMode === "double-tap" ? ", double tap for details" : ""
                }`}
              >
                {terrainFeature?.kind === "scorched" ? (
                  <span className="terrain-marker terrain-scorched" aria-hidden="true">♨</span>
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
                {pieceEffects.length ? (
                  <span className="board-effect-stack" aria-label="Active piece effects">
                    {pieceEffects.map((effect) => (
                      <span
                        className={`board-effect-badge effect-${effect.kind} effect-${effect.role}`}
                        key={`${effect.id}-${effect.role}`}
                        title={`${effect.label}: ${effect.description}`}
                      >
                        <i>{effect.icon}</i>
                        <small>{effect.remainingTurns}</small>
                      </span>
                    ))}
                  </span>
                ) : null}
                {isValidTarget ? <span className="move-dot" /> : null}
                {isExtraTarget ? <span className="command-target-ring" /> : null}
                {actionTarget ? (
                  <span
                    className={`board-action-marker marker-${actionTarget.boardMarker}`}
                    title={actionTarget.label}
                    aria-hidden="true"
                  >
                    <i>{actionTarget.icon}</i>
                  </span>
                ) : null}
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
