import { useEffect, useMemo, useState } from "react";

import PieceGlyph from "./PieceGlyph";

function title(value) {
  return value ? value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()) : "";
}

function squareLabel(position, rows = 8) {
  if (!position) return "";
  return `${String.fromCharCode(65 + position.col)}${rows - position.row}`;
}

function MatchClock({ clock }) {
  const [, setTick] = useState(0);
  useEffect(() => {
    if (!clock) return undefined;
    const interval = window.setInterval(() => setTick((value) => value + 1), 1000);
    return () => window.clearInterval(interval);
  }, [clock]);
  if (!clock) return null;

  const elapsed = Math.max(0, (Date.now() - new Date(clock.turnStartedAt).getTime()) / 1000);
  const remaining = { ...clock.remainingSeconds };
  remaining[clock.activeColor] = Math.max(0, remaining[clock.activeColor] - elapsed);
  const format = (seconds) => {
    const normalized = Math.max(0, Math.ceil(seconds));
    return `${Math.floor(normalized / 60)}:${String(normalized % 60).padStart(2, "0")}`;
  };
  return (
    <div className="clock-readout">
      {["white", "black"].map((color) => (
        <span key={color} className={clock.activeColor === color ? "active" : ""}>
          <b>{title(color)}</b><strong>{format(remaining[color])}</strong>
        </span>
      ))}
    </div>
  );
}

function GameStateSummary({ gameStatus, winner, score, abilities, clock }) {
  return (
    <section className="panel-section">
      <h3>Game State</h3>
      <div className="state-summary">
        <span><b>Status</b>{title(gameStatus)}</span>
        <span><b>Winner</b>{title(winner) || "None"}</span>
        <span><b>Score</b>{score?.white ?? 0} / {score?.black ?? 0}</span>
        {abilities?.enabled ? (
          <span><b>Abilities</b>{title(abilities.selected?.white) || "Hidden"} / {title(abilities.selected?.black) || "Hidden"}</span>
        ) : null}
      </div>
      <MatchClock clock={clock} />
    </section>
  );
}

