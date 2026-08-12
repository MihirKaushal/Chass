function PieceTooltip({ piece, placement = "above", edge = "center" }) {
  if (!piece) {
    return null;
  }

  const customRules =
    piece.customAttributes?.customRules ||
    piece.customAttributes?.rules ||
    [];
  const runtimeItems = [];
  if (piece.runtime?.catapult_ready_turn_remaining > 0) {
    runtimeItems.push(`Projectile ready in ${piece.runtime.catapult_ready_turn_remaining} own turn(s)`);
  }
  if (piece.runtime?.pacified_until_turn_remaining > 0) {
    runtimeItems.push(`Pacified for ${piece.runtime.pacified_until_turn_remaining} more own turn(s)`);
  }
  if (piece.runtime?.love_until_turn_remaining > 0) {
    runtimeItems.push(`Queen mobility for ${piece.runtime.love_until_turn_remaining} more own turn(s)`);
  }
  if (piece.runtime?.recruit_target_name) {
    runtimeItems.push(
      `Recruiting ${piece.runtime.recruit_target_name}: ${piece.runtime.recruit_progress || 0}/${piece.runtime.recruit_threshold || "?"}`
    );
  }
  if (piece.runtime?.pacifications) {
    runtimeItems.push(`Diplomat pacifications: ${piece.runtime.pacifications}/5`);
  }
  if (piece.runtime?.episcopal_ready_turn_remaining > 0) {
    runtimeItems.push(`Episcopal ready in ${piece.runtime.episcopal_ready_turn_remaining} own turn(s)`);
  }
  (piece.runtime?.diplomat_contacts_status || []).forEach((contact) => {
    runtimeItems.push(
      `Contact with ${contact.targetName}: ${contact.progress}/${contact.required}`
    );
  });

  return (
    <div
      className={`piece-tooltip piece-tooltip--${placement} piece-tooltip--${edge}`}
      role="tooltip"
    >
      <div className="tooltip-title"><i>{piece.icon}</i><strong>{piece.name}</strong></div>
      <span>Color: {piece.color}</span>
      <span>Points: {piece.points ?? 0}</span>
      {piece.description ? <p><b>Role</b>{piece.description}</p> : null}
      {piece.movement ? <p><b>Movement</b>{piece.movement}</p> : null}
      {customRules.length ? (
        <p><b>Special Rules</b>{customRules.join(" · ")}</p>
      ) : (
        <span>Special rules: none</span>
      )}
      {runtimeItems.length ? (
        <div className="tooltip-runtime"><b>Live Status</b>{runtimeItems.map((item) => <span key={item}>{item}</span>)}</div>
      ) : null}
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
  interactive = true,
  extraTargets = [],
  affinitySquares = {},
  editableRows = [],
  foggedRows = [],
  showCoordinates = false,
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
  const extraTargetSet = new Set(
    extraTargets.map((target) => `${target.row}-${target.col}`)
  );
  const affinityMap = new Map();
  Object.entries(affinitySquares).forEach(([color, squares]) => {
    squares.forEach((square) => affinityMap.set(`${square.row}-${square.col}`, color));
  });
  const editableRowSet = new Set(editableRows);
  const foggedRowSet = new Set(foggedRows);

  return (
    <div
      className="board-wrap"
      style={{
        aspectRatio: `${cols} / ${rows}`,
        width: `min(85vw, calc(74vh * ${cols / rows}), 820px)`,
        "--piece-size": `${Math.max(0.72, Math.min(2.1, 18 / cols))}rem`,
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

            const tooltipPlacement = visibleRowIndex === 0 ? "below" : "above";
            const tooltipEdge =
              visibleColIndex === 0
                ? "left"
                : visibleColIndex === cols - 1
                  ? "right"
                  : "center";

            return (
              <button
                type="button"
                key={key}
                className={className}
                onClick={() => interactive && onSquareClick(rowIndex, colIndex)}
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
                <span className={pieceClassName}>{piece?.symbol || ""}</span>
                {isValidTarget ? <span className="move-dot" /> : null}
                {isExtraTarget ? <span className="command-target-ring" /> : null}
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
