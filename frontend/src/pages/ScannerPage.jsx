import { useEffect, useRef, useState } from "react";

import ScannerBoardReview from "../components/scanner/ScannerBoardReview";
import ScannerPositionDetails from "../components/scanner/ScannerPositionDetails";
import ScannerContinuePanel from "../components/scanner/ScannerContinuePanel";
import ScannerIcon from "../components/scanner/ScannerIcon";
import ScannerPhotoPanel from "../components/scanner/ScannerPhotoPanel";
import ScannerServiceStatus from "../components/scanner/ScannerServiceStatus";
import { scannerPreviewPiece } from "../components/scanner/scannerPreview";
import SiteFooter from "../components/SiteFooter";
import LandingNav from "../components/LandingNav";
import AppLink from "../components/AppLink";
import Button from "../components/ui/Button";
import Dialog from "../components/ui/Dialog";
import StatusBadge from "../components/ui/StatusBadge";
import { navigate, useNavigationBlocker } from "../routing";
import { validateScannedPosition } from "../api/gameApi";
import {
  defaultScannerDetails,
  scannerImportPayload,
  scannerDetailError,
} from "../scannerReview";
import {
  recognizePhoto,
  scannerServiceUrl,
  reviewedBoardLabels,
  downloadScannerFile,
  scannerAvailability,
} from "../scannerApi";

