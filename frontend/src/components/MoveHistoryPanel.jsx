import { useEffect, useMemo, useState } from "react";

function title(value) {
  return value ? value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()) : "";
}

function squareLabel(position, rows = 8) {
  if (!position) return "";
  return `${String.fromCharCode(65 + position.col)}${rows - position.row}`;
}

function CapturedPieces({ capturedPieces }) {
  const whiteCaptures = capturedPieces?.white || [];
  const blackCaptures = capturedPieces?.black || [];
  return (
    <section className="panel-section">
      <h3>Captured Pieces</h3>
      <div className="captures-row">
        <div><strong>White</strong><p>{whiteCaptures.map((piece) => piece.symbol).join(" ") || "-"}</p></div>
        <div><strong>Black</strong><p>{blackCaptures.map((piece) => piece.symbol).join(" ") || "-"}</p></div>
      </div>
    </section>
  );
}

function ActiveRules({ rules, compact }) {
  const activeRules = rules.filter((rule) => rule.enabled);
  const list = <ul className="rule-list">{activeRules.map((rule) => <li key={rule.id}><span>{rule.name}</span><small>{rule.tier}</small></li>)}</ul>;
  if (compact) return <details className="panel-section compact-rules"><summary>Active Rules ({activeRules.length})</summary>{list}</details>;
  return <section className="panel-section"><h3>Active Rules</h3>{list}</section>;
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
    <section className="panel-section clock-panel">
      <h3>Match Clock</h3>
      <div>{["white", "black"].map((color) => <span key={color} className={clock.activeColor === color ? "active" : ""}><b>{title(color)}</b><strong>{format(remaining[color])}</strong></span>)}</div>
    </section>
  );
}

function GameStateSummary({ gameStatus, winner, score, abilities }) {
  return (
    <section className="panel-section">
      <h3>Game State</h3>
      <div className="state-summary">
        <span>Status: {title(gameStatus)}</span>
        <span>Winner: {title(winner) || "-"}</span>
        <span>Score W/B: {score?.white ?? 0} / {score?.black ?? 0}</span>
        {abilities?.enabled && abilities.selected ? (
          <span>
            Abilities: {title(abilities.selected.white) || "Hidden"} / {title(abilities.selected.black) || "Hidden"}
          </span>
        ) : null}
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
        const used = abilities.used?.[color];
        return (
          <div key={color}>
            <span><b>{title(color)}</b><strong>{title(ability) || "Hidden"}</strong></span>
            <small>{ability === "locked" ? "Choice locked" : used ? "Used" : "Ready"}</small>
          </div>
        );
      })}
    </section>
  );
}

function CountdownPanel({ countdowns = [] }) {
  return (
    <section className="panel-section countdown-panel">
      <div className="panel-heading-row"><h3>Live Effects</h3><span>{countdowns.length}</span></div>
      <p className="panel-helper">Both players can see every active recovery and timed effect.</p>
      {countdowns.length === 0 ? <p className="empty-panel-copy">No active countdowns.</p> : (
        <div className="countdown-groups">
          {["white", "black"].map((color) => {
            const items = countdowns.filter((item) => item.owner === color);
            if (!items.length) return null;
            return <div key={color}><h4>{title(color)}</h4>{items.map((item) => <article key={item.id}><i>{item.icon}</i><span><strong>{item.pieceName ? `${item.pieceName}: ${item.label}` : item.label}</strong><small>{item.description}</small></span><b>{item.remainingTurns}<small> turn{item.remainingTurns === 1 ? "" : "s"}</small></b></article>)}</div>;
          })}
        </div>
      )}
    </section>
  );
}

function ActionPanel({ actions = [], onAction, actionLoading, boardRows }) {
  const groups = useMemo(() => {
    const result = new Map();
    actions.forEach((action) => {
      const list = result.get(action.actionType) || [];
      list.push(action);
      result.set(action.actionType, list);
    });
    return [...result.entries()];
  }, [actions]);
  if (!groups.length) return null;
  return (
    <section className="panel-section action-panel">
      <h3>Available Special Actions</h3>
      <p className="panel-helper">Using one of these consumes your normal turn.</p>
      {groups.map(([type, options]) => (
        <details key={type} open={groups.length === 1}>
          <summary><span>{options[0].icon} {title(type)}</span><b>{options.length}</b></summary>
          <div className="action-option-list">
            {options.map((action) => (
              <button type="button" key={action.id} disabled={actionLoading} onClick={() => onAction(action)}>
                <strong>{action.label}</strong>
                <small>
                  {action.source ? `${squareLabel(action.source, boardRows)} → ` : ""}
                  {action.target ? squareLabel(action.target, boardRows) : ""}
                </small>
                <span>{action.description}</span>
              </button>
            ))}
          </div>
        </details>
      ))}
    </section>
  );
}

function MoveHistoryPanel({
  rules,
  history,
  capturedPieces,
  lastMoveExplanation,
  gameStatus,
  winner,
  score,
  abilities,
  countdowns,
  availableActions,
  clock,
  onAction,
  actionLoading,
  boardRows,
  compactRules = false,
}) {
  return (
    <aside className="history-panel">
      <GameStateSummary gameStatus={gameStatus} winner={winner} score={score} abilities={abilities} />
      <AbilityLoadouts abilities={abilities} />
      <MatchClock clock={clock} />
      <CountdownPanel countdowns={countdowns} />
      <ActionPanel actions={availableActions} onAction={onAction} actionLoading={actionLoading} boardRows={boardRows} />
      <ActiveRules rules={rules} compact={compactRules} />
      <CapturedPieces capturedPieces={capturedPieces} />
      <section className="panel-section history-section">
        <h3>Move History</h3>
        {lastMoveExplanation ? <p className="move-explanation">{lastMoveExplanation}</p> : null}
        <ol>{[...history].reverse().map((move) => <li key={move.moveNumber}><span>{move.moveNumber}. {move.actionType === "move" ? title(move.piece) : title(move.actionType)} ({title(move.player)})</span><small>{move.explanation}</small></li>)}</ol>
      </section>
    </aside>
  );
}

export default MoveHistoryPanel;
