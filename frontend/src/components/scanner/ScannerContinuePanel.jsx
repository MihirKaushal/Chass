import Button from "../ui/Button";
import StatusBadge from "../ui/StatusBadge";

function ScannerContinuePanel() {
  return (
    <section
      className="scanner-panel scanner-continue-panel"
      aria-labelledby="scanner-continue-title"
    >
      <header className="scanner-panel-header">
        <div>
          <span className="eyebrow">Next Step</span>
          <h2 id="scanner-continue-title">Continue On Chass</h2>
        </div>
        <StatusBadge>Coming Later</StatusBadge>
      </header>
      <p className="scanner-continue-description">
        Starting a game from this position is still in development. For now, you
        can review the board and download your corrected labels.
      </p>
      <div
        className="scanner-future-modes"
        aria-label="Game import is not available yet"
      >
        <Button disabled>Start Local Game</Button>
        <Button disabled>Create Online Game</Button>
        <Button disabled>Play Against A Bot</Button>
      </div>
    </section>
  );
}

export default ScannerContinuePanel;
