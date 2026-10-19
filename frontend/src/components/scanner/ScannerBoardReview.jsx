import { useState } from "react";

import ChessBoard from "../ChessBoard";
import PieceGlyph from "../PieceGlyph";
import Button from "../ui/Button";
import ScannerIcon from "./ScannerIcon";
import { SCANNER_PIECES } from "./scannerPreview";

function ScannerBoardReview({
  board,
  reviewSquares,
  onSquareEdit,
  onReviewSquare,
  onUndo,
  canUndo,
  onReset,
}) {
  const [flipped, setFlipped] = useState(false);
  const [tool, setTool] = useState(null);
  const [selectedSquare, setSelectedSquare] = useState(null);
  const selectedLabel = selectedSquare
    ? `${String.fromCharCode(97 + selectedSquare.col)}${8 - selectedSquare.row}`
    : "";
  const selectedNeedsReview =
    selectedSquare &&
    reviewSquares.some(
      (square) =>
        square.row === selectedSquare.row && square.col === selectedSquare.col,
    );

  const selectSquare = (row, col) => {
    setSelectedSquare({ row, col });
    if (tool) onSquareEdit(row, col, tool);
  };

  return (
    <section
      className="scanner-panel scanner-review-panel"
      aria-labelledby="scanner-review-title"
    >
      <header className="scanner-panel-header">
        <div>
          <span className="scanner-overline">Check every square</span>
          <h2 id="scanner-review-title">Review the position</h2>
        </div>
        <span className="scanner-step-label">02</span>
      </header>
      <div className="scanner-board-toolbar">
        <span className="scanner-example-badge">Example position</span>
        <Button
          variant="text"
          size="small"
          onClick={() => setFlipped((current) => !current)}
        >
          <ScannerIcon name="rotate" />
          Flip Board
        </Button>
      </div>
      <div className="scanner-review-board">
        <ChessBoard
          board={board}
          boardRows={8}
          boardCols={8}
          selectedSquare={selectedSquare}
          validMoves={[]}
          boardFlipped={flipped}
          onSquareClick={selectSquare}
          showCoordinates
          pieceDetailsMode="none"
          extraTargets={reviewSquares}
        />
      </div>
      <div
        className={`scanner-review-status${reviewSquares.length ? " has-review" : ""}`}
      >
        <span className="scanner-review-status-icon">
          <ScannerIcon name={reviewSquares.length ? "info" : "check"} />
        </span>
        <div>
          <strong>
            {reviewSquares.length
              ? `${reviewSquares.length} example ${reviewSquares.length === 1 ? "square" : "squares"} to review`
              : "Example squares reviewed"}
          </strong>
          <small>
            {reviewSquares.length
              ? "Gold markers show how uncertain squares will appear."
              : "You can still edit any square using the pieces below."}
          </small>
        </div>
        {reviewSquares.length ? (
          <Button
            size="small"
            variant="text"
            onClick={() => {
              setTool(null);
              setSelectedSquare(reviewSquares[0]);
            }}
          >
            Review {reviewSquares[0].label}
          </Button>
        ) : null}
      </div>
      <div className="scanner-piece-editor">
        <div className="scanner-editor-heading">
          <h3>Correct a piece</h3>
          <span>Choose a piece, then a square.</span>
        </div>
        <div className="scanner-piece-palette">
          {["white", "black"].map((color) => (
            <fieldset className="scanner-palette-row" key={color}>
              <legend>{color === "white" ? "White" : "Black"}</legend>
              {SCANNER_PIECES.map((piece) => (
                <button
                  key={piece.type}
                  type="button"
                  className={`scanner-palette-piece${tool?.type === piece.type && tool.color === color ? " is-selected" : ""}`}
                  aria-label={`Place ${color} ${piece.name.toLowerCase()}`}
                  aria-pressed={
                    tool?.type === piece.type && tool.color === color
                  }
                  title={`${color === "white" ? "White" : "Black"} ${piece.name}`}
                  onClick={() => setTool({ type: piece.type, color })}
                >
                  <PieceGlyph
                    type={piece.type}
                    color={color}
                    symbol={piece.symbols[color]}
                  />
                </button>
              ))}
            </fieldset>
          ))}
        </div>
        <div className="scanner-editor-actions">
          <Button
            variant="secondary"
            size="small"
            disabled={!canUndo}
            onClick={onUndo}
          >
            <ScannerIcon name="undo" />
            Undo
          </Button>
          <Button
            variant="secondary"
            size="small"
            aria-pressed={tool?.type === "erase"}
            className={tool?.type === "erase" ? "is-selected" : ""}
            onClick={() =>
              setTool((current) =>
                current?.type === "erase" ? null : { type: "erase" },
              )
            }
          >
            <ScannerIcon name="eraser" />
            Eraser
          </Button>
          <Button
            variant="text"
            size="small"
            onClick={() => {
              onReset();
              setSelectedSquare(null);
              setTool(null);
            }}
          >
            Reset Example
          </Button>
        </div>
        <div className="scanner-selected-square" aria-live="polite">
          <span>
            {tool
              ? tool.type === "erase"
                ? "Eraser selected. Click a square to remove its piece."
                : `${tool.color === "white" ? "White" : "Black"} ${tool.type} selected. Click a square to place it.`
              : selectedLabel
                ? `${selectedLabel} selected. Choose a replacement above, then click the square.`
                : "Click a square to inspect it, or choose a piece to start editing."}
          </span>
          {selectedNeedsReview ? (
            <Button
              variant="text"
              size="small"
              onClick={() => onReviewSquare(selectedSquare)}
            >
              Mark {selectedLabel} Correct
              <ScannerIcon name="check" />
            </Button>
          ) : null}
        </div>
      </div>
    </section>
  );
}

export default ScannerBoardReview;
