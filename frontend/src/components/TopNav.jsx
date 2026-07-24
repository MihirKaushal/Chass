function TopNav({
  activeTab,
  onTabChange,
  onReset,
  onHome,
  currentPlayer,
  gameStatus,
  winner,
  onFlipBoard,
  onToggleAutoBoardFlip,
  boardFlipped,
  autoBoardFlipEnabled,
  canCustomize,
  canReset,
  mode,
  playerColor,
  connectionStatus,
}) {
  const statusLabel =
    gameStatus === "checkmate"
      ? `Checkmate (${winner || "none"})`
      : gameStatus === "stalemate"
        ? "Stalemate"
        : gameStatus === "score_target"
          ? `Score Victory (${winner || "none"})`
          : gameStatus === "check"
            ? "Check"
            : "Active";

  return (
    <header className="top-nav">
      <button type="button" className="brand-block brand-button" onClick={onHome}>
        <strong>Chass!</strong>
        <span>Variant-ready chess sandbox</span>
      </button>

      <nav className="tab-nav" aria-label="Game sections">
        <button
          type="button"
          className={activeTab === "play" ? "tab active" : "tab"}
          onClick={() => onTabChange("play")}
        >
          Play
        </button>
        {canCustomize ? (
          <button
            type="button"
            className={activeTab === "customize" ? "tab active" : "tab"}
            onClick={() => onTabChange("customize")}
          >
            Customize
          </button>
        ) : null}
      </nav>

      <div className="game-meta">
        <span className="turn-pill">Turn: {currentPlayer}</span>
        <span className="status-pill">Status: {statusLabel}</span>
        <span className="mode-pill">
          {mode === "online"
            ? `${playerColor || "Online"} / ${connectionStatus}`
            : "Local room"}
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
            Reset
          </button>
        ) : null}
      </div>
    </header>
  );
}

export default TopNav;
