import { useEffect, useMemo, useRef, useState } from "react";

import { getCatalog, validateGameConfiguration } from "../api/gameApi";
import { barricadeSquares, significantCenterSquares } from "../boardGeometry";
import { boardPlacementRestriction } from "../customizeBoardPlacement";
import { configurationIssueSquares, locateConfigurationIssue } from "../configurationIssues";
import { matchingCustomizeResults } from "../customizeNavigation";
import { PIECE_FILTERS, visibleCustomizePieces } from "../customizePieces";
import {
  CONFIGURATION_SECTION_IDS,
  configurationSectionStatuses,
  reconcileDraftIdentity,
  sectionIsModified,
} from "../customizeSectionState";
import {
  savedKingPointValue,
  synchronizeKingPointValue,
  updatePiecePointValue,
} from "../customizationState";
import { matchesRulebookSearch } from "../rulebookSearch";
import { isExactClassicDraft } from "../matchPredictor";
import {
  applyParameterChange,
  effectiveCatalogEntry,
  mergeParameterGroups,
  parameterDefault,
  parameterDefaults,
  parameterMaximum,
  parameterValueLabel,
} from "../variantTuning";
import GameBriefing from "./GameBriefing";
import PageSkeleton from "./PageSkeleton";
import PieceGlyph from "./PieceGlyph";
import PieceTooltip from "./PieceTooltip";

const MIN_DIMENSION = 4;
const MAX_DIMENSION = 16;
const STANDARD_TYPES = ["pawn", "knight", "bishop", "rook", "queen", "king"];
const BACK_RANK = ["rook", "knight", "bishop", "queen", "king", "bishop", "knight", "rook"];
const DEFAULT_DRAFT_POOL = { pawn: 16, knight: 4, bishop: 4, rook: 4, queen: 2, king: 2 };
const SECTION_VISIBILITY_STORAGE_KEY = "chass-customize-section-visibility";

function title(value) {
  return value ? value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()) : "";
}

function clamp(value, minimum, maximum) {
  const number = Number(value);
  if (!Number.isFinite(number)) return minimum;
  return Math.max(minimum, Math.min(maximum, Math.trunc(number)));
}

function cloneDraft(value) {
  return JSON.parse(JSON.stringify(value));
}

function initialSectionVisibility() {
  const defaults = Object.fromEntries(
    CONFIGURATION_SECTION_IDS.map((sectionId) => [sectionId, true])
  );
  try {
    const saved = JSON.parse(window.sessionStorage.getItem(SECTION_VISIBILITY_STORAGE_KEY));
    return Object.fromEntries(
      CONFIGURATION_SECTION_IDS.map((sectionId) => [
        sectionId,
        typeof saved?.[sectionId] === "boolean" ? saved[sectionId] : defaults[sectionId],
      ])
    );
  } catch {
    return defaults;
  }
}

function resizeDynamicParameterDefaults(
  groups,
  entries,
  previousContext,
  nextContext
) {
  const resized = { ...groups };
  entries.forEach((entry) => {
    const dynamicParameters = (entry.tunableParameters || []).filter(
      (parameter) => parameter.dynamicDefault
    );
    if (!dynamicParameters.length) return;
    resized[entry.id] = { ...groups[entry.id] };
    dynamicParameters.forEach((parameter) => {
      if (
        groups[entry.id]?.[parameter.id]
        === parameterDefault(parameter, previousContext)
      ) {
        resized[entry.id][parameter.id] = parameterDefault(parameter, nextContext);
      }
    });
  });
  return resized;
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
  const abilityParameters = parameterDefaults(catalog.specialAbilities, { rows: 8, cols: 8 });
  return {
    schemaVersion: 2,
    presetId: "classic",
    formationId: "classic",
    matchPredictorEnabled: true,
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
    const abilityParameters = mergeParameterGroups(
      base.specialAbilities.parameters,
      configuration.specialAbilities?.parameters
    );
    catalog.specialAbilities.forEach((ability) => {
      (ability.tunableParameters || [])
        .filter((parameter) => parameter.dynamicDefault)
        .forEach((parameter) => {
          if (!Object.hasOwn(
            configuration.specialAbilities?.parameters?.[ability.id] || {},
            parameter.id
          )) {
            abilityParameters[ability.id][parameter.id] = parameterDefault(
              parameter,
              { rows: boardRows, cols: boardCols }
            );
          }
        });
    });
    const loadedDraft = {
      ...base,
      schemaVersion: 2,
      presetId: configuration.presetId || "custom",
      formationId: configuration.formationId || "custom",
      matchPredictorEnabled: configuration.matchPredictorEnabled ?? base.matchPredictorEnabled,
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
        parameters: abilityParameters,
      },
      gambit: {
        ...base.gambit,
        ...gambit,
        draftPool: { ...base.gambit.draftPool, ...(gambit.draftPool || {}) },
      },
    };
    const loadedKingPoints = savedKingPointValue(
      configuration.victory,
      pointValues
    );
    return synchronizeKingPointValue(
      loadedDraft,
      loadedKingPoints,
      catalog.limits.pointMax
    );
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
  const specialAbilities = {
    ...defaults.specialAbilities,
    parameters: parameterDefaults(catalog.specialAbilities, { rows, cols }),
  };
  const modeKingPoints = mode.victory?.kingPoints ?? defaults.pointValues.king;
  return synchronizeKingPointValue({
    ...current,
    presetId: mode.id,
    formationId,
    matchPredictorEnabled: mode.matchPredictorEnabled ?? (mode.id === "classic"),
    boardRows: rows,
    boardCols: cols,
    enabledPieces: [...STANDARD_TYPES],
    pieceParameters: defaults.pieceParameters,
    pointValues: defaults.pointValues,
    pieceCaps: defaults.pieceCaps,
    barricadeCount: defaults.barricadeCount,
    placements: layout,
    victory: { ...current.victory, ...mode.victory },
    customRules: { ...defaults.customRules, ...(mode.customRules || {}) },
    specialAbilities,
    gambit: { ...defaults.gambit, enabled: false, draftEnabled: false, ...mode.gambit },
  }, modeKingPoints, catalog.limits.pointMax);
}

