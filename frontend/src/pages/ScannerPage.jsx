import { useEffect, useRef, useState } from "react";

import ScannerBoardReview from "../components/scanner/ScannerBoardReview";
import ScannerPositionDetails from "../components/scanner/ScannerPositionDetails";
import ScannerContinuePanel from "../components/scanner/ScannerContinuePanel";
import ScannerIcon from "../components/scanner/ScannerIcon";
import ScannerPhotoPanel from "../components/scanner/ScannerPhotoPanel";
import ScannerServiceStatus from "../components/scanner/ScannerServiceStatus";
import ScannerScanDetails from "../components/scanner/ScannerScanDetails";
import { createReviewClock } from "../scannerInsights";
import { scannerPreviewPiece } from "../components/scanner/scannerPreview";
import SiteFooter from "../components/SiteFooter";
import LandingNav from "../components/LandingNav";
import AppLink from "../components/AppLink";
import Button from "../components/ui/Button";
import Dialog from "../components/ui/Dialog";
import Disclosure from "../components/ui/Disclosure";
import { navigate, useNavigationBlocker } from "../routing";
import { validateScannedPosition } from "../api/gameApi";
import { browserScannerSupported, recognizeInBrowser, recognizeWithFallback } from "../scanner/browserClient";
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
  waitForScanner,
  scannerWakeUrl,
  addKingReviewHints,
} from "../scannerApi";

