import { useEffect, useRef, useState } from "react";

import { onlinePlayerSummary, roomLabel } from "../playHeader";
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
  canReset,
  mode,
  playerColor,
  presence,
  gameReady,
  variant,
  phase,
}) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const settingsRef = useRef(null);
  const settingsTriggerRef = useRef(null);
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

    settingsRef.current?.querySelector('[role="menuitem"]')?.focus();
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
    const items = [...event.currentTarget.querySelectorAll('[role="menuitem"]:not(:disabled)')];
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
        <button type="button" className="tab" onClick={onHome}>
          Home
        </button>
        <button type="button" className="tab" onClick={onCustomize}>
          Customize
        </button>
      </nav>

      <div className="game-hud">
        <span className="turn-banner">
          <i aria-hidden="true" />
          {phase === "play" && !winner ? `${title(currentPlayer)} to move` : statusLabel}
        </span>
        {phase === "play" && !winner && gameStatus !== "active" ? (
          <StatusBadge tone="info" className="status-chip">
            {title(gameStatus)}
          </StatusBadge>
        ) : null}
        {mode === "online" ? (
          <span className="online-player-summary" aria-live="polite">
            {onlinePlayerSummary(playerColor, presence, gameReady)}
          </span>
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
            <circle cx="12" cy="12" r="5" />
            <circle cx="12" cy="12" r="2" />
            <path d="M12 2.5v4M12 17.5v4M2.5 12h4M17.5 12h4M5.3 5.3l2.8 2.8M15.9 15.9l2.8 2.8M18.7 5.3l-2.8 2.8M8.1 15.9l-2.8 2.8" />
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
                {variant === "gambit" ? "Request New Setup" : "Request Restart"}
              </Button>
            ) : null}
          </div>
        ) : null}
      </div>
    </header>
  );
}

export default TopNav;
