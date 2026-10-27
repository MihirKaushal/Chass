import Button from "../ui/Button";
import StatusBadge from "../ui/StatusBadge";

function ScannerContinuePanel({
  confirmed,
  remainingReviews = 0,
  validation,
  validating,
  error,
  busy,
  onContinue,
  onRetry,
  onIssue,
}) {
  const ready =
    confirmed &&
    remainingReviews === 0 &&
    validation?.valid &&
    !validating &&
    !busy;
  return (
    <section
      className="scanner-panel scanner-continue-panel"
      aria-labelledby="scanner-continue-title"
      aria-busy={busy || validating}
    >
      <header className="scanner-panel-header">
        <div>
          <span className="eyebrow">Continue From This Position</span>
          <h2 id="scanner-continue-title">Play On Chass</h2>
        </div>
        <StatusBadge tone={ready ? "success" : "neutral"}>
          {busy
            ? "Creating Game"
            : validating
              ? "Checking Position"
              : ready
                ? "Ready To Play"
                : "Review Required"}
        </StatusBadge>
      </header>
      <p className="scanner-continue-description">
        Play on this device, or create a private online room. For online games
        you play White and your friend joins as Black, regardless of whose turn
        is next.
      </p>
      <div className="scanner-import-feedback" aria-live="polite">
        {validation?.issues?.length ? (
          <ul>
            {validation.issues.map((issue, index) => (
              <li key={index}>
                <Button variant="text" onClick={() => onIssue?.(issue)}>
                  {issue.message}
                </Button>
              </li>
            ))}
          </ul>
        ) : null}
        {error ? (
          <p role="alert" className="scanner-field-error">
            {error}{" "}
            <Button variant="text" size="small" onClick={onRetry}>
              Recheck Position
            </Button>
          </p>
        ) : null}
        {!error && !validation?.issues?.length && !ready ? (
          <p>
            {remainingReviews
              ? `Resolve ${remainingReviews} flagged square${remainingReviews === 1 ? "" : "s"} before continuing.`
              : "Confirm the reviewed board and game details above before continuing."}
          </p>
        ) : null}
      </div>
      <div className="scanner-future-modes">
        <Button disabled={!ready} onClick={() => onContinue("local")}>
          Start Local Game
        </Button>
        <Button disabled={!ready} onClick={() => onContinue("online")}>
          Create Online Game
        </Button>
        <Button disabled title="Scanned-position bot games are coming later.">
          Play Against A Bot (Later)
        </Button>
      </div>
    </section>
  );
}

export default ScannerContinuePanel;