function ScannerPage({ onHome, onCustomize, onImport }) {
  const [board, setBoard] = useState(null);
  const [reviewSquares, setReviewSquares] = useState([]);
  const [boardHistory, setBoardHistory] = useState([]);
  const [confirmed, setConfirmed] = useState(false);
  const [scan, setScan] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [hasPhoto, setHasPhoto] = useState(false);
  const [pendingDestination, setPendingDestination] = useState(null);
  const [connectionRetry, setConnectionRetry] = useState(0);
  const [details, setDetails] = useState(defaultScannerDetails);
  const [validation, setValidation] = useState(null);
  const [validating, setValidating] = useState(false);
  const [validationRetry, setValidationRetry] = useState(0);
  const [importError, setImportError] = useState("");
  const [creating, setCreating] = useState(false);
  const [issueSquares, setIssueSquares] = useState([]);
  const requestRef = useRef(null);
  const serviceUrl = scannerServiceUrl(
    window.location.hostname,
    import.meta.env.VITE_SCANNER_API_URL || "",
    import.meta.env.VITE_API_URL || "http://localhost:8000",
  );
  const [serviceStatus, setServiceStatus] = useState(
    serviceUrl ? "checking" : "unconfigured",
  );
  const currentStep = !board ? 0 : !reviewSquares.length ? 2 : 1;

  useEffect(() => {
    if (!scan) return undefined;
    const frame = window.requestAnimationFrame(() => {
      document
        .getElementById("scanner-review-title")
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [scan]);

  useNavigationBlocker((destination) => {
    setPendingDestination(destination);
    return false;
  }, hasPhoto || creating);

  useEffect(() => {
    if (!board) return undefined;
    let active = true;
    const controller = new AbortController();
    setValidation(null);
    setImportError("");
    const detailError = scannerDetailError(details);
    if (detailError) {
      setValidation({
        valid: false,
        issues: [{ message: detailError, field: "details", squares: [] }],
      });
      setValidating(false);
      return undefined;
    }
    setValidating(true);
    const timeout = window.setTimeout(() => controller.abort(), 45000);
    const timer = window.setTimeout(() => {
      validateScannedPosition(
        scannerImportPayload(board, details),
        controller.signal,
      )
        .then((result) => {
          if (active) setValidation(result);
        })
        .catch((failure) => {
          if (active)
            setImportError(
              controller.signal.aborted
                ? "Position validation timed out. Retry once the game service is connected."
                : failure.message,
            );
        })
        .finally(() => {
          window.clearTimeout(timeout);
          if (active) setValidating(false);
        });
    }, 250);
    return () => {
      active = false;
      window.clearTimeout(timer);
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [board, details, validationRetry]);

  useEffect(() => {
    if (!serviceUrl) {
      setServiceStatus("unconfigured");
      return undefined;
    }
    let active = true;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 75000);
    setServiceStatus("checking");
    scannerAvailability(serviceUrl, controller.signal)
      .then((status) => {
        if (active) setServiceStatus(status);
      })
      .catch(() => {
        if (active) setServiceStatus("offline");
      })
      .finally(() => window.clearTimeout(timeout));
    return () => {
      active = false;
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, [serviceUrl, connectionRetry]);

  const scanBoard = (result) =>
    result.board.map((rank, row) =>
      rank.map((label, col) => {
        if (!label) return null;
        const [color, type] = label.split("-");
        return scannerPreviewPiece(type, color, row, col);
      }),
    );

  const invalidateScan = (photoPresent = true) => {
    setHasPhoto(photoPresent);
    requestRef.current?.abort();
    requestRef.current = null;
    setBusy(false);
    setError("");
    setScan(null);
    setBoard(null);
    setBoardHistory([]);
    setReviewSquares([]);
    setConfirmed(false);
    setDetails(defaultScannerDetails());
    setValidation(null);
    setIssueSquares([]);
    setImportError("");
  };

  const recognize = async (file) => {
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    setBusy(true);
    setConfirmed(false);
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
      setDetails(defaultScannerDetails());
      setIssueSquares([]);
    } catch (failure) {
      if (requestRef.current === controller)
        setError(
          failure.name === "AbortError"
            ? "Recognition timed out. Check the scanner connection and try again."
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
    setValidation(null);
    setIssueSquares([]);
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
    setValidation(null);
    setIssueSquares([]);
  };

  const continueGame = async (mode) => {
    if (
      creating ||
      busy ||
      !confirmed ||
      reviewSquares.length ||
      !validation?.valid ||
      validating
    )
      return;
    setCreating(true);
    setImportError("");
    try {
      await onImport(
        scannerImportPayload(board, details, { mode, confirmed: true }),
      );
    } catch (failure) {
      setImportError(
        failure.message || "The game could not be created. Try again.",
      );
      setCreating(false);
    }
  };

  return (
    <div className="page-frame scanner-page">
      <main className="scanner-shell">
        <LandingNav
          active="scanner"
          onHome={onHome}
          onCustomize={onCustomize}
        />
        <header className="scanner-hero">
          <div className="scanner-heading">
            <div>
              <div className="scanner-hero-meta">
                <span className="eyebrow">Chass! Vision</span>
                <StatusBadge tone="info">Experimental</StatusBadge>
              </div>
              <h1>AI Chess Board Scanner</h1>
              <p>
                Scan a physical board, review the pieces, and continue your game
                on one device or in a private online room.
              </p>
              <AppLink
                href="/rulebook#rulebook-scanner"
                className="scanner-guide-link"
              >
                <ScannerIcon name="info" />
                Scanner Guide In The Rulebook
              </AppLink>
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
          </div>
          <ol className="scanner-progress" aria-label="Scanner progress">
            {["Prepare Photo", "Review Pieces", "Confirm Position"].map(
              (label, index) => (
                <li
                  key={label}
                  className={
                    index < currentStep
                      ? "is-complete"
                      : index === currentStep
                        ? "is-current"
                        : ""
                  }
                  aria-current={index === currentStep ? "step" : undefined}
                >
                  <span aria-hidden="true">
                    {index < currentStep ? (
                      <ScannerIcon name="check" />
                    ) : (
                      index + 1
                    )}
                  </span>
                  {label}
                </li>
              ),
            )}
          </ol>
        </header>
        <fieldset className="scanner-workflow" disabled={creating}>
          <ScannerServiceStatus
            status={serviceStatus}
            onRetry={() => setConnectionRetry((value) => value + 1)}
          />

          <div
            className={`scanner-workspace${board ? "" : " scanner-workspace-initial"}`}
          >
            <ScannerPhotoPanel
              onRecognize={recognize}
              onPhotoChange={invalidateScan}
              busy={busy}
              serviceAvailable={serviceStatus === "ready"}
            />
            {board ? (
              <fieldset className="scanner-workflow" disabled={busy}>
                <ScannerBoardReview
                  scan={scan}
                  issueSquares={issueSquares}
                  board={board}
                  reviewSquares={reviewSquares}
                  onSquareEdit={editSquare}
                  onReviewSquare={(target) => {
                    setReviewSquares((current) =>
                      current.filter(
                        (square) =>
                          square.row !== target.row ||
                          square.col !== target.col,
                      ),
                    );
                    setConfirmed(false);
                    setIssueSquares([]);
                  }}
                  onUndo={undoEdit}
                  canUndo={boardHistory.length > 0}
                  onReset={() => {
                    setValidation(null);
                    setBoard(scanBoard(scan));
                    setReviewSquares(scan.reviewSquares);
                    setBoardHistory([]);
                    setConfirmed(false);
                    setIssueSquares([]);
                  }}
                />
              </fieldset>
            ) : null}
          </div>
          <div className="scanner-request-status" aria-live="polite">
            {error ? (
              <p className="scanner-field-error" role="alert">
                {error}
              </p>
            ) : busy ? (
              <p>Recognizing pieces. You can replace the photo to cancel.</p>
            ) : null}
          </div>
          {scan?.warnings?.length ? (
            <div className="scanner-preview-banner">
              <ScannerIcon name="info" />
              <p>{scan.warnings.join(" ")}</p>
            </div>
          ) : null}

          {board ? (
            <fieldset className="scanner-workflow" disabled={busy}>
              <ScannerPositionDetails
                details={details}
                remainingReviews={reviewSquares.length}
                onChange={(next) => {
                  setDetails(next);
                  setConfirmed(false);
                  setValidation(null);
                  setIssueSquares([]);
                }}
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

              <ScannerContinuePanel
                confirmed={confirmed}
                remainingReviews={reviewSquares.length}
                validation={validation}
                validating={validating}
                busy={creating}
                error={importError}
                onContinue={continueGame}
                onRetry={() => setValidationRetry((value) => value + 1)}
                onIssue={(issue) => {
                  setIssueSquares(issue.squares || []);
                  document
                    .getElementById(
                      issue.field === "board"
                        ? "scanner-review-title"
                        : "scanner-position-title",
                    )
                    ?.scrollIntoView({ behavior: "smooth", block: "center" });
                }}
              />
            </fieldset>
          ) : null}
        </fieldset>
      </main>
      <SiteFooter />
      <Dialog
        open={Boolean(pendingDestination)}
        onClose={() => setPendingDestination(null)}
        title="Leave Board Scanner?"
        eyebrow="Current Scan"
        closeLabel="Close leave scanner confirmation"
        description={
          creating
            ? "Please wait while the game is created. Your scan will open as a game when it is ready."
            : "Your photo and corrections will be cleared when you leave. Download any prepared photo or reviewed labels you want to keep."
        }
        actions={
          <>
            <Button
              variant="secondary"
              onClick={() => setPendingDestination(null)}
            >
              Keep Editing
            </Button>
            <Button
              variant="danger"
              disabled={creating}
              onClick={() => {
                const destination = pendingDestination;
                setPendingDestination(null);
                navigate(destination, { bypassBlocker: true });
              }}
            >
              Leave Scanner
            </Button>
          </>
        }
      />
    </div>
  );
}

export default ScannerPage;
