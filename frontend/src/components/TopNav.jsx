function TopNav({
  activeTab,
  onTabChange,
  onReset,
  currentPlayer,
  gameStatus,
  winner,
  onFlipBoard,
  onToggleAutoBoardFlip,
  boardFlipped,
  autoBoardFlipEnabled,
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
      <div className="brand-block">
        <h1>Chass!</h1>
        <p>Variant-ready chess sandbox</p>
      </div>

      <nav className="tab-nav">
        <button
          type="button"
          className={activeTab === "play" ? "tab active" : "tab"}
          onClick={() => onTabChange("play")}
        >
          Play
        </button>
        <button
          type="button"
          className={activeTab === "customize" ? "tab active" : "tab"}
          onClick={() => onTabChange("customize")}
        >
          Customize
        </button>
      </nav>

      <div className="status-block">
        <span className="turn-pill">Turn: {currentPlayer}</span>
        <span className="status-pill">Status: {statusLabel}</span>
        <button
          type="button"
          className="reset-button secondary"
          onClick={onFlipBoard}
        >
          {boardFlipped ? "Unflip Board" : "Flip Board"}
        </button>
        <button
          type="button"
          className={autoBoardFlipEnabled ? "reset-button" : "reset-button secondary"}
          onClick={onToggleAutoBoardFlip}
        >
          Toggle Auto Board Flip ({autoBoardFlipEnabled ? "On" : "Off"})
        </button>
        <button type="button" className="reset-button" onClick={onReset}>
          Reset
        </button>
      </div>
    </header>
  );
}

export default TopNav;