function applyFormationToDraft(current, formation, catalog) {
  const disabled = formation.disabledAbilities || {};
  return {
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
      parameters: resizeDynamicParameterDefaults(
        current.specialAbilities.parameters,
        catalog.specialAbilities,
        { rows: current.boardRows, cols: current.boardCols },
        { rows: formation.boardRows, cols: formation.boardCols }
      ),
    },
    gambit: { ...current.gambit, enabled: false, draftEnabled: false },
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
      matchPredictorEnabled: draft.matchPredictorEnabled && isExactClassicDraft(draft),
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
      victory: {
        ...draft.victory,
        kingPoints: Number(draft.pointValues.king ?? 0),
      },
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

function ConfigurationBoard({
  draft,
  catalog,
  selectedTool,
  onSelectTool,
  onPlace,
  onClearBoard,
  onClearColor,
  onMirror,
  onUndo,
  canUndo,
  onRestore,
  highlightedIssueSquares = [],
  placementNotice = "",
}) {
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
  const significantCenterMap = new Set(
    significantCenterSquares(draft.boardRows, draft.boardCols, {
      victoryMode: draft.victory.mode,
      affinityEnabled: draft.customRules.affinityEnabled,
    }).map((square) => `${square.row}-${square.col}`)
  );
  const issueSquareMap = useMemo(
    () => new Set(highlightedIssueSquares.map((square) => `${square.row}-${square.col}`)),
    [highlightedIssueSquares]
  );

  return (
    <div className="studio-preview-stack" data-setting-key="board-editor" id="customize-board-editor">
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
              const squareKey = `${row}-${col}`;
              const configuredPlacement = placementMap.get(squareKey);
              const placement = barricadeMap.get(squareKey) || configuredPlacement;
              const definition = placement ? definitionMap.get(placement.type) : null;
              const piece = previewPiece(
                placement,
                definition,
                draft.pointValues[placement?.type],
                draft.pieceParameters[placement?.type]
              );
              const significantCenter = significantCenterMap.has(squareKey);
              const issueSquare = issueSquareMap.has(squareKey);
              const placementRestriction = boardPlacementRestriction(
                draft,
                selectedTool,
                row,
                col
              );
              const centerStartConflict = Boolean(
                !draft.gambit.enabled
                && significantCenter
                && configuredPlacement
                && configuredPlacement.type !== "barricade"
              );
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
                    significantCenter ? "studio-affinity" : "",
                    centerStartConflict ? "center-start-conflict" : "",
                    issueSquare ? "issue-square-highlight" : "",
                    placementRestriction ? "placement-blocked" : "",
                  ].filter(Boolean).join(" ")}
                  onClick={() => onPlace(row, col)}
                  title={placementRestriction || undefined}
                  aria-label={`${coordinate(row, col, draft.boardRows)}${piece ? `, ${piece.color} ${piece.name}` : ""}${centerStartConflict ? ", invalid occupied center starting square" : ""}${issueSquare ? ", highlighted configuration issue" : ""}${placementRestriction ? `, unavailable: ${placementRestriction}` : ""}`}
                >
                  {col === 0 ? <span className="studio-rank">{draft.boardRows - row}</span> : null}
                  {row === draft.boardRows - 1 ? <span className="studio-file">{String.fromCharCode(65 + col)}</span> : null}
                  {centerStartConflict || issueSquare ? <span className="center-start-warning" aria-hidden="true">!</span> : null}
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
            <button type="button" className="text-button" disabled={!canUndo} onClick={onUndo}>
              Undo
            </button>
          </div>
        ) : null}
        {placementNotice ? <small className="board-placement-notice" role="status">{placementNotice}</small> : null}
      </div>
      {!draft.gambit.enabled ? (
        <div className="board-editor-toolbar" aria-label="Board editor shortcuts">
          <button type="button" onClick={onRestore}>Restore Formation</button>
          <button type="button" onClick={() => onMirror("white")}>Mirror White To Black</button>
          <button type="button" onClick={() => onMirror("black")}>Mirror Black To White</button>
          <button type="button" disabled={!draft.placements.some((piece) => piece.color === "white")} onClick={() => onClearColor("white")}>Clear White</button>
          <button type="button" disabled={!draft.placements.some((piece) => piece.color === "black")} onClick={() => onClearColor("black")}>Clear Black</button>
          <button type="button" className="clear-board-button" disabled={!draft.placements.length} onClick={onClearBoard}>Clear All</button>
        </div>
      ) : null}
    </div>
  );
}

function Toggle({ checked, onChange, label, description, settingKey }) {
  return (
    <label className="studio-toggle" data-setting-key={settingKey}>
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span className="toggle-track" aria-hidden="true"><i /></span>
      <span className="toggle-copy"><strong>{label}</strong><small>{description}</small></span>
    </label>
  );
}

