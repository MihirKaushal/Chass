import { useEffect, useMemo, useState } from "react";

import PieceGlyph from "./PieceGlyph";

function title(value) {
  return value ? value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()) : "";
}

function label(value) {
  return title(String(value).replace(/([a-z0-9])([A-Z])/g, "$1 $2"));
}

function formatValue(value) {
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) return value.map(label).join(", ");
  if (value && typeof value === "object") return JSON.stringify(value);
  return label(value);
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

function EffectDisclosure({ title: heading, itemKeys, children, emptyDescription }) {
  const hasItems = itemKeys.length > 0;
  const signature = itemKeys.join("|");
  const [open, setOpen] = useState(hasItems);

  useEffect(() => {
    setOpen(hasItems);
  }, [hasItems, signature]);

  return (
    <details
      className={`panel-section effect-disclosure ${hasItems ? "has-enabled-effects" : "is-empty"}`}
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>
        <span>{heading}</span>
        <small>{hasItems ? `${itemKeys.length} Enabled` : "None Enabled"}</small>
      </summary>
      {hasItems ? children : <p className="effect-empty-state">{emptyDescription}</p>}
    </details>
  );
}

function SpecialRulesDisclosure({ game }) {
  const activeRules = (game.rules || []).filter(
    (rule) => rule.enabled && (rule.isSpecial || rule.tier !== "basic")
  );
  return (
    <EffectDisclosure
      title="Special Rules"
      itemKeys={activeRules.map((rule) => rule.id)}
      emptyDescription="No special rules are enabled for this match."
    >
      <div className="effect-disclosure-list">
        {activeRules.map((rule) => {
          const configuredVictory = rule.id === "configured_victory"
            ? Object.fromEntries(
                Object.entries(game.configuration?.victory || {}).filter(
                  ([key, value]) => key !== "mode" && value != null
                )
              )
            : {};
          const params = Object.entries({ ...configuredVictory, ...(rule.params || {}) });
          return (
            <article className="effect-reference-card" key={rule.id}>
              <header><strong>{rule.name}</strong><span>Enabled</span></header>
              <p>{rule.description}</p>
              {params.length ? (
                <dl className="effect-metadata">
                  {params.map(([key, value]) => (
                    <div key={key}><dt>{label(key)}</dt><dd>{formatValue(value)}</dd></div>
                  ))}
                </dl>
              ) : null}
            </article>
          );
        })}
      </div>
    </EffectDisclosure>
  );
}

function CustomPiecesDisclosure({ game }) {
  const enabledTypes = new Set(game.configuration?.enabledPieces || []);
  const customPieces = (game.pieceDefinitions || []).filter(
    (piece) => piece.isCustom && enabledTypes.has(piece.type)
  );
  const boardPieces = (game.board || []).flat().filter(Boolean);

  return (
    <EffectDisclosure
      title="Custom Pieces"
      itemKeys={customPieces.map((piece) => piece.type)}
      emptyDescription="No custom pieces are enabled for this match."
    >
      <div className="effect-disclosure-list">
        {customPieces.map((piece) => {
          const pieceIds = new Set(
            boardPieces.filter((boardPiece) => boardPiece.type === piece.type).map((boardPiece) => boardPiece.pieceId)
          );
          const countdowns = (game.countdowns || []).filter(
            (countdown) => countdown.kind === piece.type || pieceIds.has(countdown.pieceId)
          );
          const rules = piece.customAttributes?.rules || [];
          return (
            <article className="effect-reference-card" key={piece.type}>
              <header className="effect-piece-heading">
                <span><PieceGlyph piece={{ ...piece, color: "black", name: piece.displayName }} /><strong>{piece.displayName}</strong></span>
                <b>{piece.points == null ? "No Point Value" : `${piece.points} Point${piece.points === 1 ? "" : "s"}`}</b>
              </header>
              <p>{piece.description}</p>
              <small className="effect-movement"><b>Movement</b>{piece.movement}</small>
              {rules.length ? <small className="effect-rule-copy"><b>Behavior</b>{rules.join(" · ")}</small> : null}
              {countdowns.map((countdown) => (
                <div className="effect-live-status" key={countdown.id}>
                  <span>{title(countdown.owner)}: {countdown.label}</span>
                  <b>{countdown.remainingTurns} turn{countdown.remainingTurns === 1 ? "" : "s"}</b>
                </div>
              ))}
            </article>
          );
        })}
      </div>
    </EffectDisclosure>
  );
}

function SpecialAbilitiesDisclosure({ abilities, catalog }) {
  const selected = abilities?.selected || {};
  const abilityIds = [...new Set(
    Object.values(selected).filter((abilityId) => abilityId && abilityId !== "locked")
  )];
  const definitions = new Map(
    (catalog?.specialAbilities || []).map((ability) => [ability.id, ability])
  );

  return (
    <EffectDisclosure
      title="Special Abilities"
      itemKeys={abilityIds}
      emptyDescription="No special abilities are enabled for this match."
    >
      <div className="effect-disclosure-list">
        {abilityIds.map((abilityId) => {
          const definition = definitions.get(abilityId);
          const owners = ["white", "black"].filter((color) => selected[color] === abilityId);
          return (
            <article className="effect-reference-card" key={abilityId}>
              <header>
                <strong>{definition?.icon ? `${definition.icon} ` : ""}{definition?.name || title(abilityId)}</strong>
                {definition?.usageLimit ? <span>{definition.usageLimit === 1 ? "One Use" : `${definition.usageLimit} Uses`}</span> : definition?.cooldownTurns ? <span>{definition.cooldownTurns}-Turn Cooldown</span> : <span>Enabled</span>}
              </header>
              <p>{definition?.summary || "A selected special ability for this match."}</p>
              <div className="ability-owner-statuses">
                {owners.map((color) => {
                  const remaining = abilities.cooldowns?.[color]?.[abilityId] || 0;
                  const uses = abilities.usageCount?.[color]?.[abilityId] || 0;
                  return (
                    <div key={color}>
                      <strong>{title(color)}</strong>
                      <span>{remaining ? `${remaining} own turns remaining` : definition?.usageLimit && uses >= definition.usageLimit ? "Used" : "Ready"}</span>
                      <small>{uses} use{uses === 1 ? "" : "s"}</small>
                    </div>
                  );
                })}
              </div>
            </article>
          );
        })}
      </div>
    </EffectDisclosure>
  );
}

function EnabledEffects({ game, catalog }) {
  return (
    <div className="enabled-effects" aria-label="Enabled match options">
      <SpecialRulesDisclosure game={game} />
      <CustomPiecesDisclosure game={game} />
      <SpecialAbilitiesDisclosure abilities={game.abilities} catalog={catalog} />
    </div>
  );
}

export function EffectsPanel({ game, catalog, onAction, actionLoading, children }) {
  return (
    <aside className="effects-panel">
      {children}
      <CountdownPanel countdowns={game.countdowns} />
      <ActionPanel actions={game.availableActions} onAction={onAction} actionLoading={actionLoading} boardRows={game.boardRows ?? game.boardSize} />
      <EnabledEffects game={game} catalog={catalog} />
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