function CapturedPieces({ capturedPieces }) {
  return (
    <section className="panel-section">
      <h3>Captured Pieces</h3>
      <div className="captures-row">
        {["white", "black"].map((color) => {
          const pieces = capturedPieces?.[color] || [];
          return (
            <div key={color}>
              <strong>{title(color)}</strong>
              <p className="captured-glyphs">
                {pieces.length ? pieces.map((piece) => (
                  <PieceGlyph key={piece.pieceId} piece={piece} />
                )) : <span>None</span>}
              </p>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function AbilityLoadouts({ abilities }) {
  if (!abilities?.enabled || !abilities.selected) return null;
  return (
    <section className="panel-section ability-loadouts">
      <h3>Player Abilities</h3>
      {["white", "black"].map((color) => {
        const ability = abilities.selected[color];
        const cooldown = abilities.cooldowns?.[color]?.[ability] || 0;
        const uses = abilities.usageCount?.[color]?.[ability] || 0;
        return (
          <div key={color}>
            <span><b>{title(color)}</b><strong>{title(ability) || "Hidden"}</strong></span>
            <small>{ability === "locked" ? "Locked" : cooldown ? `${cooldown} own turns` : "Ready"}</small>
            {uses ? <em>{uses} use{uses === 1 ? "" : "s"}</em> : null}
          </div>
        );
      })}
    </section>
  );
}

function CountdownPanel({ countdowns = [] }) {
  if (!countdowns.length) return null;
  return (
    <section className="panel-section countdown-panel">
      <div className="panel-heading-row"><h3>Live Effects</h3><span>{countdowns.length}</span></div>
      <div className="countdown-groups">
        {["white", "black"].map((color) => {
          const items = countdowns.filter((item) => item.owner === color);
          if (!items.length) return null;
          return (
            <div key={color}>
              <h4>{title(color)}</h4>
              {items.map((item) => (
                <article key={item.id}>
                  <i>{item.icon}</i>
                  <span><strong>{item.pieceName ? `${item.pieceName}: ${item.label}` : item.label}</strong><small>{item.description}</small></span>
                  <b>{item.remainingTurns}<small> turn{item.remainingTurns === 1 ? "" : "s"}</small></b>
                </article>
              ))}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function ActionPanel({ actions = [], onAction, actionLoading, boardRows }) {
  const groups = useMemo(() => {
    const result = new Map();
    actions.forEach((action) => result.set(action.actionType, [...(result.get(action.actionType) || []), action]));
    return [...result.entries()];
  }, [actions]);
  if (!groups.length) return null;
  return (
    <section className="panel-section action-panel">
      <h3>Special Actions</h3>
      {groups.map(([type, options]) => (
        <details key={type} open={groups.length === 1}>
          <summary><span>{options[0].icon} {title(type)}</span><b>{options.length}</b></summary>
          <div className="action-option-list">
            {options.map((action) => (
              <button type="button" key={action.id} disabled={actionLoading} onClick={() => onAction(action)}>
                <strong>{action.label}</strong>
                <small>{action.source ? `${squareLabel(action.source, boardRows)} → ` : ""}{action.target ? squareLabel(action.target, boardRows) : ""}</small>
                <span>{action.description}</span>
              </button>
            ))}
          </div>
        </details>
      ))}
    </section>
  );
}

function RuleEffectsReference({ rules = [], pieceDefinitions = [], abilities }) {
  const specialRules = rules.filter((rule) => rule.isSpecial || rule.tier !== "basic");
  const customPieces = pieceDefinitions.filter((piece) => piece.isCustom);
  if (!specialRules.length && !customPieces.length && !abilities?.enabled) return null;
  return (
    <details className="panel-section all-effects-reference">
      <summary>All Rules And Effects</summary>
      {specialRules.length ? (
        <div><h4>Special Rules</h4>{specialRules.map((rule) => <p key={rule.id}><b>{rule.name}</b><span>{rule.enabled ? "Enabled" : "Disabled"}</span><small>{rule.description}</small></p>)}</div>
      ) : null}
      {customPieces.length ? (
        <div><h4>Custom Pieces</h4>{customPieces.map((piece) => <p key={piece.type}><b>{piece.displayName}</b><small>{piece.movement}</small></p>)}</div>
      ) : null}
      {abilities?.enabled ? (
        <div><h4>Allowed Abilities</h4>{abilities.allowed.map((ability) => <p key={ability}><b>{title(ability)}</b><small>{Object.values(abilities.selected || {}).includes(ability) ? "Selected in this match" : "Available at setup"}</small></p>)}</div>
      ) : null}
    </details>
  );
}

function ActiveSpecialRules({ rules = [] }) {
  const active = rules.filter((rule) => rule.enabled && (rule.isSpecial || rule.tier !== "basic"));
  if (!active.length) return null;
  return (
    <section className="panel-section active-special-rules">
      <h3>Special Rules</h3>
      {active.map((rule) => <p key={rule.id}><strong>{rule.name}</strong><small>{rule.description}</small></p>)}
    </section>
  );
}

export function EffectsPanel({ game, onAction, actionLoading, children }) {
  return (
    <aside className="effects-panel">
      {children}
      <AbilityLoadouts abilities={game.abilities} />
      <CountdownPanel countdowns={game.countdowns} />
      <ActionPanel actions={game.availableActions} onAction={onAction} actionLoading={actionLoading} boardRows={game.boardRows ?? game.boardSize} />
      <ActiveSpecialRules rules={game.rules} />
      <RuleEffectsReference rules={game.rules} pieceDefinitions={game.pieceDefinitions} abilities={game.abilities} />
    </aside>
  );
}

export function GameInfoPanel({ game }) {
  return (
    <aside className="history-panel">
      <GameStateSummary gameStatus={game.gameStatus} winner={game.winner} score={game.score} abilities={game.abilities} clock={game.clock} />
      <CapturedPieces capturedPieces={game.capturedPieces} />
      <section className="panel-section history-section">
        <h3>Move History</h3>
        {game.lastMoveExplanation ? <p className="move-explanation">{game.lastMoveExplanation}</p> : null}
        <ol>{[...(game.history || [])].reverse().map((move) => <li key={move.moveNumber}><span>{move.moveNumber}. {move.actionType === "move" ? title(move.piece) : title(move.actionType)} ({title(move.player)})</span><small>{move.explanation}</small></li>)}</ol>
      </section>
    </aside>
  );
}

export default GameInfoPanel;
