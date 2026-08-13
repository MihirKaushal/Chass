function title(value) {
  return value ? value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()) : "";
}

function TopNav({
  onReset,
  onHome,
  onCustomize,
  currentPlayer,
  gameStatus,
  winner,
  onFlipBoard,
  onToggleAutoBoardFlip,
  boardFlipped,
  autoBoardFlipEnabled,
  canReset,
  mode,
  playerColor,
  connectionStatus,
  variant,
  phase,
}) {
  const statusLabel =
    phase === "lobby"
      ? "Waiting For Player"
      : phase === "ability_selection"
        ? "Ability Selection"
        : phase === "deployment"
          ? "Hidden Deployment"
          : phase === "handoff"
            ? "Private Handoff"
            : winner
              ? `${title(winner)} Won`
              : title(gameStatus || "active");

  return (
    <header className="top-nav">
      <button type="button" className="brand-block brand-button" onClick={onHome}>
        <strong>Chass!</strong>
        <span>Build the rules. Play the board.</span>
      </button>

      <nav className="tab-nav" aria-label="Game sections">
        <button type="button" className="tab active">
          Play
        </button>
        <button type="button" className="tab" onClick={onCustomize}>
          Customize
        </button>
      </nav>

      <div className="game-meta">
        <span className="turn-pill">
          {phase === "play" ? `Turn: ${title(currentPlayer)}` : statusLabel}
        </span>
        <span className="status-pill">Status: {statusLabel}</span>
        <span className="mode-pill">
          {mode === "online"
            ? `${title(playerColor || "Online")} / ${connectionStatus}`
            : "Local Room"}
        </span>
      </div>

      <div className="board-actions">
        <button type="button" className="secondary" onClick={onFlipBoard}>
          {boardFlipped ? "White Side" : "Flip Board"}
        </button>
        <button
          type="button"
          className={autoBoardFlipEnabled ? "" : "secondary"}
          onClick={onToggleAutoBoardFlip}
        >
          Auto Flip: {autoBoardFlipEnabled ? "On" : "Off"}
        </button>
        {canReset ? (
          <button type="button" onClick={onReset}>
            {variant === "gambit" ? "Request New Setup" : "Request Restart"}
          </button>
        ) : null}
      </div>
    </header>
  );
}

export default TopNav;
