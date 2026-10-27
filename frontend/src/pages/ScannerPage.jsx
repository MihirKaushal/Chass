import { useEffect, useRef, useState } from "react";

import ScannerBoardReview from "../components/scanner/ScannerBoardReview";
import ScannerPositionDetails from "../components/scanner/ScannerPositionDetails";
import ScannerContinuePanel from "../components/scanner/ScannerContinuePanel";
import ScannerIcon from "../components/scanner/ScannerIcon";
import ScannerPhotoPanel from "../components/scanner/ScannerPhotoPanel";
import { scannerPreviewPiece } from "../components/scanner/scannerPreview";
import SiteFooter from "../components/SiteFooter";
import Button from "../components/ui/Button";
import {
  recognizePhoto,
  scannerServiceUrl,
  reviewedBoardLabels,
  downloadScannerFile,
} from "../scannerApi";

function ScannerPage() {
  const [board, setBoard] = useState(null);
  const [reviewSquares, setReviewSquares] = useState([]);
  const [boardHistory, setBoardHistory] = useState([]);
  const [confirmed, setConfirmed] = useState(false);
  const [scan, setScan] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const requestRef = useRef(null);
  const serviceUrl = scannerServiceUrl(
    window.location.hostname,
    import.meta.env.VITE_SCANNER_API_URL || "",
  );

  const scanBoard = (result) =>
    result.board.map((rank, row) =>
      rank.map((label, col) => {
        if (!label) return null;
        const [color, type] = label.split("-");
        return scannerPreviewPiece(type, color, row, col);
      }),
    );

  const invalidateScan = () => {
    requestRef.current?.abort();
    requestRef.current = null;
    setBusy(false);
    setError("");
    setScan(null);
    setBoard(null);
    setBoardHistory([]);
    setReviewSquares([]);
    setConfirmed(false);
  };

  const recognize = async (file) => {
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    setBusy(true);
    setError("");
    const timeout = window.setTimeout(() => controller.abort(), 90000);
    try {
      const result = await recognizePhoto(serviceUrl, file, controller.signal);
      if (requestRef.current !== controller) return;
      setScan(result);
      setBoard(scanBoard(result));
      setReviewSquares(result.reviewSquares);
      setBoardHistory([]);
      setConfirmed(false);
    } catch (failure) {
      if (requestRef.current === controller)
        setError(
          failure.name === "AbortError"
            ? "Recognition timed out. Check the local scanner terminal and retry."
            : failure.message,
        );
    } finally {
      window.clearTimeout(timeout);
      if (requestRef.current === controller) {
        setBusy(false);
        requestRef.current = null;
      }
    }
  };

  useEffect(() => {
    const previousTitle = document.title;
    document.title = "AI Chess Board Scanner | Chass!";
    return () => {
      requestRef.current?.abort();
      requestRef.current = null;
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
            Experimental
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
            <strong>Local scanner testing.</strong> Review every square after
            recognition. This model has limited training data, and game import
            is not connected yet.
          </p>
        </div>

        <div
          className={`scanner-workspace${board ? "" : " scanner-workspace-initial"}`}
        >
          <ScannerPhotoPanel
            onRecognize={recognize}
            onPhotoChange={invalidateScan}
            busy={busy}
            serviceAvailable={Boolean(serviceUrl)}
          />
          {board ? (
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
                setBoard(scanBoard(scan));
                setReviewSquares(scan.reviewSquares);
                setBoardHistory([]);
                setConfirmed(false);
              }}
            />
          ) : null}
        </div>
        <div className="scanner-request-status" aria-live="polite">
          {error ? (
            <p className="scanner-field-error" role="alert">
              {error}
            </p>
          ) : busy ? (
            <p>
              Recognizing pieces locally. You can replace the photo to cancel.
            </p>
          ) : null}
        </div>
        {scan?.warnings?.length ? (
          <div className="scanner-preview-banner">
            <ScannerIcon name="info" />
            <p>{scan.warnings.join(" ")}</p>
          </div>
        ) : null}

        {board ? (
          <>
            <ScannerPositionDetails
              confirmed={confirmed}
              onConfirmationChange={setConfirmed}
            />

            <div className="scanner-label-export">
              <Button
                variant="secondary"
                disabled={!confirmed || reviewSquares.length > 0}
                onClick={() => {
                  const labels = reviewedBoardLabels(scan, board);
                  downloadScannerFile(
                    new Blob([JSON.stringify(labels, null, 2)], {
                      type: "application/json",
                    }),
                    "chass-reviewed-board.json",
                  );
                }}
              >
                Export Reviewed Labels
              </Button>
              <small>
                For accuracy testing: check all 64 squares, resolve gold
                markers, and confirm above. Keep the prepared photo with these
                labels.
              </small>
            </div>

            <ScannerContinuePanel confirmed={confirmed} />
          </>
        ) : null}
      </main>
      <SiteFooter />
    </div>
  );
}

export default ScannerPage;
