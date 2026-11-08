import { useState } from "react";

import ChessBoard from "../ChessBoard";
import PieceGlyph from "../PieceGlyph";
import Button from "../ui/Button";
import ScannerIcon from "./ScannerIcon";
import { SCANNER_PIECES } from "./scannerPreview";
import { nextScannerReviewSquare, squareAlternatives } from "../../scannerReview";
import { ScannerSquareCrop } from "./ScannerPhotoEvidence";

function ScannerBoardReview({
  board,
  reviewSquares,
  onSquareEdit,
  onReviewSquare,
  onUndo,
  canUndo,
  onReset,
  scan,
  photoUrl,
  selectedSquare: controlledSquare,
  onSelectSquare,
  issueSquares = [],
}) {
  const [flipped, setFlipped] = useState(false);
  const [tool, setTool] = useState(null);
  const [localSquare, setLocalSquare] = useState(() => reviewSquares[0] || null);
  const selectedSquare = controlledSquare === undefined ? localSquare : controlledSquare;
  const setSelectedSquare = onSelectSquare || setLocalSquare;
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
  const currentPiece = selectedSquare ? board[selectedSquare.row][selectedSquare.col] : null;
  const isCurrentPiece = (piece) =>
    currentPiece?.type === piece.type && currentPiece?.color === piece.color;
  const choices = currentPiece && !alternatives.some(isCurrentPiece)
    ? [{ ...currentPiece, label: `${currentPiece.color}-${currentPiece.type}` }, ...alternatives]
    : alternatives;
  const review = reviewSquares.find(
    (square) =>
      square.row === selectedSquare?.row && square.col === selectedSquare?.col,
  );
  const chooseAlternative = (piece) => {
    onSquareEdit(selectedSquare.row, selectedSquare.col, piece);
    setSelectedSquare(nextScannerReviewSquare(reviewSquares, selectedSquare));
    setTool(null);
  };
  const markCorrect = () => {
    onReviewSquare(selectedSquare);
    setSelectedSquare(nextScannerReviewSquare(reviewSquares, selectedSquare));
    setTool(null);
  };

  const selectSquare = (row, col) => {
    setSelectedSquare({ row, col });
    if (tool) {
      onSquareEdit(row, col, tool);
      const target = { row, col };
      const next = nextScannerReviewSquare(reviewSquares, target);
      if (next !== target) {
        setSelectedSquare(next);
        setTool(null);
      }
    }
  };

  return (
    <section
      className="scanner-panel scanner-review-panel"
      aria-labelledby="scanner-review-title"
      onKeyDown={(event) => {
        if (event.key === "Escape") setTool(null);
      }}
    >
      <header className="scanner-panel-header">
        <h2 id="scanner-review-title">Review Pieces</h2>
      </header>
      <div className="scanner-board-toolbar">
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
          keyboardNavigation
          describedBy="scanner-keyboard-help"
          extraTargets={[...reviewSquares, ...issueSquares]}
        />
      </div>
      <p id="scanner-keyboard-help" className="scanner-keyboard-help">
        Arrow keys navigate. Enter selects or places a piece. Escape or clicking the selected piece again clears the editing tool.
      </p>
      <div
        className={`scanner-review-status${reviewSquares.length ? " has-review" : ""}`}
        role="status"
      >
        <span className="scanner-review-status-icon">
          <ScannerIcon name={reviewSquares.length ? "info" : "check"} />
        </span>
        <div>
          <strong>
            {reviewSquares.length
              ? `${reviewSquares.length} ${reviewSquares.length === 1 ? "square" : "squares"} to review`
              : "No more squares to review"}
          </strong>
          <small>
            {reviewSquares.length
              ? "Gold markers need review. Check unmarked and empty squares too."
              : "Recheck the entire board for missing pieces, wrong pieces, and incorrect colors, then confirm all 64 squares below."}
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
            <ScannerSquareCrop src={photoUrl} square={selectedSquare} />
            {review?.reasons?.map((reason) => (
              <p key={reason}>{reason}</p>
            ))}
            {choices.length ? (
              <>
                <p>
                  Choose the piece in your photo. Percentages are model scores, not calibrated probabilities.
                </p>
                <div className="scanner-alternative-options">
                  {choices.map((option) => (
                    <Button
                      key={option.label}
                      variant="secondary"
                      size="small"
                      className={isCurrentPiece(option) ? "is-current" : ""}
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
                      <span className="scanner-alternative-label">
                        {option.color === "white" ? "White" : "Black"}{" "}
                        {option.type}
                        {isCurrentPiece(option) ? <span className="scanner-current-label">(Current Piece)</span> : null}
                      </span>
                      {Number.isFinite(option.score) ? <small>{Math.round(option.score * 100)}%</small> : null}
                    </Button>
                  ))}
                </div>
              </>
            ) : (
              <p>
                No suggestions. Use the pieces below to make a correction.
              </p>
            )}
            <div className="scanner-review-choice-actions">
              <Button
                variant="secondary"
                size="small"
                onClick={() => chooseAlternative({ type: "erase" })}
              >
                This Square Is Empty{!currentPiece ? " (Current)" : ""}
              </Button>
              {selectedNeedsReview ? (
                <Button
                  size="small"
                  onClick={markCorrect}
                >
                  Mark {selectedLabel} Correct
                </Button>
              ) : null}
            </div>
          </>
        ) : (
          <p>
            Select a square to review or correct it.
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
                  onClick={() => setTool((current) =>
                    current?.type === piece.type && current.color === color
                      ? null
                      : { type: piece.type, color },
                  )}
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
            onClick={() => {
              setTool(null);
              onUndo();
            }}
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
              setSelectedSquare(scan?.reviewSquares?.[0] || null);
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
        </div>
      </div>
    </section>
  );
}

export default ScannerBoardReview;