function ScannerPage({ onHome, onCustomize, onImport }) {
  const [board, setBoard] = useState(null);
  const [reviewSquares, setReviewSquares] = useState([]);
  const [boardHistory, setBoardHistory] = useState([]);
  const [confirmed, setConfirmed] = useState(false);
  const [scan, setScan] = useState(null);
  const [preparedPhoto, setPreparedPhoto] = useState(null);
  const [photoUrl, setPhotoUrl] = useState("");
  const [selectedSquare, setSelectedSquare] = useState(null);
  const [showDetections, setShowDetections] = useState(false);
  const [reviewMs, setReviewMs] = useState(0);
  const reviewClock = useRef(null);
  const [busy, setBusy] = useState(false);
  const [onDevice, setOnDevice] = useState(false);
  const [recognitionStatus, setRecognitionStatus] = useState("");
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
  const wakeUrl = scannerWakeUrl(serviceUrl, import.meta.env.VITE_SCANNER_WAKE_URL || "");
  const currentStep = !board ? 0 : !reviewSquares.length ? 2 : 1;

  useEffect(() => {
    if (!preparedPhoto) { setPhotoUrl(""); return undefined; }
    const url = URL.createObjectURL(preparedPhoto);
    setPhotoUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [preparedPhoto]);

  useEffect(() => {
    if (!scan) return undefined;
    const clock = reviewClock.current;
    const update = () => {
      if (document.hidden || confirmed || busy) clock.pause();
      else clock.resume();
    };
    update();
    setReviewMs(clock.elapsed());
    document.addEventListener("visibilitychange", update);
    return () => { clock.pause(); document.removeEventListener("visibilitychange", update); };
  }, [scan, confirmed, busy]);

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
    waitForScanner(serviceUrl, {
      signal: controller.signal,
      wakeUrl,
      onStatus: (status) => {
        if (active) setServiceStatus(status);
      },
    })
      .then((status) => {
        if (active) setServiceStatus(status);
      })
      .catch(() => {
        if (active) setServiceStatus("offline");
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [serviceUrl, wakeUrl, connectionRetry]);

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
    if (requestRef.current) setConnectionRetry((value) => value + 1);
    requestRef.current?.abort();
    requestRef.current = null;
    setBusy(false);
    setError("");
    setScan(null);
    setPreparedPhoto(null);
    setSelectedSquare(null);
    setShowDetections(false);
    reviewClock.current = null;
    setReviewMs(0);
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
    setRecognitionStatus("Connecting to scanner...");
    setConfirmed(false);
    setError("");
    let timeout;
    const started = performance.now();
    const clientTimings = {};
    try {
      const result = addKingReviewHints(await recognizeWithFallback({
        enabled: onDevice, file, signal: controller.signal,
        onStatus: (message) => {
          if (requestRef.current === controller) setRecognitionStatus(message);
        },
        browser: async (...args) => {
          const attempt = performance.now();
          try { return await recognizeInBrowser(...args); }
          catch (failure) { clientTimings.fallbackMs = performance.now() - attempt; throw failure; }
        },
        server: async () => {
          // A prepared photo may sit open long enough for the model to fall asleep.
          const connectionStarted = performance.now();
          const status = await waitForScanner(serviceUrl, {
            signal: controller.signal, wakeUrl,
            onStatus: (next) => {
              if (requestRef.current === controller) setServiceStatus(next);
            },
          });
          clientTimings.connectionMs = performance.now() - connectionStarted;
          controller.signal.throwIfAborted();
          if (requestRef.current === controller) setServiceStatus(status);
          if (status !== "ready") throw new Error("Scanner unavailable. Retry Connection, then scan again.");
          if (requestRef.current === controller) setRecognitionStatus("Recognizing pieces...");
          timeout = window.setTimeout(() => controller.abort(), 90000);
          const requestStarted = performance.now();
          const response = await recognizePhoto(serviceUrl, file, controller.signal);
          clientTimings.requestMs = performance.now() - requestStarted;
          return response;
        },
      }));
      if (requestRef.current !== controller) return;
      clientTimings.totalMs = performance.now() - started;
      setScan({ ...result, clientTimings });
      setPreparedPhoto(file);
      setSelectedSquare(result.reviewSquares[0] || null);
      reviewClock.current = createReviewClock();
      setReviewMs(0);
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
      [...current, { board, reviewSquares, selectedSquare: { row, col } }].slice(-40),
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
    setSelectedSquare(previous.selectedSquare);
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
              <div className="scanner-title-row">
                <h1>AI Board Scanner</h1>
              </div>
              <p>
                Turn a photo into a playable game. Standard 8 x 8 boards and
                classic pieces only.
              </p>
            </div>
            <AppLink
              href="/rulebook#rulebook-scanner"
              className="scanner-guide-link"
            >
              <ScannerIcon name="info" />
              Scanner Guide
            </AppLink>
          </div>
          <fieldset className="scanner-workflow scanner-connection-controls" disabled={creating}>
            <ScannerServiceStatus
              status={serviceStatus}
              onRetry={() => setConnectionRetry((value) => value + 1)}
            />
            <Disclosure className="scanner-runtime-options" summary="Recognition Options">
              <label className="scanner-runtime-toggle">
                <input type="checkbox" checked={onDevice} disabled={busy || !browserScannerSupported()}
                  onChange={(event) => setOnDevice(event.target.checked)} />
                Try on-device recognition
              </label>
              <p>Downloads models once (about 52 MB, plus the runtime). Speed depends on your device.
                If it fails, your prepared photo is sent to the server instead. Review all squares either way.</p>
            </Disclosure>
          </fieldset>
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
          {scan && board ? <ScannerScanDetails scan={scan} board={board}
            reviewSquares={reviewSquares} confirmed={confirmed} reviewMs={reviewMs}
            showDetections={showDetections} onShowDetections={setShowDetections} /> : null}

          <div
            className={`scanner-workspace${board ? "" : " scanner-workspace-initial"}`}
          >
            <ScannerPhotoPanel
              onRecognize={recognize}
              onPhotoChange={invalidateScan}
              busy={busy}
              serviceAvailable={serviceStatus === "ready" || onDevice}
              scan={scan}
              selectedSquare={selectedSquare}
              showDetections={showDetections}
            />
            {board ? (
              <fieldset className="scanner-workflow" disabled={busy}>
                <ScannerBoardReview
                  scan={scan}
                  photoUrl={photoUrl}
                  selectedSquare={selectedSquare}
                  onSelectSquare={setSelectedSquare}
                  issueSquares={issueSquares}
                  board={board}
                  reviewSquares={reviewSquares}
                  onSquareEdit={editSquare}
                  onReviewSquare={(target) => {
                    setBoardHistory((current) =>
                      [...current, { board, reviewSquares, selectedSquare: target }].slice(-40),
                    );
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
              <p>{recognitionStatus}</p>
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

              <Disclosure className="scanner-label-export" summary="Export For Accuracy Testing">
                <p>Keep the prepared photo and reviewed labels together.</p>
                <Button
                  variant="secondary"
                  disabled={!confirmed || reviewSquares.length > 0}
                  onClick={() => {
                    const labels = reviewedBoardLabels(scan, board, { reviewMs: reviewClock.current?.elapsed() });
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
              </Disclosure>

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
                  if (issue.field === "board" && issue.squares?.length) {
                    setSelectedSquare(issue.squares[0]);
                  }
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
        closeLabel="Close leave scanner confirmation"
        description={
          creating
            ? "Please wait while your game is created."
            : "Your photo and corrections will be cleared. Save any exports you want to keep."
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
