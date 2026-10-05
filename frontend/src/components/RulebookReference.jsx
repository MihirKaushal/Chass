import { useEffect, useState } from "react";

import { matchesRulebookSearch } from "../rulebookSearch";
import {
  effectiveCatalogEntry,
  parameterDefaults,
  parameterValueLabel,
} from "../variantTuning";
import PieceGlyph from "./PieceGlyph";
import Disclosure from "./ui/Disclosure";
import EmptyState from "./ui/EmptyState";

const STANDARD_TYPES = ["pawn", "knight", "bishop", "rook", "queen", "king"];

function referenceDraft(catalog) {
  return {
    enabledPieces: [...STANDARD_TYPES],
    pieceParameters: parameterDefaults(catalog.pieces),
    pointValues: Object.fromEntries(
      catalog.pieces.map((piece) => [piece.type, Math.max(0, piece.points ?? 0)])
    ),
    victory: { mode: "checkmate" },
    customRules: {
      affinityEnabled: false,
      affinitySquareCount: 4,
      affinityControlRequired: 2,
      commandPointCap: 3,
    },
    specialAbilities: {
      enabled: false,
      allowed: [],
      parameters: parameterDefaults(catalog.specialAbilities, { rows: 8, cols: 8 }),
    },
    gambit: { enabled: false },
  };
}

function DefaultMarker({ visible = false }) {
  return visible ? <small className="rulebook-default-marker">Default</small> : null;
}

function ConfiguredParameterList({ parameters, markDefaults = false }) {
  if (!parameters?.length) return null;
  return (
    <dl className="configured-parameter-list">
      {parameters.map((parameter) => (
        <div key={parameter.id}>
          <dt>{parameter.label}</dt>
          <dd>
            <span>{parameterValueLabel(parameter)}</span>
            <DefaultMarker visible={markDefaults} />
          </dd>
        </div>
      ))}
    </dl>
  );
}

function RulebookSection({
  id,
  title: heading,
  description,
  className = "",
  revealKey = "",
  children,
}) {
  const [open, setOpen] = useState(true);

  useEffect(() => {
    if (revealKey) setOpen(true);
  }, [revealKey]);

  return (
    <Disclosure
      className={`rulebook-section rulebook-disclosure ${className}`.trim()}
      id={id}
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
      summary={<div><h3>{heading}</h3><p>{description}</p></div>}
      summaryClassName="rulebook-section-heading"
      bodyClassName="rulebook-disclosure-body"
    >
      {children}
    </Disclosure>
  );
}

