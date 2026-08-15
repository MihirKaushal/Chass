import { useEffect, useMemo, useState } from "react";

import { getCatalog, validateGameConfiguration } from "../api/gameApi";
import { affinitySquares, barricadeSquares, objectiveCenterSquares } from "../boardGeometry";
import {
  effectiveCatalogEntry,
  mergeParameterGroups,
  parameterDefaults,
  parameterValueLabel,
} from "../variantTuning";
import PieceGlyph from "./PieceGlyph";
import PieceTooltip from "./PieceTooltip";

const MIN_DIMENSION = 4;
const MAX_DIMENSION = 16;
const STANDARD_TYPES = ["pawn", "knight", "bishop", "rook", "queen", "king"];
const BACK_RANK = ["rook", "knight", "bishop", "queen", "king", "bishop", "knight", "rook"];
const DEFAULT_DRAFT_POOL = { pawn: 16, knight: 4, bishop: 4, rook: 4, queen: 2, king: 2 };

function title(value) {
  return value ? value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()) : "";
}

function clamp(value, minimum, maximum) {
  const number = Number(value);
  if (!Number.isFinite(number)) return minimum;
  return Math.max(minimum, Math.min(maximum, Math.trunc(number)));
}

function coordinate(row, col, rows) {
  return `${String.fromCharCode(65 + col)}${rows - row}`;
}

function adaptiveBackRank(cols) {
  if (cols >= BACK_RANK.length) return [...BACK_RANK];
  const rank = Array(cols).fill("pawn");
  const cycle = ["rook", "knight", "bishop"];
  let left = 0;
  let right = cols - 1;
  let cycleIndex = 0;
  while (right - left + 1 > 2) {
    rank[left] = cycle[cycleIndex % cycle.length];
    rank[right] = cycle[cycleIndex % cycle.length];
    left += 1;
    right -= 1;
    cycleIndex += 1;
  }
  if (cols % 2 === 0) {
    rank[left] = "queen";
    rank[right] = "king";
  } else {
    rank[left] = "king";
  }
  return rank;
}

function classicLayout(rows, cols) {
  const backRank = adaptiveBackRank(cols);
  const startCol = Math.floor((cols - backRank.length) / 2);
  return backRank.flatMap((type, index) => {
    const col = startCol + index;
    return [
      { row: 0, col, type, color: "black" },
      { row: 1, col, type: "pawn", color: "black" },
      { row: rows - 2, col, type: "pawn", color: "white" },
      { row: rows - 1, col, type, color: "white" },
    ];
  });
}

function centeredResize(placements, oldRows, oldCols, rows, cols) {
  const rowOffset = Math.floor((rows - oldRows) / 2);
  const colOffset = Math.floor((cols - oldCols) / 2);
  return placements
    .filter((piece) => piece.type !== "barricade")
    .map((piece) => ({ ...piece, row: piece.row + rowOffset, col: piece.col + colOffset }))
    .filter((piece) => piece.row >= 0 && piece.row < rows && piece.col >= 0 && piece.col < cols);
}

function defaultDraft(catalog) {
  const pointValues = {};
  const pieceCaps = {};
  const draftPool = {};
  catalog.pieces.forEach((piece) => {
    pointValues[piece.type] = Math.max(0, piece.points ?? 0);
    pieceCaps[piece.type] = piece.type === "king" ? 1 : piece.type === "queen" ? 2 : 16;
    draftPool[piece.type] = piece.type === "barricade"
      ? 0
      : (DEFAULT_DRAFT_POOL[piece.type] ?? 2);
  });
  const pieceParameters = parameterDefaults(catalog.pieces);
  const abilityParameters = parameterDefaults(catalog.specialAbilities);
  return {
    schemaVersion: 2,
    presetId: "classic",
    formationId: "classic",
    barricadeCount: 1,
    boardRows: 8,
    boardCols: 8,
    enabledPieces: [...STANDARD_TYPES],
    pieceParameters,
    pointValues,
    pieceCaps,
    placements: classicLayout(8, 8),
    victory: { mode: "checkmate", targetPoints: 21, timeSeconds: 600, kingPoints: 0, dominionRounds: 3, checkTarget: 3 },
    customRules: { affinityEnabled: false, commandPointCap: 3 },
    specialAbilities: {
      enabled: false,
      allowed: [],
      maxPerPlayer: 1,
      parameters: abilityParameters,
    },
    gambit: {
      enabled: false,
      budget: 39,
      maxPieces: 16,
      setupRows: 2,
      maxQueens: 2,
      draftEnabled: false,
      draftPool,
    },
  };
}

function loadSavedDraft(catalog) {
  const base = defaultDraft(catalog);
  const serialized = window.sessionStorage.getItem("chass-customize-draft");
  if (!serialized) return base;
  window.sessionStorage.removeItem("chass-customize-draft");
  try {
    const saved = JSON.parse(serialized);
    const configuration = saved.configuration || {};
    const gambit = configuration.gambit || {};
    const boardRows = clamp(saved.boardRows ?? base.boardRows, MIN_DIMENSION, MAX_DIMENSION);
    const boardCols = clamp(saved.boardCols ?? base.boardCols, MIN_DIMENSION, MAX_DIMENSION);
    const savedPoints = configuration.piecePoints || {};
    const pointValues = Object.fromEntries(
      catalog.pieces.map((piece) => [
        piece.type,
        clamp(savedPoints[piece.type] ?? base.pointValues[piece.type], 0, catalog.limits.pointMax),
      ])
    );
    return {
      ...base,
      schemaVersion: 2,
      presetId: configuration.presetId || "custom",
      formationId: configuration.formationId || "custom",
      barricadeCount: configuration.barricadeCount ?? base.barricadeCount,
      boardRows,
      boardCols,
      enabledPieces: configuration.enabledPieces || base.enabledPieces,
      pieceParameters: mergeParameterGroups(
        base.pieceParameters,
        configuration.pieceParameters
      ),
      pointValues,
      pieceCaps: { ...base.pieceCaps, ...(gambit.pieceCaps || {}) },
      placements: configuration.initialLayout?.length
        ? configuration.initialLayout
        : classicLayout(boardRows, boardCols),
      victory: { ...base.victory, ...(configuration.victory || {}) },
      customRules: {
        ...base.customRules,
        ...(
          configuration.customRules ||
          (gambit.affinityEnabled !== undefined
            ? {
                affinityEnabled: gambit.affinityEnabled,
                commandPointCap: gambit.commandPointCap ?? 3,
              }
            : {})
        ),
      },
      specialAbilities: {
        ...base.specialAbilities,
        ...(configuration.specialAbilities || {}),
        parameters: mergeParameterGroups(
          base.specialAbilities.parameters,
          configuration.specialAbilities?.parameters
        ),
      },
      gambit: {
        ...base.gambit,
        ...gambit,
        draftPool: { ...base.gambit.draftPool, ...(gambit.draftPool || {}) },
      },
    };
  } catch {
    return base;
  }
}

