import { useEffect, useState } from "react";

import ScannerBoardReview from "../components/scanner/ScannerBoardReview";
import ScannerPositionDetails from "../components/scanner/ScannerPositionDetails";
import ScannerContinuePanel from "../components/scanner/ScannerContinuePanel";
import ScannerIcon from "../components/scanner/ScannerIcon";
import ScannerPhotoPanel from "../components/scanner/ScannerPhotoPanel";
import {
  createScannerExample,
  EXAMPLE_REVIEW_SQUARES,
  scannerPreviewPiece,
} from "../components/scanner/scannerPreview";
import SiteFooter from "../components/SiteFooter";

function ScannerPage() {
  const [board, setBoard] = useState(createScannerExample);
  const [reviewSquares, setReviewSquares] = useState(EXAMPLE_REVIEW_SQUARES);
  const [boardHistory, setBoardHistory] = useState([]);
  const [confirmed, setConfirmed] = useState(false);

  useEffect(() => {
    const previousTitle = document.title;
    document.title = "AI Chess Board Scanner | Chass!";
    return () => {
      document.title = previousTitle;
    };
  }, []);

  const editSquare = (row, col, tool) => {
    setBoardHistory((current) =>
      [...current, { board, reviewSquares }].slice(-40),
    );
    setBoard((current) =>
      current.map((rank, rankIndex) =>
        rankIndex !== row
          ? rank
          : rank.map((piece, colIndex) =>
              colIndex !== col
                ? piece
                : tool.type === "erase"
                  ? null
                  : scannerPreviewPiece(tool.type, tool.color, row, col),
            ),
      ),
    );
    setReviewSquares((current) =>
      current.filter((square) => square.row !== row || square.col !== col),
    );
    setConfirmed(false);
  };

  const undoEdit = () => {
    const previous = boardHistory[boardHistory.length - 1];
    if (!previous) return;
    setBoard(previous.board);
    setReviewSquares(previous.reviewSquares);
    setBoardHistory((current) => current.slice(0, -1));
    setConfirmed(false);
  };

  return (
    <div className="page-frame scanner-page">
      <main className="scanner-shell">
        <div className="scanner-topbar">
          <div className="scanner-brand">
            <img src="/chass-mark.svg" alt="" />
            <span>Chass!</span>
            <span className="scanner-brand-divider" />
            <span className="scanner-brand-section">Board Scanner</span>
          </div>
          <span className="scanner-preview-badge">
            <span />
            UI Preview
          </span>
        </div>
        <header className="scanner-heading">
          <div>
            <span className="scanner-overline">
              Physical board, digital game
            </span>
            <h1>AI Chess Board Scanner</h1>
            <p>
              Bring a board photo. Check the pieces. Continue from your
              position.
            </p>
          </div>
          <div className="scanner-scope">
            <span className="scanner-scope-mark">
              <ScannerIcon name="align" />
            </span>
            <div>
              <strong>Standard 8 × 8</strong>
              <span>Classic chess pieces</span>
            </div>
          </div>
        </header>
        <div className="scanner-preview-banner">
          <ScannerIcon name="info" />
          <p>
            <strong>Explore the scanner preview.</strong> Photo preview and
            editing controls work locally. AI recognition and game launch are
            coming next.
          </p>
        </div>

        <div className="scanner-workspace">
          <ScannerPhotoPanel />
          <ScannerBoardReview
            board={board}
            reviewSquares={reviewSquares}
            onSquareEdit={editSquare}
            onReviewSquare={(target) => {
              setReviewSquares((current) =>
                current.filter(
                  (square) =>
                    square.row !== target.row || square.col !== target.col,
                ),
              );
              setConfirmed(false);
            }}
            onUndo={undoEdit}
            canUndo={boardHistory.length > 0}
            onReset={() => {
              setBoard(createScannerExample());
              setReviewSquares(EXAMPLE_REVIEW_SQUARES);
              setBoardHistory([]);
              setConfirmed(false);
            }}
          />
        </div>

        <ScannerPositionDetails
          confirmed={confirmed}
          onConfirmationChange={setConfirmed}
        />

        <ScannerContinuePanel confirmed={confirmed} />
      </main>
      <SiteFooter />
    </div>
  );
}

export default ScannerPage;