function TunableParameterFields({
  parameters,
  values,
  disabled = false,
  boardRows = 8,
  boardCols = 8,
  onChange,
}) {
  if (!parameters?.length) return null;
  const resolvedValues = Object.fromEntries(
    parameters.map((parameter) => [
      parameter.id,
      values?.[parameter.id] ?? parameterDefault(parameter, {
        rows: boardRows,
        cols: boardCols,
      }),
    ])
  );
  return (
    <fieldset className="tuning-fieldset" disabled={disabled}>
      <legend>Behavior Settings</legend>
      <div className="tuning-field-grid">
        {parameters.map((parameter) => {
          const defaultValue = parameterDefault(parameter, {
            rows: boardRows,
            cols: boardCols,
          });
          const maximum = parameterMaximum(parameter, resolvedValues);
          return (
          <label key={parameter.id}>
            <span>{parameter.label}</span>
            <input
              type="number"
              min={parameter.min}
              max={maximum}
              step="1"
              value={resolvedValues[parameter.id]}
              onChange={(event) => {
                const value = clamp(event.target.value, parameter.min, maximum);
                onChange(applyParameterChange(
                  parameters,
                  resolvedValues,
                  parameter.id,
                  value
                ));
              }}
            />
            <small>
              {parameter.description} Default: {parameterValueLabel(parameter, defaultValue)}.
            </small>
          </label>
          );
        })}
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

function SectionStatusBadges({ status }) {
  if (!status?.modified && !status?.issueCount) return null;
  return (
    <span className="section-status-badges">
      {status.issueCount ? (
        <b className="section-status issue">
          {status.issueCount === 1 ? "Issue" : `${status.issueCount} Issues`}
        </b>
      ) : null}
      {status.modified ? <b className="section-status modified">Modified</b> : null}
    </span>
  );
}

function SectionHeading({ title: heading, description, status }) {
  return (
    <div className="section-heading">
      <div>
        <span className="section-title-line">
          <h2>{heading}</h2>
          <SectionStatusBadges status={status} />
        </span>
        <p>{description}</p>
      </div>
    </div>
  );
}

function DisclosureArrow() {
  return <span className="disclosure-arrow" aria-hidden="true" />;
}

function CollapsibleStudioSection({
  title: heading,
  description,
  className = "",
  sectionId,
  open,
  onOpenChange,
  onReset,
  status,
  children,
}) {
  return (
    <details
      className={`studio-section studio-disclosure ${className}`.trim()}
      id={sectionId}
      open={open}
      onToggle={(event) => onOpenChange(event.currentTarget.open)}
    >
      <summary>
        <SectionHeading title={heading} description={description} status={status} />
        <DisclosureArrow />
      </summary>
      <div className="studio-disclosure-body">
        <div className="studio-section-actions">
          <button
            type="button"
            className="section-reset-button"
            disabled={!status?.modified}
            onClick={onReset}
          >
            Reset Section
          </button>
        </div>
        {children}
      </div>
    </details>
  );
}

function CustomizeNavigator({
  query,
  results,
  sectionStatuses,
  onQueryChange,
  onNavigate,
  onExpandAll,
  onCollapseAll,
}) {
  const firstResult = results[0];
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    if (!menuOpen) return undefined;

    const closeOutsideMenu = (event) => {
      if (!menuRef.current?.contains(event.target)) setMenuOpen(false);
    };
    document.addEventListener("pointerdown", closeOutsideMenu);
    return () => document.removeEventListener("pointerdown", closeOutsideMenu);
  }, [menuOpen]);

  return (
    <aside className="customize-section-navigator" aria-label="Customize page navigation">
      <div className="customize-navigator-heading">
        <strong>Jump To A Section</strong>
      </div>
      <label className="customize-section-search">
        <span className="visually-hidden">Search customize sections and settings</span>
        <input
          type="search"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key !== "Enter" || !firstResult) return;
            event.preventDefault();
            onNavigate(firstResult);
          }}
          placeholder="Find a setting or section"
        />
        {query ? (
          <button type="button" onClick={() => onQueryChange("")} aria-label="Clear customize search">
            Clear
          </button>
        ) : null}
      </label>
      <div
        className={`customize-jump-menu ${menuOpen ? "is-open" : ""}`}
        ref={menuRef}
        onMouseEnter={() => setMenuOpen(true)}
        onMouseLeave={() => setMenuOpen(false)}
        onBlur={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget)) setMenuOpen(false);
        }}
        onKeyDown={(event) => {
          if (event.key !== "Escape") return;
          setMenuOpen(false);
          menuRef.current?.querySelector("button")?.focus();
        }}
      >
        <button
          type="button"
          className="customize-jump-trigger"
          aria-expanded={menuOpen}
          aria-controls="customize-jump-options"
          onClick={() => setMenuOpen((open) => !open)}
        >
          <span>Jump to...</span>
          <small>
            {results.length} {query.trim()
              ? `match${results.length === 1 ? "" : "es"}`
              : `section${results.length === 1 ? "" : "s"}`}
          </small>
          <i aria-hidden="true" />
        </button>
        <div className="customize-jump-options" id="customize-jump-options">
          {results.length ? (
            <nav aria-label="Customize sections">
              {results.map((result) => (
                <a
                  href={`#${result.targetId || result.sectionId}`}
                  key={result.id}
                  onClick={(event) => {
                    event.preventDefault();
                    setMenuOpen(false);
                    onNavigate(result);
                  }}
                >
                  <span className="customize-jump-result-heading">
                    <span>{result.label}</span>
                    <SectionStatusBadges status={sectionStatuses[result.sectionId]} />
                  </span>
                  {query.trim() && result.category ? <small>{result.category}</small> : null}
                </a>
              ))}
            </nav>
          ) : <p>No matching section.</p>}
        </div>
      </div>
      <div className="customize-disclosure-actions" aria-label="Section display controls">
        <button type="button" onClick={onExpandAll}>Expand All</button>
        <button type="button" onClick={onCollapseAll}>Collapse All</button>
      </div>
    </aside>
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
  const affinityCopy = [
    "Affinity Squares",
    "Each color receives two adaptive center squares. Hold both squares assigned to your color through the opponent's turn to earn one command point.",
    "Spend one point for a Pawn, two to evolve a Pawn, or three for a Rook. A command uses the normal turn and must leave the King safe.",
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
    + visibleVictoryModes.length
    + Number(showAffinity)
    + visibleAbilities.length
    + Number(showGambit)
    + Number(showCountdowns);
  const revealKey = query || (enabledOnly ? "enabled" : "");

  return (
    <section className="rulebook" id="rulebook">
      <header className="rulebook-hero">
        <div className="rulebook-hero-copy">
          <span className="eyebrow">Complete Reference</span>
          <h2>The Chass Rulebook</h2>
          <p>Detailed behavior for every built-in piece, victory rule, ability, and Gambit system.</p>
          <div className="rulebook-search-tools">
            <label className="rulebook-search">
              <span className="visually-hidden">Search the rulebook</span>
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search pieces, rules, or abilities"
              />
              {query ? <button type="button" onClick={() => setQuery("")} aria-label="Clear rulebook search">Clear</button> : null}
            </label>
            <label className="rulebook-enabled-filter">
              <input
                type="checkbox"
                checked={enabledOnly}
                onChange={(event) => setEnabledOnly(event.target.checked)}
              />
              <span>Enabled Only</span>
            </label>
            {(query || enabledOnly) ? <small>{resultCount} reference{resultCount === 1 ? "" : "s"} shown</small> : null}
          </div>
        </div>
        <nav aria-label="Rulebook sections">
          <a href="#rulebook-pieces">Pieces</a>
          <a href="#rulebook-victory">Victory</a>
          <a href="#rulebook-custom-rules">Custom Rules</a>
          <a href="#rulebook-abilities">Abilities</a>
          <a href="#rulebook-gambit">Gambit</a>
        </nav>
      </header>

      <RulebookSection id="rulebook-pieces" title="Piece Encyclopedia" description="Movement, value, and special behavior." revealKey={revealKey}>
        <div className="rulebook-entry-grid">
          {visiblePieces.map((effectivePiece) => (
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
          ))}
        </div>
        {!visiblePieces.length ? <p className="rulebook-empty">No matching pieces in this configuration.</p> : null}
      </RulebookSection>

      <RulebookSection id="rulebook-victory" title="Victory Rules" description="What ends a match and decides its result." revealKey={revealKey}>
        <div className="rulebook-strip">
          {visibleVictoryModes.map((mode) => <div key={mode.id}><i>{mode.icon}</i><strong>{mode.name}</strong><p>{mode.summary}</p></div>)}
        </div>
        {!visibleVictoryModes.length ? <p className="rulebook-empty">No matching victory rules in this configuration.</p> : null}
      </RulebookSection>

      <RulebookSection id="rulebook-custom-rules" title="Custom Rules" description="Optional board-wide systems that work with any compatible game mode." revealKey={revealKey}>
        {showAffinity ? <div className="rulebook-gambit-copy">
          <div>
            <h4>Affinity Squares</h4>
            <p>Each color receives two adaptive center squares. Hold both squares assigned to your color through the opponent&apos;s turn to earn one command point.</p>
            <p>Spend one point for a Pawn, two to evolve a Pawn, or three for a Rook. A command uses the normal turn and must leave the King safe.</p>
            <p>Marked center squares must begin empty; only Barricades may start there.</p>
          </div>
          <div>
            <h4>Command Point Cap</h4>
            <p>The cap controls how many unused command points a player may save. It defaults to three and can be changed without enabling Chass Gambit.</p>
          </div>
        </div> : <p className="rulebook-empty">No matching custom rules in this configuration.</p>}
      </RulebookSection>

      <RulebookSection id="rulebook-abilities" title="Special Ability Codex" description="Each player privately chooses the configured number of enabled abilities." revealKey={revealKey}>
        <div className="rulebook-entry-grid">
          {visibleAbilities.map((effectiveAbility) => (
            <details className="rulebook-entry ability-entry" key={effectiveAbility.id}>
              <summary><span className="entry-icon">{effectiveAbility.icon}</span><span><strong>{effectiveAbility.name}</strong><small>Player ability</small></span></summary>
              <p>{effectiveAbility.summary}</p>
              <ConfiguredParameterList parameters={effectiveAbility.configuredParameters} />
              <ul>{effectiveAbility.details.map((detail) => <li key={detail}>{detail}</li>)}</ul>
            </details>
          ))}
        </div>
        {!visibleAbilities.length ? <p className="rulebook-empty">No matching abilities in this configuration.</p> : null}
      </RulebookSection>

      <RulebookSection id="rulebook-gambit" title={`${catalog.gambit.icon} ${catalog.gambit.name}`} description={catalog.gambit.summary} revealKey={revealKey}>
        {showGambit ? <div className="rulebook-gambit-copy">
          <ol>{catalog.gambit.details.map((detail) => <li key={detail}>{detail}</li>)}</ol>
          <div>
            <h4>Draft Gambit</h4>
            <ol>{catalog.gambit.draftDetails.map((detail) => <li key={detail}>{detail}</li>)}</ol>
          </div>
        </div> : <p className="rulebook-empty">No matching Gambit rules in this configuration.</p>}
      </RulebookSection>

      <RulebookSection title="Turns And Countdowns" description="How timed effects are counted." className="countdown-reference" revealKey={revealKey}>
        {showCountdowns
          ? <p>{countdownCopy}</p>
          : <p className="rulebook-empty">No matching countdown rules in this configuration.</p>}
      </RulebookSection>
    </section>
  );
}

