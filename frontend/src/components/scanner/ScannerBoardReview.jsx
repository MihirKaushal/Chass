import { useState } from "react";

import ChessBoard from "../ChessBoard";
import PieceGlyph from "../PieceGlyph";
import Button from "../ui/Button";
import ScannerIcon from "./ScannerIcon";
import { SCANNER_PIECES } from "./scannerPreview";
import { squareAlternatives } from "../../scannerReview";

function ScannerBoardReview({
  board,
  reviewSquares,
  onSquareEdit,
  onReviewSquare,
  onUndo,
  canUndo,
  onReset,
  scan,
  issueSquares = [],
}) {
  const [flipped, setFlipped] = useState(false);
  const [tool, setTool] = useState(null);
  const [selectedSquare, setSelectedSquare] = useState(
    () => reviewSquares[0] || null,
  );
  const selectedLabel = selectedSquare
    ? `${String.fromCharCode(97 + selectedSquare.col)}${8 - selectedSquare.row}`
    : "";
  const selectedNeedsReview =
    selectedSquare &&
    reviewSquares.some(
      (square) =>
        square.row === selectedSquare.row && square.col === selectedSquare.col,
    );
  const alternatives = squareAlternatives(scan, selectedSquare);
  const review = reviewSquares.find(
    (square) =>
      square.row === selectedSquare?.row && square.col === selectedSquare?.col,
  );
  const chooseAlternative = (piece) => {
    onSquareEdit(selectedSquare.row, selectedSquare.col, piece);
    setTool(null);
  };

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
        <span className="scanner-example-badge">Scanned position</span>
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
          extraTargets={[...reviewSquares, ...issueSquares]}
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
              ? `${reviewSquares.length} ${reviewSquares.length === 1 ? "square" : "squares"} to review`
              : "Flagged squares reviewed"}
          </strong>
          <small>
            {reviewSquares.length
              ? "Gold markers flag uncertainty. Also check unmarked and empty squares for mistakes."
              : "Check every square, including empty ones. The model can miss pieces."}
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
      <div className="scanner-alternatives" aria-live="polite">
        <h3>
          {selectedLabel ? `Review ${selectedLabel}` : "Inspect a square"}
        </h3>
        {selectedSquare ? (
          <>
            {review?.reasons?.map((reason) => (
              <p key={reason}>{reason}</p>
            ))}
            {alternatives.length ? (
              <>
                <p>
                  Model suggestions. Choose the piece you see in the photo;
                  scores are not guaranteed accuracy.
                </p>
                <div className="scanner-alternative-options">
                  {alternatives.map((option) => (
                    <Button
                      key={option.label}
                      variant="secondary"
                      size="small"
                      onClick={() => chooseAlternative(option)}
                    >
                      <PieceGlyph
                        type={option.type}
                        color={option.color}
                        symbol={
                          SCANNER_PIECES.find(
                            (piece) => piece.type === option.type,
                          )?.symbols[option.color]
                        }
                      />
                      <span>
                        {option.color === "white" ? "White" : "Black"}{" "}
                        {option.type}
                      </span>
                      <small>{Math.round(option.score * 100)}%</small>
                    </Button>
                  ))}
                </div>
              </>
            ) : (
              <p>
                No model suggestions here. Use the piece palette below to add a
                missed piece.
              </p>
            )}
            <div className="scanner-review-choice-actions">
              <Button
                variant="secondary"
                size="small"
                onClick={() => chooseAlternative({ type: "erase" })}
              >
                This Square Is Empty
              </Button>
              {selectedNeedsReview ? (
                <Button
                  size="small"
                  onClick={() => onReviewSquare(selectedSquare)}
                >
                  Keep Current Piece
                </Button>
              ) : null}
            </div>
          </>
        ) : (
          <p>
            Gold squares need review. Click one to compare the model's top
            options, or choose any square to correct a missed piece.
          </p>
        )}
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
            Restore Scan
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
