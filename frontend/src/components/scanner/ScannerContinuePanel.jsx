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
        <h2 id="scanner-continue-title">Continue game</h2>
        <StatusBadge tone={ready ? "success" : "neutral"} busy={busy || validating}>
          {busy
            ? "Creating game"
            : validating
              ? "Checking position"
              : ready
                ? "Ready to play"
                : "Review required"}
        </StatusBadge>
      </header>
      <p className="scanner-continue-description">
        In an online room, you play White and your friend plays Black.
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
              Recheck position
            </Button>
          </p>
        ) : null}
        {!error && !validation?.issues?.length && !ready ? (
          <p>
            {remainingReviews
              ? `Resolve ${remainingReviews} flagged square${remainingReviews === 1 ? "" : "s"} before continuing.`
              : "Confirm the board and game details above."}
          </p>
        ) : null}
      </div>
      <div className="scanner-future-modes">
        <Button disabled={!ready} onClick={() => onContinue("local")}>
          Start local game
        </Button>
        <Button variant="secondary" disabled={!ready} onClick={() => onContinue("online")}>
          Create online game
        </Button>
      </div>
    </section>
  );
}

export default ScannerContinuePanel;
