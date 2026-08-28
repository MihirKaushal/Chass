import { useEffect, useRef, useState } from "react";

import { onlinePlayerStatus, onlinePlayerSummary, roomLabel } from "../playHeader";
import Button from "./ui/Button";
import StatusBadge from "./ui/StatusBadge";

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
  autoBoardFlipEnabled,
  onToggleMatchAnalysis,
  matchAnalysisEnabled,
  matchAnalysisAvailable,
  canReset,
  mode,
  playerColor,
  presence,
  gameReady,
  variant,
  phase,
  bot,
}) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const settingsRef = useRef(null);
  const settingsTriggerRef = useRef(null);
  const onlineStatus = onlinePlayerStatus(playerColor, presence, gameReady);
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

  useEffect(() => {
    if (!settingsOpen) return undefined;

    settingsRef.current?.querySelector('[role^="menuitem"]:not(:disabled)')?.focus();
    const closeOnOutsideClick = (event) => {
      if (!settingsRef.current?.contains(event.target)) {
        setSettingsOpen(false);
      }
    };
    const closeOnEscape = (event) => {
      if (event.key === "Escape") {
        setSettingsOpen(false);
        settingsTriggerRef.current?.focus();
      }
    };
    document.addEventListener("pointerdown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [settingsOpen]);

  const runSetting = (action) => {
    action();
    setSettingsOpen(false);
    settingsTriggerRef.current?.focus();
  };

  const handleMenuKeyDown = (event) => {
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
    const items = [...event.currentTarget.querySelectorAll('[role^="menuitem"]:not(:disabled)')];
    if (!items.length) return;
    event.preventDefault();
    const currentIndex = items.indexOf(document.activeElement);
    if (event.key === "Home") {
      items[0].focus();
    } else if (event.key === "End") {
      items[items.length - 1].focus();
    } else {
      const direction = event.key === "ArrowDown" ? 1 : -1;
      const nextIndex = (currentIndex + direction + items.length) % items.length;
      items[nextIndex].focus();
    }
  };

  return (
    <header className="top-nav">
      <button type="button" className="brand-block brand-button" onClick={onHome}>
        <strong>Chass!</strong>
        <span>Build the rules. Play the board.</span>
      </button>

      <nav className="tab-nav" aria-label="Game sections">
        <button type="button" className="tab site-nav-button" onClick={onHome}>
          Home
        </button>
        <button type="button" className="tab site-nav-button" onClick={onCustomize}>
          Customize
        </button>
      </nav>

      <div className="game-hud">
        {mode === "online" ? (
          <span
            className={`online-player-summary connection-${onlineStatus.connection || "spectator"}`}
            aria-label={onlinePlayerSummary(playerColor, presence, gameReady)}
            aria-live="polite"
          >
            {onlineStatus.role === "spectator" ? (
              <span>You are spectating this online room.</span>
            ) : (
              <>
                <span>
                  You are playing as <strong className={`player-color-token ${onlineStatus.playerColor}`}>{title(onlineStatus.playerColor)}</strong>.
                </span>
                <span>
                  <strong className={`player-color-token ${onlineStatus.opponentColor}`}>{title(onlineStatus.opponentColor)}</strong>{" "}
                  {onlineStatus.connection === "waiting" ? (
                    <>has not joined.</>
                  ) : (
                    <>is <strong className={`connection-label ${onlineStatus.connection}`}>{onlineStatus.connection}</strong>.</>
                  )}
                </span>
              </>
            )}
          </span>
        ) : null}
        {mode === "bot" && bot ? (
          <span className="bot-player-summary" aria-label={`You are playing ${title(bot.humanColor)} against the estimated ${bot.targetElo} Elo bot.`}>
            <span>
              You are <strong className={`player-color-token ${bot.humanColor}`}>{title(bot.humanColor)}</strong>.
            </span>
            <span>
              <strong>Estimated {bot.targetElo}</strong> bot plays {title(bot.botColor)}.
            </span>
          </span>
        ) : null}
        <span className="turn-banner">
          <i aria-hidden="true" />
          {phase === "play" && !winner ? `${title(currentPlayer)} to move` : statusLabel}
        </span>
        {phase === "play" && !winner && gameStatus !== "active" ? (
          <StatusBadge tone="info" className="status-chip">
            {title(gameStatus)}
          </StatusBadge>
        ) : null}
        <StatusBadge className="mode-chip">
          {roomLabel(mode)}
        </StatusBadge>
      </div>

      <div className="play-settings" ref={settingsRef}>
        <button
          ref={settingsTriggerRef}
          type="button"
          className={`play-settings-trigger ${settingsOpen ? "is-open" : ""}`}
          aria-label="Game settings"
          aria-haspopup="menu"
          aria-expanded={settingsOpen}
          aria-controls="play-settings-menu"
          title="Game settings"
          onClick={() => setSettingsOpen((open) => !open)}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.09a2 2 0 0 1 1 1.74v.5a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.38a2 2 0 0 0-.73-2.73l-.15-.09a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2Z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
        </button>
        {settingsOpen ? (
          <div
            id="play-settings-menu"
            className="play-settings-menu"
            role="menu"
            aria-label="Game settings"
            onKeyDown={handleMenuKeyDown}
          >
            <Button
              size="small"
              variant={matchAnalysisEnabled ? "primary" : "secondary"}
              role="menuitemcheckbox"
              aria-checked={matchAnalysisEnabled}
              disabled={!matchAnalysisAvailable}
              onClick={() => runSetting(onToggleMatchAnalysis)}
            >
              Match Analysis: {matchAnalysisAvailable ? (matchAnalysisEnabled ? "Enabled" : "Disabled") : "Unavailable"}
            </Button>
            <Button size="small" variant="secondary" role="menuitem" onClick={() => runSetting(onFlipBoard)}>
              Flip Board
            </Button>
            <Button
              size="small"
              variant={autoBoardFlipEnabled ? "primary" : "secondary"}
              role="menuitem"
              onClick={() => runSetting(onToggleAutoBoardFlip)}
            >
              Auto Flip: {autoBoardFlipEnabled ? "On" : "Off"}
            </Button>
            {canReset ? (
              <Button size="small" role="menuitem" onClick={() => runSetting(onReset)}>
                {mode === "bot"
                  ? "Restart Game"
                  : variant === "gambit" ? "Request New Setup" : "Request Restart"}
              </Button>
            ) : null}
          </div>
        ) : null}
      </div>
    </header>
  );
}

export default TopNav;