function formationLayout(catalog, formationId, rows, cols) {
  if (formationId === "classic") return classicLayout(rows, cols);
  return (
    catalog.formations.find((formation) => formation.id === formationId)?.initialLayout ||
    classicLayout(rows, cols)
  );
}

function applyModeToDraft(current, mode, catalog) {
  const defaults = defaultDraft(catalog);
  const rows = mode.boardRows;
  const cols = mode.boardCols;
  const formationId = mode.formationId || "classic";
  const layout = formationLayout(catalog, formationId, rows, cols);
  return {
    ...current,
    presetId: mode.id,
    formationId,
    boardRows: rows,
    boardCols: cols,
    enabledPieces: [...STANDARD_TYPES],
    pieceParameters: defaults.pieceParameters,
    pointValues: {
      ...defaults.pointValues,
      ...(mode.victory?.kingPoints !== undefined
        ? { king: mode.victory.kingPoints }
        : {}),
    },
    pieceCaps: defaults.pieceCaps,
    barricadeCount: defaults.barricadeCount,
    placements: layout,
    victory: { ...current.victory, ...mode.victory },
    customRules: { ...defaults.customRules, ...(mode.customRules || {}) },
    specialAbilities: defaults.specialAbilities,
    gambit: { ...defaults.gambit, enabled: false, draftEnabled: false, ...mode.gambit },
  };
}

function buildRequest(draft, mode = "local") {
  return {
    mode,
    variant: draft.gambit.enabled ? "gambit" : "classic",
    boardRows: draft.boardRows,
    boardCols: draft.boardCols,
    configuration: {
      schemaVersion: 2,
      presetId: draft.presetId,
      formationId: draft.formationId,
      barricadeCount: draft.barricadeCount,
      enabledPieces: draft.enabledPieces,
      piecePoints: Object.fromEntries(
        draft.enabledPieces.map((type) => [type, Number(draft.pointValues[type] ?? 0)])
      ),
      pieceParameters: Object.fromEntries(
        draft.enabledPieces
          .filter((type) => draft.pieceParameters[type])
          .map((type) => [type, draft.pieceParameters[type]])
      ),
      initialLayout: draft.gambit.enabled
        ? []
        : draft.placements.filter((piece) => piece.type !== "barricade"),
      victory: draft.victory,
      customRules: draft.customRules,
      specialAbilities: draft.specialAbilities,
      gambit: {
        ...draft.gambit,
        pieceCaps: Object.fromEntries(
          draft.enabledPieces.map((type) => [
            type,
            Number(draft.pieceCaps[type] ?? draft.gambit.maxPieces),
          ])
        ),
        draftPool: Object.fromEntries(
          draft.enabledPieces
            .filter((type) => type !== "barricade")
            .map((type) => [type, Number(draft.gambit.draftPool[type] ?? 0)])
        ),
      },
    },
  };
}

function previewPiece(placement, definition, points, configuredParameters) {
  if (!placement || !definition) return null;
  const effectiveDefinition = effectiveCatalogEntry(definition, configuredParameters);
  return {
    type: placement.type,
    name: effectiveDefinition.name,
    color: placement.color,
    points,
    symbol: effectiveDefinition.symbols?.[placement.color] || effectiveDefinition.icon || "?",
    icon: effectiveDefinition.icon,
    isCustom: effectiveDefinition.isCustom,
    description: effectiveDefinition.description,
    movement: effectiveDefinition.movement,
    customAttributes: {
      rules: effectiveDefinition.rules || [],
      configuredParameters: effectiveDefinition.configuredParameters || [],
    },
  };
}