function RulebookReference({ catalog, draft: suppliedDraft, predictorProfile = null }) {
  const draft = suppliedDraft || referenceDraft(catalog);
  const markDefaults = !suppliedDraft;
  const [query, setQuery] = useState("");
  const [enabledOnly, setEnabledOnly] = useState(false);
  const effectivePieces = catalog.pieces.map((piece) => effectiveCatalogEntry(
    piece,
    draft.pieceParameters[piece.type]
  ));
  const visiblePieces = effectivePieces.filter((piece) => (
    (!enabledOnly || draft.enabledPieces.includes(piece.type))
    && matchesRulebookSearch(
      query,
      piece,
      `${draft.pointValues[piece.type] ?? 0} points`
    )
  ));
  const visibleVictoryModes = catalog.victoryModes.filter((mode) => (
    (!enabledOnly || draft.victory.mode === mode.id)
    && matchesRulebookSearch(query, mode)
  ));
  const analysisEngineCopy = [
    "Match Analysis",
    "Stockfish 18",
    "Fairy-Stockfish",
    "Chass Engine",
    "engine analysis probability parity legal moves terminal outcomes custom pieces abilities",
    predictorProfile,
  ];
  const chessBotCopy = [
    "Classic Chess Bots",
    "Play against Stockfish 18 at seven estimated strengths from 500 through 2500 Elo.",
    "Lower levels use controlled move variation. Stronger levels use Stockfish native strength limits.",
    "Fairy-Stockfish Bots",
    "Verified static variants use three conservative estimated strengths from 500 through 1000 Elo.",
    "Fairy supports standard pieces and movement on boards up to 10x12 with Checkmate, Royal Center, or Check Race.",
    "Chass Engine Bots",
    "All remaining valid games use conservative estimated strengths of 500 and 800.",
    "The native bot understands custom pieces, abilities, terrain, Affinity Squares, Gambit setup, command powers, and alternate win conditions.",
    "The Chass Rule Engine remains authoritative for legal moves, check, checkmate, history, and rematches.",
    "computer opponent beginner learner developing intermediate advanced expert master static custom universal variant parity",
  ];
  const showAnalysisEngines = matchesRulebookSearch(query, analysisEngineCopy);
  const showChessBots = matchesRulebookSearch(query, chessBotCopy);
  const affinityCopy = [
    "Affinity Squares",
    `The board marks ${draft.customRules.affinitySquareCount} centered squares, divided equally between White and Black.`,
    `Hold ${draft.customRules.affinityControlRequired} of your ${draft.customRules.affinitySquareCount / 2} assigned squares through the opponent's turn to earn one command point.`,
    "Spend one point for a Pawn, two to evolve a Pawn, or three for a Rook. A command uses the normal turn and must leave the King safe.",
    "Affinity Square Count",
    "Squares Required",
    "Command Point Cap",
    `The cap controls how many unused command points a player may save. The current cap is ${draft.customRules.commandPointCap}.`,
    "Marked center squares must begin empty; only Barricades may start there.",
  ];
  const showAffinity = (!enabledOnly || draft.customRules.affinityEnabled)
    && matchesRulebookSearch(query, affinityCopy);
  const effectiveAbilities = catalog.specialAbilities.map((ability) => effectiveCatalogEntry(
    ability,
    draft.specialAbilities.parameters[ability.id]
  ));
  const visibleAbilities = effectiveAbilities.filter((ability) => (
    (
      !enabledOnly
      || (
        draft.specialAbilities.enabled
        && draft.specialAbilities.allowed.includes(ability.id)
      )
    )
    && matchesRulebookSearch(query, ability)
  ));
  const showGambit = (!enabledOnly || draft.gambit.enabled)
    && matchesRulebookSearch(query, catalog.gambit, "Draft Gambit");
  const enabledTimedEntries = [
    ...effectivePieces.filter((piece) => draft.enabledPieces.includes(piece.type)),
    ...effectiveAbilities.filter((ability) => (
      draft.specialAbilities.enabled
      && draft.specialAbilities.allowed.includes(ability.id)
    )),
  ].some((entry) => ["round", "cooldown", "recharge", "duration", "rest"].some(
    (term) => matchesRulebookSearch(
      term,
      entry.configuredParameters,
      entry.rules,
      entry.details
    )
  ));
  const countdownCopy = "Countdowns decrease when the affected player completes a turn. Both players see active timers in the Play sidebar and in piece details.";
  const showCountdowns = (!enabledOnly || enabledTimedEntries)
    && matchesRulebookSearch(query, "Turns And Countdowns", countdownCopy);
  const resultCount = visiblePieces.length
    + Number(showAnalysisEngines)
    + Number(showChessBots)
    + visibleVictoryModes.length
    + Number(showAffinity)
    + visibleAbilities.length
    + Number(showGambit)
    + Number(showCountdowns);
  const revealKey = query || (enabledOnly ? "enabled" : "");

  return (
    <section className="rulebook rulebook-reference" id="rulebook">
      <header className="rulebook-hero rulebook-reference-hero">
        <div className="rulebook-reference-heading">
          <div className="rulebook-hero-copy">
            <span className="eyebrow">Complete Reference</span>
            <h2>The Chass Rulebook</h2>
            <p>Detailed behavior for every engine, bot, piece, win condition, ability, and Gambit system.</p>
          </div>
          <nav aria-label="Rulebook sections">
            <a href="#rulebook-match-analysis">Match Analysis</a>
            <a href="#rulebook-bots">Chess Bots</a>
            <a href="#rulebook-pieces">Pieces</a>
            <a href="#rulebook-victory">Win Conditions</a>
            <a href="#rulebook-custom-rules">Custom Rules</a>
            <a href="#rulebook-abilities">Abilities</a>
            <a href="#rulebook-gambit">Gambit</a>
          </nav>
        </div>
        <div className="rulebook-search-column">
          <div className="rulebook-search-tools">
            <label className="rulebook-search">
              <span className="visually-hidden">Search the rulebook</span>
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search engines, bots, pieces, rules, or abilities"
              />
              {query ? <button type="button" onClick={() => setQuery("")} aria-label="Clear rulebook search">Clear</button> : null}
            </label>
            <label className="rulebook-enabled-filter">
              <input
                type="checkbox"
                checked={enabledOnly}
                onChange={(event) => setEnabledOnly(event.target.checked)}
              />
              <span>{suppliedDraft ? "Enabled Only" : "Classic Defaults Only"}</span>
            </label>
            {(query || enabledOnly) ? <small>{resultCount} reference{resultCount === 1 ? "" : "s"} shown</small> : null}
          </div>
        </div>
      </header>

      {markDefaults ? (
        <p className="rulebook-default-note">
          <DefaultMarker visible /> marks the starting value. These values can be changed in the Game Customizer.
        </p>
      ) : null}

      <RulebookSection id="rulebook-match-analysis" title="Match Analysis" description="How Chass selects an engine and where each estimate is reliable." revealKey={revealKey}>
        {showAnalysisEngines ? (
          <div className="predictor-reference-grid">
            <article className={predictorProfile?.engineId === "stockfish" ? "is-selected" : ""}>
              <header><strong>Stockfish 18</strong><span>Preferred</span></header>
              <p><b>Strengths:</b> Elite standard-chess search, NNUE evaluation, and mature W/D/L estimates. Chass uses it first for compatible standard-rule 8x8 positions, including validated custom formations.</p>
              <p><b>Limits:</b> It cannot model larger boards, custom movement, Chass abilities, terrain, Affinity, or stateful variant rules.</p>
            </article>
            <article className={predictorProfile?.engineId === "fairy-stockfish" ? "is-selected" : ""}>
              <header><strong>Fairy-Stockfish</strong><span>Experimental</span></header>
              <p><b>Strengths:</b> Supports deterministic static variants on boards up to 10x12. Chass generates its profile and verifies legal moves and terminal behavior against the Rule Engine.</p>
              <p><b>Limits:</b> Its outcome percentages are not calibrated on Chass games and are less trustworthy than Stockfish for standard chess. Stateful pieces, abilities, terrain, Affinity, and Gambit setup remain unsupported.</p>
            </article>
            <article className={predictorProfile?.engineId === "chass" ? "is-selected" : ""}>
              <header><strong>Chass Engine</strong><span>Universal</span></header>
              <p><b>Strengths:</b> Evaluates every valid Chass configuration through the same Rule Engine used for gameplay, including custom-piece settings, abilities, terrain, Affinity, runtime effects, and alternate win conditions.</p>
              <p><b>Limits:</b> Its handcrafted evaluation and time-bounded search are experimental. It is weaker than Stockfish and is not trained on self-play data, so Chass reports a position-advantage share rather than a win probability.</p>
            </article>
            {predictorProfile ? (
              <p className="predictor-reference-current">
                Current configuration: <strong>{predictorProfile.engineName || "No compatible engine"}</strong>. {predictorProfile.accuracy || predictorProfile.reason || "Finish configuring the game to see automatic engine selection."}
              </p>
            ) : null}
          </div>
        ) : <EmptyState className="rulebook-empty">No matching Match Analysis reference.</EmptyState>}
      </RulebookSection>

      <RulebookSection id="rulebook-bots" title="Chess Bots" description="Computer opponents, estimated difficulty, and current compatibility." revealKey={revealKey}>
        {showChessBots ? (
          <div className="predictor-reference-grid bot-reference-grid">
            <article>
              <header><strong>Classic Chess Bots</strong><span>Stockfish 18</span></header>
              <p>Play against Stockfish 18 at seven estimated strengths from 500 through 2500 Elo. Lower levels use controlled move variation, while stronger levels use Stockfish's native strength limits.</p>
              <p>Stockfish is preferred for the exact 8x8 Classic Chass opening. It selects from Chass-approved moves, while the Rule Engine remains authoritative.</p>
            </article>
            <article>
              <header><strong>Static Variant Bots</strong><span>Fairy-Stockfish</span></header>
              <p>Verified static variants offer conservative estimated levels of 500, 800, and 1000. These ratings describe relative difficulty and are not calibrated across every board or win condition.</p>
              <p>Supported games use unchanged standard pieces and movement on boards up to 10x12 with Checkmate, Royal Center, or Check Race. Every starting position and bot turn must match Chass legal-move and terminal parity.</p>
            </article>
            <article>
              <header><strong>Custom Variant Bots</strong><span>Chass Engine</span></header>
              <p>Every other valid game offers experimental estimated levels of 500 and 800. The stronger profile searches more candidate actions and replies, but both remain intentionally below Stockfish strength.</p>
              <p>The bot can build Gambit armies, draft pieces, choose abilities, and use legal custom-piece actions, special abilities, command powers, terrain, Affinity Squares, and alternate win conditions through the same Rule Engine as human players.</p>
              <p>If an external bot becomes unavailable or loses rule parity during play, Chass Engine takes over through the same versioned game transaction so the match can continue.</p>
            </article>
          </div>
        ) : <EmptyState className="rulebook-empty">No matching Chess Bots reference.</EmptyState>}
      </RulebookSection>

      <RulebookSection id="rulebook-pieces" title="Piece Encyclopedia" description="Movement, value, and special behavior." revealKey={revealKey}>
        <div className="rulebook-entry-grid">
          {visiblePieces.map((effectivePiece) => (
            <details className="rulebook-entry" key={effectivePiece.type}>
              <summary>
                <span className="entry-icon"><PieceGlyph type={effectivePiece.type} color="black" symbol={effectivePiece.symbols.black || effectivePiece.icon} /></span>
                <span><strong>{effectivePiece.name}</strong><small>{effectivePiece.isCustom ? "Custom Piece" : "Classic Piece"}</small></span>
                <b>
                  <span>{draft.pointValues[effectivePiece.type] ?? 0} pts</span>
                  <DefaultMarker visible={markDefaults} />
                </b>
              </summary>
              <p>{effectivePiece.description}</p>
              <h4>Movement</h4>
              <p>{effectivePiece.movement}</p>
              <ConfiguredParameterList
                parameters={effectivePiece.configuredParameters}
                markDefaults={markDefaults}
              />
              {effectivePiece.rules.length ? <ul>{effectivePiece.rules.map((rule) => <li key={rule}>{rule}</li>)}</ul> : null}
            </details>
          ))}
        </div>
        {!visiblePieces.length ? <EmptyState className="rulebook-empty">No matching pieces in this configuration.</EmptyState> : null}
      </RulebookSection>

      <RulebookSection id="rulebook-victory" title="Win Conditions" description="What ends a match and decides its result." revealKey={revealKey}>
        <div className="rulebook-strip">
          {visibleVictoryModes.map((mode) => <div key={mode.id}><i>{mode.icon}</i><strong>{mode.name}</strong><p>{mode.summary}</p></div>)}
        </div>
        {!visibleVictoryModes.length ? <EmptyState className="rulebook-empty">No matching win conditions in this configuration.</EmptyState> : null}
      </RulebookSection>

      <RulebookSection id="rulebook-custom-rules" title="Custom Rules" description="Optional board-wide systems that work with any compatible match." revealKey={revealKey}>
        {showAffinity ? <div className="rulebook-gambit-copy">
          <div>
            <h4>Affinity Squares</h4>
            <p>The board marks a configurable group of centered squares, divided equally between both colors.</p>
            <p>Hold the configured number of your assigned squares through the opponent&apos;s turn to earn one command point.</p>
            <p>Spend one point for a Pawn, two to evolve a Pawn, or three for a Rook. A command uses the normal turn and must leave the King safe.</p>
            <p>Marked center squares must begin empty; only Barricades may start there.</p>
          </div>
          <div>
            <h4>Configuration</h4>
            <p><strong>Affinity squares:</strong> {draft.customRules.affinitySquareCount} total. <DefaultMarker visible={markDefaults} /></p>
            <p><strong>Squares required:</strong> {draft.customRules.affinityControlRequired} per player. <DefaultMarker visible={markDefaults} /></p>
            <p><strong>Command point cap:</strong> {draft.customRules.commandPointCap}. <DefaultMarker visible={markDefaults} /> This limits how many unused points a player may save.</p>
          </div>
        </div> : <EmptyState className="rulebook-empty">No matching custom rules in this configuration.</EmptyState>}
      </RulebookSection>

      <RulebookSection id="rulebook-abilities" title="Special Ability Codex" description="Each player privately chooses the configured number of enabled abilities." revealKey={revealKey}>
        <div className="rulebook-entry-grid">
          {visibleAbilities.map((effectiveAbility) => (
            <details className="rulebook-entry ability-entry" key={effectiveAbility.id}>
              <summary><span className="entry-icon">{effectiveAbility.icon}</span><span><strong>{effectiveAbility.name}</strong><small>Player ability</small></span></summary>
              <p>{effectiveAbility.summary}</p>
              <ConfiguredParameterList
                parameters={effectiveAbility.configuredParameters}
                markDefaults={markDefaults}
              />
              <ul>{effectiveAbility.details.map((detail) => <li key={detail}>{detail}</li>)}</ul>
            </details>
          ))}
        </div>
        {!visibleAbilities.length ? <EmptyState className="rulebook-empty">No matching abilities in this configuration.</EmptyState> : null}
      </RulebookSection>

      <RulebookSection id="rulebook-gambit" title={`${catalog.gambit.icon} ${catalog.gambit.name}`} description={catalog.gambit.summary} revealKey={revealKey}>
        {showGambit ? <div className="rulebook-gambit-copy">
          <ol>{catalog.gambit.details.map((detail) => <li key={detail}>{detail}</li>)}</ol>
          <div>
            <h4>Draft Gambit</h4>
            <ol>{catalog.gambit.draftDetails.map((detail) => <li key={detail}>{detail}</li>)}</ol>
          </div>
        </div> : <EmptyState className="rulebook-empty">No matching Gambit rules in this configuration.</EmptyState>}
      </RulebookSection>

      <RulebookSection title="Turns And Countdowns" description="How timed effects are counted." className="countdown-reference" revealKey={revealKey}>
        {showCountdowns
          ? <p>{countdownCopy}</p>
          : <EmptyState className="rulebook-empty">No matching countdown rules in this configuration.</EmptyState>}
      </RulebookSection>
    </section>
  );
}

export default RulebookReference;