function CustomizationPanel({ onCreate, initialPreset = "" }) {
  const [catalog, setCatalog] = useState(null);
  const [draft, setDraft] = useState(null);
  const [configurationBaseline, setConfigurationBaseline] = useState(null);
  const [selectedTool, setSelectedTool] = useState(null);
  const [boardHistory, setBoardHistory] = useState([]);
  const [restoreFormationId, setRestoreFormationId] = useState("classic");
  const [creatingMode, setCreatingMode] = useState("");
  const [error, setError] = useState("");
  const [sectionQuery, setSectionQuery] = useState("");
  const [pieceFilter, setPieceFilter] = useState("all");
  const [openSections, setOpenSections] = useState(initialSectionVisibility);
  const [highlightedIssueSquares, setHighlightedIssueSquares] = useState([]);
  const [placementNotice, setPlacementNotice] = useState("");
  const issueSquareTimerRef = useRef(null);
  const placementNoticeTimerRef = useRef(null);
  const settingHighlightTimerRef = useRef(null);
  const [validation, setValidation] = useState({ status: "loading", valid: false, errors: [], warnings: [], disabledOptions: {}, requestKey: null });
  const predictorCompatible = useMemo(() => isExactClassicDraft(draft), [draft]);
  const validationRequest = useMemo(() => (draft ? buildRequest(draft) : null), [draft]);
  const validationRequestKey = useMemo(
    () => (validationRequest ? JSON.stringify(validationRequest) : null),
    [validationRequest]
  );
  const customizeSearchResults = useMemo(
    () => matchingCustomizeResults(sectionQuery, catalog || {}),
    [catalog, sectionQuery]
  );
  const filteredPieces = useMemo(
    () => visibleCustomizePieces(
      catalog?.pieces || [],
      draft?.enabledPieces || [],
      pieceFilter
    ),
    [catalog, draft?.enabledPieces, pieceFilter]
  );
  const currentValidationErrors = (
    validation.status === "invalid"
    && validation.requestKey === validationRequestKey
  ) ? validation.errors : [];
  const sectionStatuses = useMemo(
    () => configurationSectionStatuses(
      draft,
      configurationBaseline,
      currentValidationErrors
    ),
    [configurationBaseline, currentValidationErrors, draft]
  );

  useEffect(() => {
    let cancelled = false;
    getCatalog()
      .then((payload) => {
        if (cancelled) return;
        let initial = loadSavedDraft(payload);
        const preset = payload.popularModes.find((mode) => mode.id === initialPreset);
        if (preset) initial = applyModeToDraft(initial, preset, payload);
        setRestoreFormationId(
          initial.formationId && initial.formationId !== "custom"
            ? initial.formationId
            : "classic"
        );
        setConfigurationBaseline(cloneDraft(initial));
        setCatalog(payload);
        setDraft(initial);
      })
      .catch((requestError) => setError(requestError.message));
    return () => { cancelled = true; };
  }, [initialPreset]);

  useEffect(() => {
    try {
      window.sessionStorage.setItem(
        SECTION_VISIBILITY_STORAGE_KEY,
        JSON.stringify(openSections)
      );
    } catch {
      // Section controls still work when browser storage is unavailable.
    }
  }, [openSections]);

  useEffect(() => {
    if (!validationRequest || !validationRequestKey) return undefined;
    let cancelled = false;
    setValidation((current) => ({ ...current, status: "checking", requestKey: null }));
    const timer = window.setTimeout(() => {
      validateGameConfiguration(validationRequest)
        .then((result) => {
          if (!cancelled) {
            setValidation({
              status: result.valid ? "valid" : "invalid",
              ...result,
              requestKey: validationRequestKey,
            });
          }
        })
        .catch((requestError) => {
          if (!cancelled) {
            setValidation({ status: "invalid", valid: false, errors: [requestError.message], warnings: [], disabledOptions: {}, requestKey: null });
          }
        });
    }, 250);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [validationRequest, validationRequestKey]);

  useEffect(() => {
    setHighlightedIssueSquares([]);
    window.clearTimeout(issueSquareTimerRef.current);
  }, [validationRequestKey]);

  useEffect(() => {
    if (!draft || predictorCompatible || !draft.matchPredictorEnabled) return;
    setDraft((current) => ({ ...current, matchPredictorEnabled: false }));
  }, [draft, predictorCompatible]);

  useEffect(() => () => {
    window.clearTimeout(issueSquareTimerRef.current);
    window.clearTimeout(placementNoticeTimerRef.current);
    window.clearTimeout(settingHighlightTimerRef.current);
  }, []);

  const definitionMap = useMemo(
    () => new Map((catalog?.pieces || []).map((piece) => [piece.type, piece])),
    [catalog]
  );

  if (!catalog || !draft) {
    if (error) {
      return <section className="customization-panel studio-loading"><h2>Customization Unavailable</h2><p>{error}</p></section>;
    }
    return <PageSkeleton variant="customize" embedded />;
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
    const nextDraft = applyModeToDraft(draft, mode, catalog);
    setSelectedTool(null);
    setBoardHistory([]);
    setRestoreFormationId(mode.formationId || "classic");
    setConfigurationBaseline(cloneDraft(nextDraft));
    setDraft(nextDraft);
  };

  const applyFormation = (formation) => {
    const nextDraft = applyFormationToDraft(draft, formation, catalog);
    setSelectedTool(null);
    setBoardHistory([]);
    setRestoreFormationId(formation.id);
    setConfigurationBaseline(cloneDraft(nextDraft));
    setDraft(nextDraft);
  };

  const changeDimensions = (nextRows, nextCols) => {
    const rows = clamp(nextRows, MIN_DIMENSION, MAX_DIMENSION);
    const cols = clamp(nextCols, MIN_DIMENSION, MAX_DIMENSION);
    setBoardHistory([]);
    setRestoreFormationId("classic");
    setDraft((current) => {
      return {
        ...current,
        presetId: "custom",
        formationId: "custom",
        boardRows: rows,
        boardCols: cols,
        barricadeCount: Math.min(current.barricadeCount, Math.max(1, Math.floor(cols / 2))),
        placements: centeredResize(current.placements, current.boardRows, current.boardCols, rows, cols),
        specialAbilities: {
          ...current.specialAbilities,
          parameters: resizeDynamicParameterDefaults(
            current.specialAbilities.parameters,
            catalog.specialAbilities,
            { rows: current.boardRows, cols: current.boardCols },
            { rows, cols }
          ),
        },
        gambit: {
          ...current.gambit,
          setupRows: Math.min(current.gambit.setupRows, Math.max(1, Math.floor(rows / 2))),
        },
      };
    });
  };

  const togglePiece = (pieceType, enabled) => {
    if (pieceType === "king" && !enabled) return;
    setBoardHistory([]);
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
    const restriction = boardPlacementRestriction(draft, selectedTool, row, col);
    window.clearTimeout(placementNoticeTimerRef.current);
    if (restriction) {
      setPlacementNotice(restriction);
      placementNoticeTimerRef.current = window.setTimeout(
        () => setPlacementNotice(""),
        3600
      );
      return;
    }
    setPlacementNotice("");
    setBoardHistory((history) => [
      ...history,
      { placements: draft.placements },
    ].slice(-40));
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
    if (!draft.placements.length) return;
    setSelectedTool(null);
    setBoardHistory((history) => [
      ...history,
      { placements: draft.placements },
    ].slice(-40));
    setDraft((current) => ({
      ...current,
      presetId: "custom",
      formationId: "custom",
      placements: [],
    }));
  };

  const clearColor = (color) => {
    if (!draft.placements.some((piece) => piece.color === color)) return;
    setSelectedTool(null);
    setBoardHistory((history) => [
      ...history,
      { placements: draft.placements },
    ].slice(-40));
    setDraft((current) => ({
      ...current,
      presetId: "custom",
      formationId: "custom",
      placements: current.placements.filter((piece) => piece.color !== color),
    }));
  };

  const mirrorColor = (sourceColor) => {
    const targetColor = sourceColor === "white" ? "black" : "white";
    const sourcePieces = draft.placements.filter((piece) => piece.color === sourceColor);
    if (!sourcePieces.length) return;
    setSelectedTool(null);
    setBoardHistory((history) => [
      ...history,
      { placements: draft.placements },
    ].slice(-40));
    setDraft((current) => {
      const retained = current.placements.filter((piece) => piece.color !== targetColor);
      const occupied = new Set(retained.map((piece) => `${piece.row}-${piece.col}`));
      const reserved = new Set(
        (current.enabledPieces.includes("barricade")
          ? barricadeSquares(current.boardRows, current.boardCols, current.barricadeCount)
          : []
        ).map((square) => `${square.row}-${square.col}`)
      );
      const mirrored = sourcePieces
        .map((piece) => ({
          ...piece,
          row: current.boardRows - 1 - piece.row,
          color: targetColor,
        }))
        .filter((piece) => {
          const key = `${piece.row}-${piece.col}`;
          if (occupied.has(key) || reserved.has(key)) return false;
          occupied.add(key);
          return true;
        });
      return {
        ...current,
        presetId: "custom",
        formationId: "custom",
        placements: [...retained, ...mirrored],
      };
    });
  };

  const undoBoard = () => {
    const previous = boardHistory[boardHistory.length - 1];
    if (!previous) return;
    setSelectedTool(null);
    setBoardHistory((history) => history.slice(0, -1));
    setDraft((current) => ({
      ...current,
      presetId: "custom",
      formationId: "custom",
      placements: previous.placements,
    }));
  };

  const restoreFormation = () => {
    const formation = catalog.formations.find(
      (item) => item.id === restoreFormationId
        && item.boardRows === draft.boardRows
        && item.boardCols === draft.boardCols
    );
    const targetId = formation?.id || "classic";
    const placements = formationLayout(
      catalog,
      targetId,
      draft.boardRows,
      draft.boardCols
    );
    setSelectedTool(null);
    setBoardHistory((history) => [
      ...history,
      { placements: draft.placements },
    ].slice(-40));
    setRestoreFormationId(targetId);
    setDraft((current) => ({
      ...current,
      presetId: targetId,
      formationId: targetId,
      placements,
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

  const setSectionOpen = (sectionId, open) => {
    if (!CONFIGURATION_SECTION_IDS.includes(sectionId)) return;
    setOpenSections((current) => (
      current[sectionId] === open ? current : { ...current, [sectionId]: open }
    ));
  };

  const setAllSectionsOpen = (open) => {
    setOpenSections(Object.fromEntries(
      CONFIGURATION_SECTION_IDS.map((sectionId) => [sectionId, open])
    ));
  };

  const resetStudioSection = (sectionId) => {
    if (!configurationBaseline) return;
    if (["studio-board-size", "studio-pieces"].includes(sectionId)) {
      setSelectedTool(null);
      setBoardHistory([]);
    }
    setDraft((current) => {
      let next = current;
      if (sectionId === "studio-popular-modes") {
        next = {
          ...current,
          matchPredictorEnabled: configurationBaseline.matchPredictorEnabled,
        };
      } else if (sectionId === "studio-board-size") {
        const rows = configurationBaseline.boardRows;
        const cols = configurationBaseline.boardCols;
        next = {
          ...current,
          boardRows: rows,
          boardCols: cols,
          barricadeCount: Math.min(
            current.barricadeCount,
            Math.max(1, Math.floor(cols / 2))
          ),
          placements: centeredResize(
            current.placements,
            current.boardRows,
            current.boardCols,
            rows,
            cols
          ),
          specialAbilities: {
            ...current.specialAbilities,
            parameters: resizeDynamicParameterDefaults(
              current.specialAbilities.parameters,
              catalog.specialAbilities,
              { rows: current.boardRows, cols: current.boardCols },
              { rows, cols }
            ),
          },
          gambit: {
            ...current.gambit,
            setupRows: Math.min(
              current.gambit.setupRows,
              Math.max(1, Math.floor(rows / 2))
            ),
          },
        };
      } else if (sectionId === "studio-pieces") {
        next = {
          ...current,
          enabledPieces: cloneDraft(configurationBaseline.enabledPieces),
          pieceParameters: cloneDraft(configurationBaseline.pieceParameters),
          pointValues: cloneDraft(configurationBaseline.pointValues),
          pieceCaps: cloneDraft(configurationBaseline.pieceCaps),
          barricadeCount: Math.min(
            configurationBaseline.barricadeCount,
            Math.max(1, Math.floor(current.boardCols / 2))
          ),
          placements: centeredResize(
            configurationBaseline.placements,
            configurationBaseline.boardRows,
            configurationBaseline.boardCols,
            current.boardRows,
            current.boardCols
          ),
          victory: {
            ...current.victory,
            kingPoints: configurationBaseline.pointValues.king,
          },
        };
      } else if (sectionId === "studio-victory") {
        next = synchronizeKingPointValue(
          {
            ...current,
            victory: cloneDraft(configurationBaseline.victory),
          },
          configurationBaseline.pointValues.king,
          catalog.limits.pointMax
        );
      } else if (sectionId === "studio-custom-rules") {
        next = {
          ...current,
          customRules: cloneDraft(configurationBaseline.customRules),
        };
      } else if (sectionId === "studio-abilities") {
        const baselineAbilities = cloneDraft(configurationBaseline.specialAbilities);
        next = {
          ...current,
          specialAbilities: {
            ...baselineAbilities,
            parameters: resizeDynamicParameterDefaults(
              baselineAbilities.parameters,
              catalog.specialAbilities,
              {
                rows: configurationBaseline.boardRows,
                cols: configurationBaseline.boardCols,
              },
              { rows: current.boardRows, cols: current.boardCols }
            ),
          },
        };
      } else if (sectionId === "studio-gambit") {
        next = {
          ...current,
          gambit: {
            ...cloneDraft(configurationBaseline.gambit),
            setupRows: Math.min(
              configurationBaseline.gambit.setupRows,
              Math.max(1, Math.floor(current.boardRows / 2))
            ),
          },
        };
      }
      return reconcileDraftIdentity(next, configurationBaseline);
    });
  };

  const create = async (mode) => {
    setCreatingMode(mode);
    setError("");
    const request = buildRequest(draft, mode);
    try {
      if (
        validation.status !== "valid" ||
        !validation.valid ||
        validation.requestKey !== validationRequestKey
      ) {
        setError("Wait for the current configuration check to finish.");
        setCreatingMode("");
        return;
      }
      await onCreate(request);
    } catch (requestError) {
      setError(requestError.message);
      setCreatingMode("");
    }
  };

  const canLaunch =
    validation.status === "valid" &&
    validation.valid &&
    validation.requestKey === validationRequestKey &&
    !creatingMode;
  const validationSummary =
    validation.status === "checking" || validation.status === "loading"
      ? "Checking configuration..."
      : validation.valid
        ? "Configuration valid"
        : `${validation.errors.length} setting issue${validation.errors.length === 1 ? "" : "s"}`;
  const briefingConfiguration = {
    presetId: draft.presetId,
    formationId: draft.formationId,
    enabledPieces: draft.enabledPieces,
    victory: draft.victory,
    customRules: draft.customRules,
    specialAbilities: draft.specialAbilities,
    gambit: draft.gambit,
  };

  const focusValidationIssue = (message) => {
    const { sectionId, settingKey } = locateConfigurationIssue(message);
    const issueSquares = configurationIssueSquares(message, draft);
    window.clearTimeout(issueSquareTimerRef.current);
    setHighlightedIssueSquares(issueSquares);
    if (issueSquares.length) {
      issueSquareTimerRef.current = window.setTimeout(
        () => setHighlightedIssueSquares([]),
        2600
      );
    }
    const section = document.getElementById(sectionId);
    setSectionOpen(sectionId, true);
    if (section instanceof HTMLDetailsElement) section.open = true;

    window.requestAnimationFrame(() => {
      const target = document.querySelector(`[data-setting-key="${settingKey}"]`) || section;
      if (!target) return;
      document.querySelectorAll(".configuration-issue-highlight").forEach(
        (element) => element.classList.remove("configuration-issue-highlight")
      );
      window.clearTimeout(settingHighlightTimerRef.current);
      target.classList.add("configuration-issue-highlight");
      target.scrollIntoView({ behavior: "smooth", block: "center" });
      const focusTarget = target.matches("button, input, select")
        ? target
        : target.querySelector("input, select, button");
      window.setTimeout(() => focusTarget?.focus({ preventScroll: true }), 350);
      settingHighlightTimerRef.current = window.setTimeout(
        () => target.classList.remove("configuration-issue-highlight"),
        2600
      );
    });
  };

  const jumpToCustomizeResult = (result) => {
    const sectionId = result.sectionId || result.id;
    const section = document.getElementById(sectionId);
    if (!section) return;
    if (result.kind === "piece" && result.pieceFilter) {
      setPieceFilter(result.pieceFilter);
    }
    setSectionOpen(sectionId, true);
    if (section instanceof HTMLDetailsElement) section.open = true;
    window.requestAnimationFrame(() => {
      const target = document.getElementById(result.targetId) || section;
      document.querySelectorAll(".customize-search-highlight").forEach(
        (element) => element.classList.remove("customize-search-highlight")
      );
      window.clearTimeout(settingHighlightTimerRef.current);
      if (target !== section) target.classList.add("customize-search-highlight");
      target.scrollIntoView({
        behavior: "smooth",
        block: target === section ? "start" : "center",
      });
      window.setTimeout(
        () => {
          const focusTarget = target.matches("button, input, select")
            ? target
            : target.querySelector("input, select, button")
              || section.querySelector("summary");
          focusTarget?.focus({ preventScroll: true });
        },
        350
      );
      if (target !== section) {
        settingHighlightTimerRef.current = window.setTimeout(
          () => target.classList.remove("customize-search-highlight"),
          2600
        );
      }
    });
  };

  const studioSectionProps = (sectionId) => ({
    open: openSections[sectionId],
    onOpenChange: (open) => setSectionOpen(sectionId, open),
    onReset: () => resetStudioSection(sectionId),
    status: sectionStatuses[sectionId],
  });

  return (
    <section className="customization-panel configuration-studio">
      <header className="studio-hero">
        <div className="studio-hero-copy"><span className="eyebrow">Configuration Studio</span><h1>Build Your Version Of Chass</h1><p>Choose a starting system, then adjust the board, pieces, victory rule, abilities, or Gambit setup.</p></div>
        <CustomizeNavigator
          query={sectionQuery}
          results={customizeSearchResults}
          sectionStatuses={sectionStatuses}
          onQueryChange={setSectionQuery}
          onNavigate={jumpToCustomizeResult}
          onExpandAll={() => setAllSectionsOpen(true)}
          onCollapseAll={() => setAllSectionsOpen(false)}
        />
      </header>

      <div className="studio-shell">
        <aside className="studio-preview-column">
          <ConfigurationBoard
            draft={draft}
            catalog={catalog}
            selectedTool={selectedTool}
            onSelectTool={(tool) => {
              setPlacementNotice("");
              setSelectedTool(tool);
            }}
            onPlace={placeTool}
            onClearBoard={clearBoard}
            onClearColor={clearColor}
            onMirror={mirrorColor}
            onUndo={undoBoard}
            canUndo={Boolean(boardHistory.length)}
            onRestore={restoreFormation}
            highlightedIssueSquares={highlightedIssueSquares}
            placementNotice={placementNotice}
          />
        </aside>

        <div className="studio-controls">
          <CollapsibleStudioSection sectionId="studio-popular-modes" title="Starting Systems" description="Choose the overall game setup. You can then change its board, pieces, victory rule, and other settings." {...studioSectionProps("studio-popular-modes")}>
            <div className="mode-preset-grid" data-setting-key="popular-modes">
              {catalog.popularModes.map((mode) => (
                <article
                  key={mode.id}
                  id={`customize-mode-${mode.id}`}
                  className={`mode-preset-card ${configurationBaseline?.presetId === mode.id ? "selected" : ""}`}
                >
                  <button type="button" className="mode-preset-choice" onClick={() => applyPopularMode(mode)}>
                    <i>{mode.icon}</i><strong>{mode.name}</strong><small>{mode.summary}</small>
                  </button>
                  {mode.id === "classic" ? (
                    <label id="customize-match-predictor" className={`classic-predictor-toggle ${predictorCompatible ? "" : "is-disabled"}`}>
                      <input
                        type="checkbox"
                        checked={predictorCompatible && draft.matchPredictorEnabled}
                        disabled={!predictorCompatible}
                        onChange={(event) => setDraft((current) => ({
                          ...current,
                          matchPredictorEnabled: event.target.checked,
                        }))}
                      />
                      <span>
                        <strong>Enable Match Predictor</strong>
                        <small>{predictorCompatible
                          ? "Live Stockfish White and Black outcome estimates after every move."
                          : "Select untouched Classic Chass settings to enable analysis."}</small>
                      </span>
                    </label>
                  ) : null}
                </article>
              ))}
            </div>
            <div id="customize-popular-formations">
              <h3 className="formation-heading">Popular Board Formations</h3>
              <p className="formation-description">Change the starting piece arrangement without selecting a different overall game system.</p>
              <div className="mode-preset-grid formation-grid">
                {catalog.formations.map((formation) => <button type="button" id={`customize-formation-${formation.id}`} key={formation.id} className={configurationBaseline?.formationId === formation.id ? "selected" : ""} onClick={() => applyFormation(formation)}><i>{formation.icon}</i><strong>{formation.name}</strong><small>{formation.summary}</small></button>)}
              </div>
            </div>
          </CollapsibleStudioSection>

          <CollapsibleStudioSection sectionId="studio-board-size" title="Board Size" description="Choose a preset or set dimensions from 4 to 16." {...studioSectionProps("studio-board-size")}>
            <div className="dimension-presets" data-setting-key="board-dimensions" id="customize-board-dimensions">
              {[8, 10, 16].map((size) => <button type="button" key={size} className={draft.boardRows === size && draft.boardCols === size ? "active" : "secondary"} onClick={() => changeDimensions(size, size)}>{size}x{size}</button>)}
              <span>Custom</span>
              <label>Rows<input type="number" min={MIN_DIMENSION} max={MAX_DIMENSION} value={draft.boardRows} onChange={(event) => changeDimensions(event.target.value, draft.boardCols)} /></label>
              <label>Columns<input type="number" min={MIN_DIMENSION} max={MAX_DIMENSION} value={draft.boardCols} onChange={(event) => changeDimensions(draft.boardRows, event.target.value)} /></label>
            </div>
          </CollapsibleStudioSection>

          <CollapsibleStudioSection sectionId="studio-pieces" title="Pieces" description="Enable pieces, set values of zero or more, and edit the starting board." {...studioSectionProps("studio-pieces")}>
            <div className="piece-filter-bar" aria-label="Filter available pieces">
              {PIECE_FILTERS.map((filter) => (
                <button
                  type="button"
                  key={filter.id}
                  className={pieceFilter === filter.id ? "active" : ""}
                  aria-pressed={pieceFilter === filter.id}
                  onClick={() => setPieceFilter(filter.id)}
                >
                  {filter.label}
                </button>
              ))}
            </div>
            <div className="piece-catalog-grid">
              {filteredPieces.map((piece) => {
                const enabled = draft.enabledPieces.includes(piece.type);
                const effectivePiece = effectiveCatalogEntry(
                  piece,
                  draft.pieceParameters[piece.type]
                );
                return (
                  <article id={`customize-piece-${piece.type}`} key={piece.type} className={`piece-config-card ${enabled ? "enabled" : ""} ${piece.isCustom ? "custom" : ""}`}>
                    <header><span><PieceGlyph type={piece.type} color="black" symbol={piece.symbols.black || piece.icon} /></span><div><h3>{piece.name}</h3><small>{piece.isCustom ? "Custom Piece" : "Classic Piece"}</small></div><input aria-label={`Enable ${piece.name}`} type="checkbox" checked={enabled} disabled={piece.type === "king"} onChange={(event) => togglePiece(piece.type, event.target.checked)} /></header>
                    <p>{effectivePiece.description}</p><small className="movement-copy">{effectivePiece.movement}</small>
                    <TunableParameterFields
                      parameters={piece.tunableParameters}
                      values={draft.pieceParameters[piece.type]}
                      disabled={!enabled}
                      boardRows={draft.boardRows}
                      boardCols={draft.boardCols}
                      onChange={(nextValues) => setDraft((current) => ({
                        ...current,
                        presetId: "custom",
                        pieceParameters: {
                          ...current.pieceParameters,
                          [piece.type]: nextValues,
                        },
                      }))}
                    />
                    <div className="piece-config-fields">
                      <label>Point Value<input type="number" min="0" max={catalog.limits.pointMax} step="1" disabled={!enabled} value={draft.pointValues[piece.type]} onChange={(event) => setDraft((current) => updatePiecePointValue(current, piece.type, event.target.value, catalog.limits.pointMax))} /></label>
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

          <CollapsibleStudioSection sectionId="studio-victory" title="End Game Logic" description="Choose the condition that decides the result." {...studioSectionProps("studio-victory")}>
            <div className="victory-grid" data-setting-key="victory-mode">
              {catalog.victoryModes.map((mode) => {
                const reason = disabledVictoryModes[mode.id];
                return <button type="button" id={`customize-victory-${mode.id}`} key={mode.id} className={draft.victory.mode === mode.id ? "selected" : ""} disabled={Boolean(reason)} title={reason || ""} onClick={() => setDraft((current) => ({ ...current, presetId: "custom", victory: { ...current.victory, mode: mode.id } }))}><i>{mode.icon}</i><span><strong>{mode.name}</strong><small>{reason || mode.summary}</small></span></button>;
              })}
            </div>
            <div className="conditional-fields">
              {draft.victory.mode === "point_race" ? <label data-setting-key="target-points">Target Score<input type="number" min="1" value={draft.victory.targetPoints} onChange={(event) => setDraft((current) => ({ ...current, presetId: "custom", victory: { ...current.victory, targetPoints: Math.max(1, Number(event.target.value)) } }))} /><small>Captured-piece points needed to win.</small></label> : null}
              {draft.victory.mode === "timed" ? <label>Minutes Per Player<input type="number" min="1" max="1440" value={Math.round(draft.victory.timeSeconds / 60)} onChange={(event) => setDraft((current) => ({ ...current, presetId: "custom", victory: { ...current.victory, timeSeconds: Math.max(60, Number(event.target.value) * 60) } }))} /><small>The server controls both clocks.</small></label> : null}
              {draft.victory.mode === "center_dominion" ? <label>Rounds To Hold<input type="number" min="1" max="20" value={draft.victory.dominionRounds} onChange={(event) => setDraft((current) => ({ ...current, presetId: "custom", victory: { ...current.victory, dominionRounds: clamp(event.target.value, 1, 20) } }))} /><small>Marked squares begin empty, then must stay occupied through this many opponent turns. Checkmate also wins.</small></label> : null}
              {draft.victory.mode === "check_race" ? <label>Checks To Win<input type="number" min="1" max="100" value={draft.victory.checkTarget} onChange={(event) => setDraft((current) => ({ ...current, presetId: "custom", victory: { ...current.victory, checkTarget: clamp(event.target.value, 1, 100) } }))} /><small>The first player to give this many checks wins. Checkmate also wins immediately.</small></label> : null}
              {["point_race", "royal_score"].includes(draft.victory.mode) ? <label>King Point Value<input type="number" min="0" max={catalog.limits.pointMax} value={draft.pointValues.king} onChange={(event) => setDraft((current) => ({ ...synchronizeKingPointValue(current, event.target.value, catalog.limits.pointMax), presetId: "custom" }))} /><small>Shared with the King Point Value in Pieces. Zero is allowed.</small></label> : null}
            </div>
          </CollapsibleStudioSection>

          <CollapsibleStudioSection sectionId="studio-custom-rules" title="Custom Rules" description="Add optional board-wide systems to any game mode." className="ability-config-section" {...studioSectionProps("studio-custom-rules")}>
            <div id="customize-affinity-squares">
              <Toggle settingKey="affinity-rules" checked={draft.customRules.affinityEnabled} onChange={(affinityEnabled) => setDraft((current) => ({ ...current, presetId: "custom", customRules: { ...current.customRules, affinityEnabled } }))} label="Enable Affinity Squares" description="Begin with the marked center empty, then control both squares of your color to earn command points." />
              {draft.customRules.affinityEnabled ? <div className="conditional-fields">
                <label>Command Point Cap<input type="number" min="0" max="20" value={draft.customRules.commandPointCap} onChange={(event) => setDraft((current) => ({ ...current, presetId: "custom", customRules: { ...current.customRules, commandPointCap: clamp(event.target.value, 0, 20) } }))} /><small>Maximum command points a player may save. The default is 3.</small></label>
              </div> : null}
            </div>
          </CollapsibleStudioSection>

          <CollapsibleStudioSection sectionId="studio-abilities" title="Special Abilities" description="Each player privately chooses the configured number of allowed abilities before play." className="ability-config-section" {...studioSectionProps("studio-abilities")}>
            <Toggle settingKey="ability-options" checked={draft.specialAbilities.enabled} onChange={toggleSpecialAbilities} label="Enable Special Abilities" description="All compatible abilities start enabled. Selections are revealed after both players lock in." />
            {draft.specialAbilities.enabled ? <>
              <div className="conditional-fields" id="customize-ability-count"><label>Abilities Per Player<input type="number" min="1" max={Math.max(1, draft.specialAbilities.allowed.length)} value={draft.specialAbilities.maxPerPlayer} onChange={(event) => setDraft((current) => ({ ...current, presetId: "custom", specialAbilities: { ...current.specialAbilities, maxPerPlayer: clamp(event.target.value, 1, Math.max(1, current.specialAbilities.allowed.length)) } }))} /><small>How many abilities each player selects. The default is 1.</small></label></div>
              <div className="ability-option-grid" data-setting-key="ability-options">{catalog.specialAbilities.map((ability) => {
                const enabled = draft.specialAbilities.allowed.includes(ability.id);
                const reason = disabledAbilities[ability.id];
                const effectiveAbility = effectiveCatalogEntry(
                  ability,
                  draft.specialAbilities.parameters[ability.id]
                );
                return (
                  <article id={`customize-ability-${ability.id}`} key={ability.id} className={`ability-config-card ${enabled ? "selected" : ""}`}>
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
                      boardRows={draft.boardRows}
                      boardCols={draft.boardCols}
                      onChange={(nextValues) => setDraft((current) => ({
                        ...current,
                        presetId: "custom",
                        specialAbilities: {
                          ...current.specialAbilities,
                          parameters: {
                            ...current.specialAbilities.parameters,
                            [ability.id]: nextValues,
                          },
                        },
                      }))}
                    />
                  </article>
                );
              })}</div>
            </> : null}
          </CollapsibleStudioSection>

          <CollapsibleStudioSection sectionId="studio-gambit" title="Chass Gambit Settings" description="Configure private army construction for the current board and ruleset." className="gambit-config-section" {...studioSectionProps("studio-gambit")}>
            <Toggle checked={draft.gambit.enabled} onChange={(enabled) => setDraft((current) => ({ ...current, presetId: enabled ? "gambit" : "custom", formationId: enabled ? "classic" : "custom", gambit: { ...current.gambit, enabled, draftEnabled: enabled ? current.gambit.draftEnabled : false } }))} label="Enable Chass Gambit" description="Each player builds an army in their closest home rows without exceeding the point limit." />
            {draft.gambit.enabled ? <div className="gambit-settings-grid" data-setting-key="gambit-settings" id="customize-gambit-settings">
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
        <div className="launch-validation-copy">
          <span>Ready To Launch</span>
          <strong>{validationSummary}</strong>
          {validation.errors.length ? (
            <div className="validation-inline-issues" aria-label="Configuration issues">
              {validation.errors.map((issue, index) => (
                <button type="button" key={`${issue}-${index}`} onClick={() => focusValidationIssue(issue)}>
                  <b>{index + 1}</b>{issue}
                </button>
              ))}
            </div>
          ) : (
            validation.warnings[0] ? <small>{validation.warnings[0]}</small> : null
          )}
        </div>
        <GameBriefing
          boardRows={draft.boardRows}
          boardCols={draft.boardCols}
          configuration={briefingConfiguration}
          catalog={catalog}
          className="studio-launch-summary"
        />
        <div className="launch-actions"><button type="button" disabled={!canLaunch} onClick={() => create("local")}>{creatingMode === "local" ? "Building..." : "Start Local Game"}</button><button type="button" className="secondary" disabled={!canLaunch} onClick={() => create("online")}>{creatingMode === "online" ? "Creating Invite..." : "Create Online Game"}</button></div>
      </section>
      {error ? <p className="studio-error">{error}</p> : null}
      <Rulebook catalog={catalog} draft={draft} />
    </section>
  );
}

export default CustomizationPanel;