function ConfigurationBoard({ draft, catalog, selectedTool, onSelectTool, onPlace, onClearBoard }) {
  const definitionMap = useMemo(
    () => new Map(catalog.pieces.map((piece) => [piece.type, piece])),
    [catalog]
  );
  const placementMap = useMemo(
    () => new Map(draft.placements.map((piece) => [`${piece.row}-${piece.col}`, piece])),
    [draft.placements]
  );
  const setupRows = new Set([
    ...Array.from({ length: Math.min(draft.gambit.setupRows, draft.boardRows) }, (_, index) => index),
    ...Array.from(
      { length: Math.min(draft.gambit.setupRows, draft.boardRows) },
      (_, index) => draft.boardRows - 1 - index
    ),
  ]);
  const barricadeMap = new Map(
    (draft.enabledPieces.includes("barricade")
      ? barricadeSquares(draft.boardRows, draft.boardCols, draft.barricadeCount)
      : []
    ).map((square) => [`${square.row}-${square.col}`, { ...square, type: "barricade", color: "neutral" }])
  );
  const affinityMap = new Set(
    ["center_dominion", "royal_center"].includes(draft.victory.mode) || draft.customRules.affinityEnabled
      ? (draft.victory.mode === "royal_center"
          ? objectiveCenterSquares(draft.boardRows, draft.boardCols)
          : Object.values(affinitySquares(draft.boardRows, draft.boardCols)).flat())
          .map((square) => `${square.row}-${square.col}`)
      : []
  );

  return (
    <div className="studio-preview-stack">
      <div className="studio-board-frame">
        <div
          className="studio-board"
          style={{
            aspectRatio: `${draft.boardCols} / ${draft.boardRows}`,
            gridTemplateColumns: `repeat(${draft.boardCols}, minmax(0, 1fr))`,
            gridTemplateRows: `repeat(${draft.boardRows}, minmax(0, 1fr))`,
            "--studio-piece-size": `${Math.max(0.7, Math.min(1.8, 14 / Math.max(draft.boardRows, draft.boardCols)))}rem`,
          }}
        >
          {Array.from({ length: draft.boardRows }).map((_, row) =>
            Array.from({ length: draft.boardCols }).map((__, col) => {
              const placement = barricadeMap.get(`${row}-${col}`) || placementMap.get(`${row}-${col}`);
              const definition = placement ? definitionMap.get(placement.type) : null;
              const piece = previewPiece(
                placement,
                definition,
                draft.pointValues[placement?.type],
                draft.pieceParameters[placement?.type]
              );
              const affinity = affinityMap.has(`${row}-${col}`);
              const tooltipPlacement = row < draft.boardRows / 2 ? "below" : "above";
              const tooltipEdge = col < draft.boardCols / 3 ? "left" : col >= (draft.boardCols * 2) / 3 ? "right" : "center";
              return (
                <button
                  type="button"
                  key={`${row}-${col}`}
                  className={[
                    "studio-square",
                    (row + col) % 2 === 0 ? "light" : "dark",
                    draft.gambit.enabled && setupRows.has(row) ? "setup-zone" : "",
                    draft.gambit.enabled ? "readonly" : "",
                    affinity ? "studio-affinity" : "",
                  ].filter(Boolean).join(" ")}
                  onClick={() => onPlace(row, col)}
                  aria-label={`${coordinate(row, col, draft.boardRows)}${piece ? `, ${piece.color} ${piece.name}` : ""}`}
                >
                  {col === 0 ? <span className="studio-rank">{draft.boardRows - row}</span> : null}
                  {row === draft.boardRows - 1 ? <span className="studio-file">{String.fromCharCode(65 + col)}</span> : null}
                  {piece ? (
                    <>
                      <span className={`studio-piece piece-${piece.color} ${piece.isCustom ? "custom" : ""}`}>
                        <PieceGlyph piece={piece} />
                      </span>
                      <PieceTooltip piece={piece} placement={tooltipPlacement} edge={tooltipEdge} />
                    </>
                  ) : null}
                </button>
              );
            })
          )}
        </div>
      </div>

      <div className="board-tool-readout">
        <span>{draft.gambit.enabled ? "Private Setup Preview" : "Board Editor"}</span>
        <strong>
          {draft.gambit.enabled
            ? `${draft.gambit.setupRows} home rows per player`
            : selectedTool?.kind === "erase"
              ? "Eraser selected"
              : selectedTool
                ? `${title(selectedTool.color)} ${title(selectedTool.type)} selected`
                : "Choose a piece below"}
        </strong>
        {!draft.gambit.enabled ? (
          <div className="board-editor-actions">
            <button type="button" className="text-button" onClick={() => onSelectTool({ kind: "erase" })}>
              Use Eraser
            </button>
            <button type="button" className="text-button clear-board-button" disabled={!draft.placements.length} onClick={onClearBoard}>
              Clear Board
            </button>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function Toggle({ checked, onChange, label, description }) {
  return (
    <label className="studio-toggle">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span className="toggle-track" aria-hidden="true"><i /></span>
      <span className="toggle-copy"><strong>{label}</strong><small>{description}</small></span>
    </label>
  );
}

function TunableParameterFields({ parameters, values, disabled = false, onChange }) {
  if (!parameters?.length) return null;
  return (
    <fieldset className="tuning-fieldset" disabled={disabled}>
      <legend>Behavior Settings</legend>
      <div className="tuning-field-grid">
        {parameters.map((parameter) => (
          <label key={parameter.id}>
            <span>{parameter.label}</span>
            <input
              type="number"
              min={parameter.min}
              max={parameter.max}
              step="1"
              value={values?.[parameter.id] ?? parameter.default}
              onChange={(event) => onChange(
                parameter.id,
                clamp(event.target.value, parameter.min, parameter.max)
              )}
            />
            <small>
              {parameter.description} Default: {parameterValueLabel(parameter, parameter.default)}.
            </small>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function ConfiguredParameterList({ parameters }) {
  if (!parameters?.length) return null;
  return (
    <dl className="configured-parameter-list">
      {parameters.map((parameter) => (
        <div key={parameter.id}>
          <dt>{parameter.label}</dt>
          <dd>{parameterValueLabel(parameter)}</dd>
        </div>
      ))}
    </dl>
  );
}

function SectionHeading({ title: heading, description }) {
  return <div className="section-heading"><div><h2>{heading}</h2><p>{description}</p></div></div>;
}

function DisclosureArrow() {
  return <span className="disclosure-arrow" aria-hidden="true" />;
}

function CollapsibleStudioSection({ title: heading, description, className = "", children }) {
  const [open, setOpen] = useState(true);

  return (
    <details
      className={`studio-section studio-disclosure ${className}`.trim()}
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>
        <SectionHeading title={heading} description={description} />
        <DisclosureArrow />
      </summary>
      <div className="studio-disclosure-body">{children}</div>
    </details>
  );
}

function RulebookSection({ id, title: heading, description, className = "", children }) {
  const [open, setOpen] = useState(true);

  return (
    <details
      className={`rulebook-section rulebook-disclosure ${className}`.trim()}
      id={id}
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary className="rulebook-section-heading">
        <div><h3>{heading}</h3><p>{description}</p></div>
        <DisclosureArrow />
      </summary>
      <div className="rulebook-disclosure-body">{children}</div>
    </details>
  );
}

function Rulebook({ catalog, draft }) {
  return (
    <section className="rulebook" id="rulebook">
      <header className="rulebook-hero">
        <div>
          <span className="eyebrow">Complete Reference</span>
          <h2>The Chass Rulebook</h2>
          <p>Detailed behavior for every built-in piece, victory rule, ability, and Gambit system.</p>
        </div>
        <nav aria-label="Rulebook sections">
          <a href="#rulebook-pieces">Pieces</a>
          <a href="#rulebook-victory">Victory</a>
          <a href="#rulebook-custom-rules">Custom Rules</a>
          <a href="#rulebook-abilities">Abilities</a>
          <a href="#rulebook-gambit">Gambit</a>
        </nav>
      </header>

      <RulebookSection id="rulebook-pieces" title="Piece Encyclopedia" description="Movement, value, and special behavior.">
        <div className="rulebook-entry-grid">
          {catalog.pieces.map((piece) => {
            const effectivePiece = effectiveCatalogEntry(
              piece,
              draft.pieceParameters[piece.type]
            );
            return (
            <details className="rulebook-entry" key={effectivePiece.type}>
              <summary>
                <span className="entry-icon"><PieceGlyph type={effectivePiece.type} color="black" symbol={effectivePiece.symbols.black || effectivePiece.icon} /></span>
                <span><strong>{effectivePiece.name}</strong><small>{effectivePiece.isCustom ? "Custom piece" : "Classic piece"}</small></span>
                <b>{draft.pointValues[effectivePiece.type] ?? 0} pts</b>
              </summary>
              <p>{effectivePiece.description}</p>
              <h4>Movement</h4>
              <p>{effectivePiece.movement}</p>
              <ConfiguredParameterList parameters={effectivePiece.configuredParameters} />
              {effectivePiece.rules.length ? <ul>{effectivePiece.rules.map((rule) => <li key={rule}>{rule}</li>)}</ul> : null}
            </details>
          );})}
        </div>
      </RulebookSection>

      <RulebookSection id="rulebook-victory" title="Victory Rules" description="What ends a match and decides its result.">
        <div className="rulebook-strip">
          {catalog.victoryModes.map((mode) => <div key={mode.id}><i>{mode.icon}</i><strong>{mode.name}</strong><p>{mode.summary}</p></div>)}
        </div>
      </RulebookSection>

      <RulebookSection id="rulebook-custom-rules" title="Custom Rules" description="Optional board-wide systems that work with any compatible game mode.">
        <div className="rulebook-gambit-copy">
          <div>
            <h4>Affinity Squares</h4>
            <p>Each color receives two adaptive center squares. Hold both squares assigned to your color through the opponent&apos;s turn to earn one command point.</p>
            <p>Spend one point for a Pawn, two to evolve a Pawn, or three for a Rook. A command uses the normal turn and must leave the King safe.</p>
          </div>
          <div>
            <h4>Command Point Cap</h4>
            <p>The cap controls how many unused command points a player may save. It defaults to three and can be changed without enabling Chass Gambit.</p>
          </div>
        </div>
      </RulebookSection>

      <RulebookSection id="rulebook-abilities" title="Special Ability Codex" description="Each player privately chooses the configured number of enabled abilities.">
        <div className="rulebook-entry-grid">
          {catalog.specialAbilities.map((ability) => {
            const effectiveAbility = effectiveCatalogEntry(
              ability,
              draft.specialAbilities.parameters[ability.id]
            );
            return (
            <details className="rulebook-entry ability-entry" key={effectiveAbility.id}>
              <summary><span className="entry-icon">{effectiveAbility.icon}</span><span><strong>{effectiveAbility.name}</strong><small>Player ability</small></span></summary>
              <p>{effectiveAbility.summary}</p>
              <ConfiguredParameterList parameters={effectiveAbility.configuredParameters} />
              <ul>{effectiveAbility.details.map((detail) => <li key={detail}>{detail}</li>)}</ul>
            </details>
          );})}
        </div>
      </RulebookSection>

      <RulebookSection id="rulebook-gambit" title={`${catalog.gambit.icon} ${catalog.gambit.name}`} description={catalog.gambit.summary}>
        <div className="rulebook-gambit-copy">
          <ol>{catalog.gambit.details.map((detail) => <li key={detail}>{detail}</li>)}</ol>
          <div>
            <h4>Draft Gambit</h4>
            <ol>{catalog.gambit.draftDetails.map((detail) => <li key={detail}>{detail}</li>)}</ol>
          </div>
        </div>
      </RulebookSection>

      <RulebookSection title="Turns And Countdowns" description="How timed effects are counted." className="countdown-reference">
        <p>Countdowns decrease when the affected player completes a turn. Both players see active timers in the Play sidebar and in piece tooltips.</p>
      </RulebookSection>
    </section>
  );
}

function CustomizationPanel({ onCreate, initialPreset = "" }) {
  const [catalog, setCatalog] = useState(null);
  const [draft, setDraft] = useState(null);
  const [selectedTool, setSelectedTool] = useState(null);
  const [creatingMode, setCreatingMode] = useState("");
  const [error, setError] = useState("");
  const [validation, setValidation] = useState({ status: "loading", valid: false, errors: [], warnings: [], disabledOptions: {} });

  useEffect(() => {
    let cancelled = false;
    getCatalog()
      .then((payload) => {
        if (cancelled) return;
        let initial = loadSavedDraft(payload);
        const preset = payload.popularModes.find((mode) => mode.id === initialPreset);
        if (preset) initial = applyModeToDraft(initial, preset, payload);
        setCatalog(payload);
        setDraft(initial);
      })
      .catch((requestError) => setError(requestError.message));
    return () => { cancelled = true; };
  }, [initialPreset]);

  useEffect(() => {
    if (!draft) return undefined;
    let cancelled = false;
    setValidation((current) => ({ ...current, status: "checking" }));
    const timer = window.setTimeout(() => {
      validateGameConfiguration(buildRequest(draft))
        .then((result) => {
          if (!cancelled) setValidation({ status: result.valid ? "valid" : "invalid", ...result });
        })
        .catch((requestError) => {
          if (!cancelled) {
            setValidation({ status: "invalid", valid: false, errors: [requestError.message], warnings: [], disabledOptions: {} });
          }
        });
    }, 500);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [draft]);

  const definitionMap = useMemo(
    () => new Map((catalog?.pieces || []).map((piece) => [piece.type, piece])),
    [catalog]
  );

  if (!catalog || !draft) {
    return <section className="customization-panel studio-loading"><span className="loading-mark" /><h2>Opening The Chass Workshop</h2><p>{error || "Loading game options..."}</p></section>;
  }

  const currentFormation = catalog.formations.find((formation) => formation.id === draft.formationId);
  const disabledVictoryModes = {
    ...(currentFormation?.disabledVictoryModes || {}),
    ...(validation.disabledOptions?.victoryModes || {}),
  };
  const disabledAbilities = {
    ...(currentFormation?.disabledAbilities || {}),
    ...(validation.disabledOptions?.abilities || {}),
  };

  const applyPopularMode = (mode) => {
    setSelectedTool(null);
    setDraft((current) => applyModeToDraft(current, mode, catalog));
  };

  const applyFormation = (formation) => {
    const disabled = formation.disabledAbilities || {};
    setSelectedTool(null);
    setDraft((current) => ({
      ...current,
      presetId: formation.id,
      formationId: formation.id,
      boardRows: formation.boardRows,
      boardCols: formation.boardCols,
      enabledPieces: [...STANDARD_TYPES],
      placements: formation.initialLayout,
      victory: { ...current.victory, mode: formation.defaultVictory },
      specialAbilities: {
        ...current.specialAbilities,
        allowed: current.specialAbilities.allowed.filter((ability) => !disabled[ability]),
      },
      gambit: { ...current.gambit, enabled: false, draftEnabled: false },
    }));
  };

  const changeDimensions = (nextRows, nextCols) => {
    const rows = clamp(nextRows, MIN_DIMENSION, MAX_DIMENSION);
    const cols = clamp(nextCols, MIN_DIMENSION, MAX_DIMENSION);
    setDraft((current) => ({
      ...current,
      presetId: "custom",
      formationId: "custom",
      boardRows: rows,
      boardCols: cols,
      barricadeCount: Math.min(current.barricadeCount, Math.max(1, Math.floor(cols / 2))),
      placements: centeredResize(current.placements, current.boardRows, current.boardCols, rows, cols),
      gambit: {
        ...current.gambit,
        setupRows: Math.min(current.gambit.setupRows, Math.max(1, Math.floor(rows / 2))),
      },
    }));
  };

  const togglePiece = (pieceType, enabled) => {
    if (pieceType === "king" && !enabled) return;
    setDraft((current) => ({
      ...current,
      presetId: "custom",
      formationId: "custom",
      enabledPieces: enabled
        ? [...new Set([...current.enabledPieces, pieceType])]
        : current.enabledPieces.filter((type) => type !== pieceType),
      placements: enabled
        ? current.placements
        : current.placements.filter((piece) => piece.type !== pieceType),
    }));
    if (!enabled && selectedTool?.type === pieceType) setSelectedTool(null);
  };

  const placeTool = (row, col) => {
    if (draft.gambit.enabled || !selectedTool) return;
    const reserved = draft.enabledPieces.includes("barricade") && barricadeSquares(
      draft.boardRows,
      draft.boardCols,
      draft.barricadeCount
    ).some((square) => square.row === row && square.col === col);
    if (reserved) return;
    setDraft((current) => {
      const withoutSquare = current.placements.filter((piece) => piece.row !== row || piece.col !== col);
      return {
        ...current,
        presetId: "custom",
        formationId: "custom",
        placements: selectedTool.kind === "erase"
          ? withoutSquare
          : [...withoutSquare, { row, col, type: selectedTool.type, color: selectedTool.color }],
      };
    });
  };

  const clearBoard = () => {
    setSelectedTool(null);
    setDraft((current) => ({
      ...current,
      presetId: "custom",
      formationId: "custom",
      placements: [],
    }));
  };

  const toggleSpecialAbilities = (enabled) => {
    const allowed = enabled
      ? catalog.specialAbilities
          .filter((ability) => !disabledAbilities[ability.id])
          .map((ability) => ability.id)
      : [];
    setDraft((current) => ({
      ...current,
      presetId: "custom",
      specialAbilities: {
        ...current.specialAbilities,
        enabled,
        allowed,
        maxPerPlayer: Math.min(current.specialAbilities.maxPerPlayer, Math.max(1, allowed.length)),
      },
    }));
  };

  const create = async (mode) => {
    setCreatingMode(mode);
    setError("");
    const request = buildRequest(draft, mode);
    try {
      const latestValidation = await validateGameConfiguration(request);
      setValidation({ status: latestValidation.valid ? "valid" : "invalid", ...latestValidation });
      if (!latestValidation.valid) {
        setError(latestValidation.errors[0]);
        setCreatingMode("");
        return;
      }
      await onCreate(request);
    } catch (requestError) {
      setError(requestError.message);
      setCreatingMode("");
    }
  };

  const canLaunch = validation.status === "valid" && validation.valid && !creatingMode;
  const validationSummary =
    validation.status === "checking" || validation.status === "loading"
      ? "Checking configuration..."
      : validation.valid
        ? "Configuration valid"
        : `${validation.errors.length} setting issue${validation.errors.length === 1 ? "" : "s"}`;

  return (
    <section className="customization-panel configuration-studio">
      <header className="studio-hero">
        <div><span className="eyebrow">Configuration Studio</span><h1>Build Your Version Of Chass</h1><p>Choose a starting mode, then adjust the board, pieces, victory rule, abilities, or Gambit setup.</p></div>
        <a className="rulebook-jump" href="#rulebook">Read The Rulebook</a>
      </header>

      <div className="studio-shell">
        <aside className="studio-preview-column">
          <ConfigurationBoard draft={draft} catalog={catalog} selectedTool={selectedTool} onSelectTool={setSelectedTool} onPlace={placeTool} onClearBoard={clearBoard} />
          <div className="studio-summary-card"><span>Current Game</span><strong>{draft.boardRows}x{draft.boardCols} {draft.gambit.enabled && draft.gambit.draftEnabled ? "Draft Gambit" : draft.gambit.enabled ? "Gambit" : "Board"}</strong><p>{draft.enabledPieces.length} piece types, {title(draft.victory.mode)} victory</p>{draft.specialAbilities.enabled ? <p>{draft.specialAbilities.allowed.length} abilities enabled</p> : null}</div>
        </aside>

        <div className="studio-controls">
          <CollapsibleStudioSection title="Popular Modes" description="Load a complete starting configuration.">
            <div className="mode-preset-grid">
              {catalog.popularModes.map((mode) => <button type="button" key={mode.id} className={draft.presetId === mode.id ? "selected" : ""} onClick={() => applyPopularMode(mode)}><i>{mode.icon}</i><strong>{mode.name}</strong><small>{mode.summary}</small></button>)}
            </div>
            <h3 className="formation-heading">Board Formations</h3>
            <div className="mode-preset-grid formation-grid">
              {catalog.formations.map((formation) => <button type="button" key={formation.id} className={draft.formationId === formation.id ? "selected" : ""} onClick={() => applyFormation(formation)}><i>{formation.icon}</i><strong>{formation.name}</strong><small>{formation.summary}</small></button>)}
            </div>
          </CollapsibleStudioSection>

          <CollapsibleStudioSection title="Board Size" description="Choose a preset or set dimensions from 4 to 16.">
            <div className="dimension-presets">
              {[8, 10, 16].map((size) => <button type="button" key={size} className={draft.boardRows === size && draft.boardCols === size ? "active" : "secondary"} onClick={() => changeDimensions(size, size)}>{size}x{size}</button>)}
              <span>Custom</span>
              <label>Rows<input type="number" min={MIN_DIMENSION} max={MAX_DIMENSION} value={draft.boardRows} onChange={(event) => changeDimensions(event.target.value, draft.boardCols)} /></label>
              <label>Columns<input type="number" min={MIN_DIMENSION} max={MAX_DIMENSION} value={draft.boardCols} onChange={(event) => changeDimensions(draft.boardRows, event.target.value)} /></label>
            </div>
          </CollapsibleStudioSection>

          <CollapsibleStudioSection title="Pieces" description="Enable pieces, set values of zero or more, and edit the starting board.">
            <div className="piece-catalog-grid">
              {catalog.pieces.map((piece) => {
                const enabled = draft.enabledPieces.includes(piece.type);
                const effectivePiece = effectiveCatalogEntry(
                  piece,
                  draft.pieceParameters[piece.type]
                );
                return (
                  <article key={piece.type} className={`piece-config-card ${enabled ? "enabled" : ""} ${piece.isCustom ? "custom" : ""}`}>
                    <header><span><PieceGlyph type={piece.type} color="black" symbol={piece.symbols.black || piece.icon} /></span><div><h3>{piece.name}</h3><small>{piece.isCustom ? "Custom Piece" : "Classic Piece"}</small></div><input aria-label={`Enable ${piece.name}`} type="checkbox" checked={enabled} disabled={piece.type === "king"} onChange={(event) => togglePiece(piece.type, event.target.checked)} /></header>
                    <p>{effectivePiece.description}</p><small className="movement-copy">{effectivePiece.movement}</small>
                    <TunableParameterFields
                      parameters={piece.tunableParameters}
                      values={draft.pieceParameters[piece.type]}
                      disabled={!enabled}
                      onChange={(parameterId, value) => setDraft((current) => ({
                        ...current,
                        presetId: "custom",
                        pieceParameters: {
                          ...current.pieceParameters,
                          [piece.type]: {
                            ...current.pieceParameters[piece.type],
                            [parameterId]: value,
                          },
                        },
                      }))}
                    />
                    <div className="piece-config-fields">
                      <label>Point Value<input type="number" min="0" max={catalog.limits.pointMax} step="1" disabled={!enabled} value={draft.pointValues[piece.type]} onChange={(event) => setDraft((current) => ({ ...current, presetId: "custom", pointValues: { ...current.pointValues, [piece.type]: clamp(event.target.value, 0, catalog.limits.pointMax) } }))} /></label>
                      {draft.gambit.enabled && piece.type !== "barricade" ? <label>Army Limit<input type="number" min={piece.type === "king" ? 1 : 0} max={draft.gambit.maxPieces} disabled={!enabled || piece.type === "king"} value={draft.pieceCaps[piece.type]} onChange={(event) => setDraft((current) => ({ ...current, presetId: "custom", pieceCaps: { ...current.pieceCaps, [piece.type]: Math.max(0, Number(event.target.value)) } }))} /></label> : null}
                      {draft.gambit.enabled && draft.gambit.draftEnabled && piece.type !== "barricade" ? <label>{piece.type === "king" ? "Starting Kings" : "Shared Draft Pool"}<input type="number" min={piece.type === "king" ? 2 : 0} max="256" disabled={!enabled || piece.type === "king"} value={draft.gambit.draftPool[piece.type] ?? 0} onChange={(event) => setDraft((current) => ({ ...current, presetId: "custom", gambit: { ...current.gambit, draftPool: { ...current.gambit.draftPool, [piece.type]: Math.max(0, Number(event.target.value)) } } }))} /><small>{piece.type === "king" ? "One King is automatically assigned to each army." : "Total copies available to both players."}</small></label> : null}
                      {enabled && piece.type === "barricade" ? <label>Starting Walls<input type="number" min="1" max={Math.max(1, Math.floor(draft.boardCols / 2))} value={draft.barricadeCount} onChange={(event) => setDraft((current) => ({ ...current, presetId: "custom", barricadeCount: clamp(event.target.value, 1, Math.max(1, Math.floor(current.boardCols / 2))) }))} /></label> : null}
                    </div>
                    {enabled && !draft.gambit.enabled ? <div className="piece-color-tools">{piece.type === "barricade" ? <p className="fixed-piece-note"><PieceGlyph type="barricade" color="neutral" symbol={piece.symbols.neutral} /> Starting walls occupy reserved central squares.</p> : ["white", "black"].map((color) => <button type="button" key={color} className={selectedTool?.type === piece.type && selectedTool?.color === color ? "active" : "secondary"} onClick={() => setSelectedTool({ kind: "piece", type: piece.type, color })}><PieceGlyph type={piece.type} color={color} symbol={piece.symbols[color] || piece.icon} /> {title(color)}</button>)}</div> : null}
                  </article>
                );
              })}
            </div>
          </CollapsibleStudioSection>

          <CollapsibleStudioSection title="End Game Logic" description="Choose the condition that decides the result.">
            <div className="victory-grid">
              {catalog.victoryModes.map((mode) => {
                const reason = disabledVictoryModes[mode.id];
                return <button type="button" key={mode.id} className={draft.victory.mode === mode.id ? "selected" : ""} disabled={Boolean(reason)} title={reason || ""} onClick={() => setDraft((current) => ({ ...current, presetId: "custom", victory: { ...current.victory, mode: mode.id } }))}><i>{mode.icon}</i><span><strong>{mode.name}</strong><small>{reason || mode.summary}</small></span></button>;
              })}
            </div>
            <div className="conditional-fields">
              {draft.victory.mode === "point_race" ? <label>Target Score<input type="number" min="1" value={draft.victory.targetPoints} onChange={(event) => setDraft((current) => ({ ...current, presetId: "custom", victory: { ...current.victory, targetPoints: Math.max(1, Number(event.target.value)) } }))} /><small>Captured-piece points needed to win.</small></label> : null}
              {draft.victory.mode === "timed" ? <label>Minutes Per Player<input type="number" min="1" max="1440" value={Math.round(draft.victory.timeSeconds / 60)} onChange={(event) => setDraft((current) => ({ ...current, presetId: "custom", victory: { ...current.victory, timeSeconds: Math.max(60, Number(event.target.value) * 60) } }))} /><small>The server controls both clocks.</small></label> : null}
              {draft.victory.mode === "center_dominion" ? <label>Rounds To Hold<input type="number" min="1" max="20" value={draft.victory.dominionRounds} onChange={(event) => setDraft((current) => ({ ...current, presetId: "custom", victory: { ...current.victory, dominionRounds: clamp(event.target.value, 1, 20) } }))} /><small>Both marked squares must stay occupied through this many opponent turns. Checkmate also wins.</small></label> : null}
              {draft.victory.mode === "check_race" ? <label>Checks To Win<input type="number" min="1" max="100" value={draft.victory.checkTarget} onChange={(event) => setDraft((current) => ({ ...current, presetId: "custom", victory: { ...current.victory, checkTarget: clamp(event.target.value, 1, 100) } }))} /><small>The first player to give this many checks wins. Checkmate also wins immediately.</small></label> : null}
              {["point_race", "king_capture", "royal_score"].includes(draft.victory.mode) ? <label>King Point Value<input type="number" min="0" value={draft.victory.kingPoints} onChange={(event) => setDraft((current) => ({ ...current, presetId: "custom", victory: { ...current.victory, kingPoints: Math.max(0, Number(event.target.value)) }, pointValues: { ...current.pointValues, king: Math.max(0, Number(event.target.value)) } }))} /><small>Zero is allowed in non-classic victory modes.</small></label> : null}
            </div>
          </CollapsibleStudioSection>

          <CollapsibleStudioSection title="Custom Rules" description="Add optional board-wide systems to any game mode." className="ability-config-section">
            <Toggle checked={draft.customRules.affinityEnabled} onChange={(affinityEnabled) => setDraft((current) => ({ ...current, presetId: "custom", customRules: { ...current.customRules, affinityEnabled } }))} label="Enable Affinity Squares" description="Control both center squares of your color to earn command points." />
            {draft.customRules.affinityEnabled ? <div className="conditional-fields">
              <label>Command Point Cap<input type="number" min="0" max="20" value={draft.customRules.commandPointCap} onChange={(event) => setDraft((current) => ({ ...current, presetId: "custom", customRules: { ...current.customRules, commandPointCap: clamp(event.target.value, 0, 20) } }))} /><small>Maximum command points a player may save. The default is 3.</small></label>
            </div> : null}
          </CollapsibleStudioSection>

          <CollapsibleStudioSection title="Special Abilities" description="Each player privately chooses the configured number of allowed abilities before play." className="ability-config-section">
            <Toggle checked={draft.specialAbilities.enabled} onChange={toggleSpecialAbilities} label="Enable Special Abilities" description="All compatible abilities start enabled. Selections are revealed after both players lock in." />
            {draft.specialAbilities.enabled ? <>
              <div className="conditional-fields"><label>Abilities Per Player<input type="number" min="1" max={Math.max(1, draft.specialAbilities.allowed.length)} value={draft.specialAbilities.maxPerPlayer} onChange={(event) => setDraft((current) => ({ ...current, presetId: "custom", specialAbilities: { ...current.specialAbilities, maxPerPlayer: clamp(event.target.value, 1, Math.max(1, current.specialAbilities.allowed.length)) } }))} /><small>How many abilities each player selects. The default is 1.</small></label></div>
              <div className="ability-option-grid">{catalog.specialAbilities.map((ability) => {
                const enabled = draft.specialAbilities.allowed.includes(ability.id);
                const reason = disabledAbilities[ability.id];
                const effectiveAbility = effectiveCatalogEntry(
                  ability,
                  draft.specialAbilities.parameters[ability.id]
                );
                return (
                  <article key={ability.id} className={`ability-config-card ${enabled ? "selected" : ""}`}>
                    <button
                      type="button"
                      className="ability-option-toggle"
                      disabled={Boolean(reason) || (enabled && draft.specialAbilities.allowed.length <= draft.specialAbilities.maxPerPlayer)}
                      title={reason || ""}
                      onClick={() => setDraft((current) => {
                        const allowed = enabled
                          ? current.specialAbilities.allowed.filter((id) => id !== ability.id)
                          : [...current.specialAbilities.allowed, ability.id];
                        return {
                          ...current,
                          presetId: "custom",
                          specialAbilities: { ...current.specialAbilities, allowed },
                        };
                      })}
                    >
                      <i>{ability.icon}</i>
                      <span><strong>{ability.name}</strong><small>{reason || effectiveAbility.summary}</small></span>
                      <b>{reason ? "Unavailable" : enabled ? "Enabled" : "Off"}</b>
                    </button>
                    <TunableParameterFields
                      parameters={ability.tunableParameters}
                      values={draft.specialAbilities.parameters[ability.id]}
                      disabled={!enabled || Boolean(reason)}
                      onChange={(parameterId, value) => setDraft((current) => ({
                        ...current,
                        presetId: "custom",
                        specialAbilities: {
                          ...current.specialAbilities,
                          parameters: {
                            ...current.specialAbilities.parameters,
                            [ability.id]: {
                              ...current.specialAbilities.parameters[ability.id],
                              [parameterId]: value,
                            },
                          },
                        },
                      }))}
                    />
                  </article>
                );
              })}</div>
            </> : null}
          </CollapsibleStudioSection>

          <CollapsibleStudioSection title="Chass Gambit" description="Add private army construction to this board and ruleset." className="gambit-config-section">
            <Toggle checked={draft.gambit.enabled} onChange={(enabled) => setDraft((current) => ({ ...current, presetId: enabled ? "gambit" : "custom", formationId: enabled ? "classic" : "custom", gambit: { ...current.gambit, enabled, draftEnabled: enabled ? current.gambit.draftEnabled : false } }))} label="Enable Chass Gambit" description="Each player builds an army in their closest home rows without exceeding the point limit." />
            {draft.gambit.enabled ? <div className="gambit-settings-grid">
              <label>Maximum Points<input type="number" min="0" value={draft.gambit.budget} onChange={(event) => setDraft((current) => ({ ...current, presetId: "custom", gambit: { ...current.gambit, budget: Math.max(0, Number(event.target.value)) } }))} /><small>Players may spend less, but cannot exceed this limit.</small></label>
              <label>Maximum Pieces<input type="number" min="1" max="128" value={draft.gambit.maxPieces} onChange={(event) => setDraft((current) => ({ ...current, presetId: "custom", gambit: { ...current.gambit, maxPieces: Math.max(1, Number(event.target.value)) } }))} /><small>Includes the required King.</small></label>
              <label>Private Setup Rows<input type="number" min="1" max={Math.floor(draft.boardRows / 2)} value={draft.gambit.setupRows} onChange={(event) => setDraft((current) => ({ ...current, presetId: "custom", gambit: { ...current.gambit, setupRows: clamp(event.target.value, 1, Math.max(1, Math.floor(current.boardRows / 2))) } }))} /><small>Rows nearest each player that they may edit.</small></label>
              <label>Maximum Queens<input type="number" min="0" max={Math.max(0, draft.gambit.maxPieces - 1)} value={draft.gambit.maxQueens} onChange={(event) => { const value = Math.max(0, Number(event.target.value)); setDraft((current) => ({ ...current, presetId: "custom", gambit: { ...current.gambit, maxQueens: value }, pieceCaps: { ...current.pieceCaps, queen: value } })); }} /><small>At least one army slot remains for the King.</small></label>
              <Toggle checked={draft.gambit.draftEnabled} onChange={(draftEnabled) => setDraft((current) => ({ ...current, presetId: draftEnabled ? "draft_gambit" : "custom", gambit: { ...current.gambit, draftEnabled, draftPool: { ...current.gambit.draftPool, king: 2 } } }))} label="Enable Shared Draft" description="Alternate public picks from one shared pool before each player privately arranges their drafted army." />
            </div> : null}
          </CollapsibleStudioSection>
        </div>
      </div>

      <section className={`studio-launch-bar validation-${validation.status}`}>
        <div><span>Ready To Launch</span><strong>{validationSummary}</strong><small>{validation.errors[0] || validation.warnings[0] || "Choose local play or create an online invite."}</small></div>
        <div className="launch-actions"><button type="button" disabled={!canLaunch} onClick={() => create("local")}>{creatingMode === "local" ? "Building..." : "Start Local Game"}</button><button type="button" className="secondary" disabled={!canLaunch} onClick={() => create("online")}>{creatingMode === "online" ? "Creating Invite..." : "Create Online Game"}</button></div>
      </section>
      {error ? <p className="studio-error">{error}</p> : null}
      <Rulebook catalog={catalog} draft={draft} />
    </section>
  );
}

export default CustomizationPanel;
