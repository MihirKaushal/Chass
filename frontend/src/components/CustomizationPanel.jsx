import { useEffect, useMemo, useRef, useState } from "react";

import { getCatalog, validateGameConfiguration } from "../api/gameApi";
import { barricadeSquares, significantCenterSquares } from "../boardGeometry";
import { availableBotProfiles } from "../botGame";
import { boardPlacementRestriction } from "../customizeBoardPlacement";
import { configurationIssueSquares, locateConfigurationIssue } from "../configurationIssues";
import { customizeLaunchState } from "../customizeLaunchState";
import {
  matchingCustomizeResults,
  nextCustomizeResultIndex,
} from "../customizeNavigation";
import {
  clampEvenWholeNumber,
  clampWholeNumber,
  customizeNumericBounds,
  normalizeCustomizeNumbers,
} from "../customizeNumericLimits";
import { PIECE_FILTERS, visibleCustomizePieces } from "../customizePieces";
import {
  resetEnabledCustomRules,
  resetEnabledGambit,
  resetEnabledSpecialAbilities,
} from "../customizeResetDefaults";
import {
  CONFIGURATION_SECTION_IDS,
  configurationSectionStatuses,
  hasConfigurationModifications,
  reconcileDraftIdentity,
  sectionIsModified,
} from "../customizeSectionState";
import {
  savedKingPointValue,
  synchronizeKingPointValue,
  updatePiecePointValue,
} from "../customizationState";
import { matchesRulebookSearch } from "../rulebookSearch";
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
import BotSetupDialog from "./BotSetupDialog";
import PageSkeleton from "./PageSkeleton";
import PieceGlyph from "./PieceGlyph";
import PieceTooltip from "./PieceTooltip";
import Button from "./ui/Button";
import Dialog from "./ui/Dialog";
import Disclosure from "./ui/Disclosure";
import EmptyState from "./ui/EmptyState";
import FormField from "./ui/FormField";
import StatusBadge from "./ui/StatusBadge";

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
    customRules: {
      affinityEnabled: false,
      affinitySquareCount: 4,
      affinityControlRequired: 2,
      commandPointCap: 3,
    },
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
    const boardRows = clamp(
      saved.boardRows ?? base.boardRows,
      catalog.limits.boardMin,
      catalog.limits.boardMax
    );
    const boardCols = clamp(
      saved.boardCols ?? base.boardCols,
      catalog.limits.boardMin,
      catalog.limits.boardMax
    );
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
      matchPredictorEnabled: true,
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
                affinitySquareCount: gambit.affinitySquareCount ?? 4,
                affinityControlRequired: gambit.affinityControlRequired ?? 2,
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
    matchPredictorEnabled: true,
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
      matchPredictorEnabled: true,
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
      affinitySquareCount: draft.customRules.affinitySquareCount,
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

function Toggle({ checked, onChange, label, description, settingKey, disabled = false }) {
  return (
    <label className={`studio-toggle${disabled ? " is-disabled" : ""}`} data-setting-key={settingKey}>
      <input type="checkbox" checked={checked} disabled={disabled} onChange={(event) => onChange(event.target.checked)} />
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
          <FormField
            key={parameter.id}
            label={parameter.label}
            description={`${parameter.description} Default: ${parameterValueLabel(parameter, defaultValue)}.`}
          >
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
          </FormField>
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
        <StatusBadge tone="danger" className="section-status issue">
          {status.issueCount === 1 ? "Issue" : `${status.issueCount} Issues`}
        </StatusBadge>
      ) : null}
      {status.modified ? (
        <StatusBadge tone="info" className="section-status modified">Modified</StatusBadge>
      ) : null}
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
    <Disclosure
      className={`studio-section studio-disclosure ${className}`.trim()}
      id={sectionId}
      open={open}
      onToggle={(event) => onOpenChange(event.currentTarget.open)}
      summary={<SectionHeading title={heading} description={description} status={status} />}
      bodyClassName="studio-disclosure-body"
    >
      <div className="studio-section-actions">
        <Button
          variant="secondary"
          size="small"
          className="section-reset-button"
          disabled={!status?.modified}
          onClick={onReset}
        >
          Reset Section
        </Button>
      </div>
      {children}
    </Disclosure>
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
  const [activeResultIndex, setActiveResultIndex] = useState(-1);
  const menuRef = useRef(null);
  const resultRefs = useRef([]);

  useEffect(() => {
    setActiveResultIndex(-1);
  }, [results]);

  useEffect(() => {
    if (query.trim()) setMenuOpen(true);
  }, [query]);

  useEffect(() => {
    if (!menuOpen) return undefined;

    const closeOutsideMenu = (event) => {
      if (!menuRef.current?.contains(event.target)) setMenuOpen(false);
    };
    document.addEventListener("pointerdown", closeOutsideMenu);
    return () => document.removeEventListener("pointerdown", closeOutsideMenu);
  }, [menuOpen]);

  useEffect(() => {
    if (!menuOpen || activeResultIndex < 0) return;
    resultRefs.current[activeResultIndex]?.scrollIntoView({ block: "nearest" });
  }, [activeResultIndex, menuOpen]);

  const selectActiveResult = () => {
    const result = results[activeResultIndex] || firstResult;
    if (!result) return;
    setMenuOpen(false);
    onNavigate(result);
  };

  return (
    <aside className="customize-section-navigator" aria-label="Customize page navigation">
      <label className="customize-section-search">
        <span className="visually-hidden">Search customize sections and settings</span>
        <input
          type="search"
          role="combobox"
          value={query}
          aria-autocomplete="list"
          aria-controls="customize-jump-options"
          aria-expanded={menuOpen}
          aria-activedescendant={activeResultIndex >= 0
            ? `customize-jump-result-${results[activeResultIndex]?.id}`
            : undefined}
          onChange={(event) => onQueryChange(event.target.value)}
          onFocus={() => {
            if (query.trim()) setMenuOpen(true);
          }}
          onKeyDown={(event) => {
            if (event.key === "ArrowDown" || event.key === "ArrowUp") {
              event.preventDefault();
              setMenuOpen(true);
              setActiveResultIndex((current) => nextCustomizeResultIndex(
                current,
                results.length,
                event.key === "ArrowDown" ? 1 : -1
              ));
            } else if (event.key === "Enter" && firstResult) {
              event.preventDefault();
              selectActiveResult();
            } else if (event.key === "Escape" && menuOpen) {
              event.preventDefault();
              setMenuOpen(false);
              setActiveResultIndex(-1);
            }
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
            <nav aria-label="Customize sections" role="listbox">
              {results.map((result, index) => (
                <a
                  id={`customize-jump-result-${result.id}`}
                  href={`#${result.targetId || result.sectionId}`}
                  key={result.id}
                  role="option"
                  aria-selected={activeResultIndex === index}
                  className={activeResultIndex === index ? "keyboard-active" : ""}
                  ref={(element) => { resultRefs.current[index] = element; }}
                  onMouseEnter={() => setActiveResultIndex(index)}
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
          ) : <EmptyState>No matching section.</EmptyState>}
        </div>
      </div>
      <div className="customize-disclosure-actions" aria-label="Section display controls">
        <button type="button" onClick={onExpandAll}>Expand All</button>
        <button type="button" onClick={onCollapseAll}>Collapse All</button>
      </div>
    </aside>
  );
}

function StartingSystemConfirmation({ mode, onCancel, onConfirm }) {
  return (
    <Dialog
      open={Boolean(mode)}
      onClose={onCancel}
      closeLabel="Close Starting System confirmation"
      eyebrow="Replace Current Setup"
      title={mode ? `Apply ${mode.name}?` : "Apply Starting System?"}
      description="This Starting System will replace your modified settings. This action cannot be undone."
      actions={mode ? (
        <>
          <Button variant="secondary" onClick={onCancel}>
            Keep My Changes
          </Button>
          <Button onClick={onConfirm}>Apply {mode.name}</Button>
        </>
      ) : null}
    />
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

function Rulebook({ catalog, draft, predictorProfile }) {
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
  const predictorCopy = [
    "Match Analysis",
    "Stockfish 18",
    "Fairy-Stockfish",
    "Chass Engine",
    "engine analysis probability parity legal moves terminal outcomes custom pieces abilities",
    predictorProfile,
  ];
  const showPredictor = matchesRulebookSearch(query, predictorCopy);
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
    + Number(showPredictor)
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
          <p>Detailed behavior for every built-in piece, win condition, ability, and Gambit system.</p>
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
          <a href="#rulebook-match-analysis">Match Analysis</a>
          <a href="#rulebook-pieces">Pieces</a>
          <a href="#rulebook-victory">Win Conditions</a>
          <a href="#rulebook-custom-rules">Custom Rules</a>
          <a href="#rulebook-abilities">Abilities</a>
          <a href="#rulebook-gambit">Gambit</a>
        </nav>
      </header>

      <RulebookSection id="rulebook-match-analysis" title="Match Analysis" description="How Chass selects an engine and where each estimate is reliable." revealKey={revealKey}>
        {showPredictor ? (
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
              <p><b>Limits:</b> Its handcrafted evaluation and time-bounded search are experimental. It is weaker than Stockfish, is not trained on self-play data, and does not provide calibrated probabilities.</p>
            </article>
            <p className="predictor-reference-current">
              Current configuration: <strong>{predictorProfile?.engineName || "No compatible engine"}</strong>. {predictorProfile?.accuracy || predictorProfile?.reason || "Finish configuring the game to see automatic engine selection."}
            </p>
          </div>
        ) : <EmptyState className="rulebook-empty">No matching Match Analysis reference.</EmptyState>}
      </RulebookSection>

      <RulebookSection id="rulebook-pieces" title="Piece Encyclopedia" description="Movement, value, and special behavior." revealKey={revealKey}>
        <div className="rulebook-entry-grid">
          {visiblePieces.map((effectivePiece) => (
            <details className="rulebook-entry" key={effectivePiece.type}>
              <summary>
                <span className="entry-icon"><PieceGlyph type={effectivePiece.type} color="black" symbol={effectivePiece.symbols.black || effectivePiece.icon} /></span>
                <span><strong>{effectivePiece.name}</strong><small>{effectivePiece.isCustom ? "Custom Piece" : "Classic Piece"}</small></span>
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
            <p>The board marks {draft.customRules.affinitySquareCount} centered squares, divided equally so each color receives {draft.customRules.affinitySquareCount / 2}.</p>
            <p>Hold {draft.customRules.affinityControlRequired} of your assigned squares through the opponent&apos;s turn to earn one command point.</p>
            <p>Spend one point for a Pawn, two to evolve a Pawn, or three for a Rook. A command uses the normal turn and must leave the King safe.</p>
            <p>Marked center squares must begin empty; only Barricades may start there.</p>
          </div>
          <div>
            <h4>Configuration</h4>
            <p><strong>Affinity squares:</strong> {draft.customRules.affinitySquareCount} total.</p>
            <p><strong>Squares required:</strong> {draft.customRules.affinityControlRequired} per player.</p>
            <p><strong>Command point cap:</strong> {draft.customRules.commandPointCap}. This limits how many unused points a player may save.</p>
          </div>
        </div> : <EmptyState className="rulebook-empty">No matching custom rules in this configuration.</EmptyState>}
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

function CustomizationPanel({ onCreate, initialPreset = "", onModificationChange }) {
  const [catalog, setCatalog] = useState(null);
  const [draft, setDraft] = useState(null);
  const [configurationBaseline, setConfigurationBaseline] = useState(null);
  const [pageEntryBaseline, setPageEntryBaseline] = useState(null);
  const [selectedTool, setSelectedTool] = useState(null);
  const [boardHistory, setBoardHistory] = useState([]);
  const [restoreFormationId, setRestoreFormationId] = useState("classic");
  const [creatingMode, setCreatingMode] = useState("");
  const [error, setError] = useState("");
  const [sectionQuery, setSectionQuery] = useState("");
  const [pieceFilter, setPieceFilter] = useState("all");
  const [openSections, setOpenSections] = useState(initialSectionVisibility);
  const [pendingStartingSystem, setPendingStartingSystem] = useState(null);
  const [highlightedIssueSquares, setHighlightedIssueSquares] = useState([]);
  const [placementNotice, setPlacementNotice] = useState("");
  const [showBotSetup, setShowBotSetup] = useState(false);
  const [botNotice, setBotNotice] = useState("");
  const issueSquareTimerRef = useRef(null);
  const placementNoticeTimerRef = useRef(null);
  const settingHighlightTimerRef = useRef(null);
  const botNoticeTimerRef = useRef(null);
  const [validation, setValidation] = useState({ status: "loading", valid: false, errors: [], warnings: [], disabledOptions: {}, matchPredictor: null, bot: null, requestKey: null });
  const validationRequest = useMemo(() => (draft ? buildRequest(draft) : null), [draft]);
  const validationRequestKey = useMemo(
    () => (validationRequest ? JSON.stringify(validationRequest) : null),
    [validationRequest]
  );
  const predictorProfile = validation.requestKey === validationRequestKey
    ? validation.matchPredictor
    : null;
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
  const pageConfigurationModified = useMemo(
    () => hasConfigurationModifications(
      configurationSectionStatuses(draft, pageEntryBaseline)
    ),
    [draft, pageEntryBaseline]
  );

  useEffect(() => {
    onModificationChange?.(pageConfigurationModified);
  }, [onModificationChange, pageConfigurationModified]);

  useEffect(() => {
    let cancelled = false;
    getCatalog()
      .then((payload) => {
        if (cancelled) return;
        let initial = loadSavedDraft(payload);
        const preset = payload.popularModes.find((mode) => mode.id === initialPreset);
        if (preset) initial = applyModeToDraft(initial, preset, payload);
        initial = normalizeCustomizeNumbers(initial, payload.limits);
        setRestoreFormationId(
          initial.formationId && initial.formationId !== "custom"
            ? initial.formationId
            : "classic"
        );
        setConfigurationBaseline(cloneDraft(initial));
        setPageEntryBaseline(cloneDraft(initial));
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
            setValidation({ status: "invalid", valid: false, errors: [requestError.message], warnings: [], disabledOptions: {}, matchPredictor: null, bot: null, requestKey: null });
          }
        });
    }, 250);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [validationRequest, validationRequestKey]);

  useEffect(() => {
    setHighlightedIssueSquares([]);
    setBotNotice("");
    window.clearTimeout(issueSquareTimerRef.current);
    window.clearTimeout(botNoticeTimerRef.current);
  }, [validationRequestKey]);

  useEffect(() => () => {
    window.clearTimeout(issueSquareTimerRef.current);
    window.clearTimeout(placementNoticeTimerRef.current);
    window.clearTimeout(settingHighlightTimerRef.current);
    window.clearTimeout(botNoticeTimerRef.current);
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
  const numericBounds = customizeNumericBounds(draft, catalog.limits);

  const applyPopularMode = (mode) => {
    const nextDraft = normalizeCustomizeNumbers(
      applyModeToDraft(draft, mode, catalog),
      catalog.limits
    );
    setSelectedTool(null);
    setBoardHistory([]);
    setRestoreFormationId(mode.formationId || "classic");
    setConfigurationBaseline(cloneDraft(nextDraft));
    setDraft(nextDraft);
  };

  const requestPopularMode = (mode) => {
    if (hasConfigurationModifications(sectionStatuses)) {
      setPendingStartingSystem(mode);
      return;
    }
    applyPopularMode(mode);
  };

  const applyFormation = (formation) => {
    const nextDraft = normalizeCustomizeNumbers(
      applyFormationToDraft(draft, formation, catalog),
      catalog.limits
    );
    setSelectedTool(null);
    setBoardHistory([]);
    setRestoreFormationId(formation.id);
    setConfigurationBaseline(cloneDraft(nextDraft));
    setDraft(nextDraft);
  };

  const changeDimensions = (nextRows, nextCols) => {
    const rows = clamp(nextRows, numericBounds.boardMin, numericBounds.boardMax);
    const cols = clamp(nextCols, numericBounds.boardMin, numericBounds.boardMax);
    setBoardHistory([]);
    setRestoreFormationId("classic");
    setDraft((current) => {
      return normalizeCustomizeNumbers({
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
      }, catalog.limits);
    });
  };

  const togglePiece = (pieceType, enabled) => {
    if (pieceType === "king" && !enabled) return;
    setBoardHistory([]);
    setDraft((current) => normalizeCustomizeNumbers({
      ...current,
      presetId: "custom",
      formationId: "custom",
      enabledPieces: enabled
        ? [...new Set([...current.enabledPieces, pieceType])]
        : current.enabledPieces.filter((type) => type !== pieceType),
      placements: enabled
        ? current.placements
        : current.placements.filter((piece) => piece.type !== pieceType),
    }, catalog.limits));
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
        next = current;
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
          customRules: resetEnabledCustomRules(configurationBaseline.customRules),
        };
      } else if (sectionId === "studio-abilities") {
        const baselineAbilities = cloneDraft(configurationBaseline.specialAbilities);
        const resetParameters = resizeDynamicParameterDefaults(
          baselineAbilities.parameters,
          catalog.specialAbilities,
          {
            rows: configurationBaseline.boardRows,
            cols: configurationBaseline.boardCols,
          },
          { rows: current.boardRows, cols: current.boardCols }
        );
        next = {
          ...current,
          specialAbilities: resetEnabledSpecialAbilities({
            defaults: baselineAbilities,
            abilities: catalog.specialAbilities,
            disabledAbilities,
            parameters: resetParameters,
          }),
        };
      } else if (sectionId === "studio-gambit") {
        const resetGambit = resetEnabledGambit(
          cloneDraft(configurationBaseline.gambit),
          current.boardRows
        );
        next = {
          ...current,
          gambit: resetGambit,
          pieceCaps: {
            ...current.pieceCaps,
            queen: resetGambit.maxQueens,
          },
        };
      }
      return reconcileDraftIdentity(
        normalizeCustomizeNumbers(next, catalog.limits),
        configurationBaseline
      );
    });
  };

  const create = async (mode, botSelection = null) => {
    setCreatingMode(mode);
    setError("");
    const request = {
      ...buildRequest(draft, mode),
      ...(botSelection ? { bot: botSelection } : {}),
    };
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

  const configurationReady =
    validation.status === "valid" &&
    validation.valid &&
    validation.requestKey === validationRequestKey;
  const canLaunch = configurationReady && !creatingMode;
  const botCompatibility = validation.requestKey === validationRequestKey
    ? validation.bot
    : null;
  const botEligible = Boolean(configurationReady && botCompatibility?.eligible);
  const botButtonDisabled = !configurationReady || Boolean(creatingMode);
  const openBotSetup = () => {
    if (!canLaunch) return;
    if (!botCompatibility?.eligible) {
      setBotNotice("Bot play is currently available for exact Classic Chass games only.");
      window.clearTimeout(botNoticeTimerRef.current);
      botNoticeTimerRef.current = window.setTimeout(() => setBotNotice(""), 4200);
      return;
    }
    setBotNotice("");
    setShowBotSetup(true);
  };
  const launchState = customizeLaunchState(validation, validationRequestKey);
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
      if (target instanceof HTMLDetailsElement) target.open = true;
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
        <div className="studio-hero-copy"><span className="eyebrow">Game Customizer</span><h1>Build Your Version Of Chass</h1><p>Choose a starting system, then adjust the board, pieces, win condition, abilities, or Gambit setup.</p></div>
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
          <CollapsibleStudioSection sectionId="studio-popular-modes" title="Starting Systems" description="Choose the overall setup, then adjust its board, pieces, win condition, and other settings." {...studioSectionProps("studio-popular-modes")}>
            <div className="mode-preset-grid" data-setting-key="popular-modes">
              {catalog.popularModes.map((mode) => (
                <article
                  key={mode.id}
                  id={`customize-mode-${mode.id}`}
                  className={`mode-preset-card ${configurationBaseline?.presetId === mode.id ? "selected" : ""}`}
                >
                  <button type="button" className="mode-preset-choice" onClick={() => requestPopularMode(mode)}>
                    <i>{mode.icon}</i><strong>{mode.name}</strong><small>{mode.summary}</small>
                  </button>
                </article>
              ))}
            </div>
            <div id="customize-popular-formations">
              <h3 className="formation-heading">Starting Layout Presets</h3>
              <p className="formation-description">Apply a familiar starting arrangement and its compatible board defaults. Win conditions and other systems remain editable below.</p>
              <div className="mode-preset-grid formation-grid">
                {catalog.formations.map((formation) => <button type="button" id={`customize-formation-${formation.id}`} key={formation.id} className={configurationBaseline?.formationId === formation.id ? "selected" : ""} onClick={() => applyFormation(formation)}><i>{formation.icon}</i><strong>{formation.name}</strong><small>{formation.summary}</small></button>)}
              </div>
            </div>
          </CollapsibleStudioSection>

          <CollapsibleStudioSection sectionId="studio-board-size" title="Board Size" description="Choose a preset or set dimensions from 4 to 16." {...studioSectionProps("studio-board-size")}>
            <div className="dimension-presets" data-setting-key="board-dimensions" id="customize-board-dimensions">
              {[8, 10, 16].map((size) => <button type="button" key={size} className={draft.boardRows === size && draft.boardCols === size ? "active" : "secondary"} onClick={() => changeDimensions(size, size)}>{size}x{size}</button>)}
              <span>Custom</span>
              <label>Rows<input type="number" min={numericBounds.boardMin} max={numericBounds.boardMax} step="1" value={draft.boardRows} onChange={(event) => changeDimensions(event.target.value, draft.boardCols)} /></label>
              <label>Columns<input type="number" min={numericBounds.boardMin} max={numericBounds.boardMax} step="1" value={draft.boardCols} onChange={(event) => changeDimensions(draft.boardRows, event.target.value)} /></label>
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
                      <label>Point Value<input type="number" min={numericBounds.pointMin} max={numericBounds.pointMax} step="1" disabled={!enabled} value={draft.pointValues[piece.type]} onChange={(event) => setDraft((current) => normalizeCustomizeNumbers(updatePiecePointValue(current, piece.type, event.target.value, numericBounds.pointMax), catalog.limits))} /></label>
                      {draft.gambit.enabled && piece.type !== "barricade" ? <label>Army Limit<input type="number" min={piece.type === "king" ? 1 : numericBounds.pieceCapMin} max={numericBounds.pieceCapMaximum} step="1" disabled={!enabled || piece.type === "king"} value={draft.pieceCaps[piece.type]} onChange={(event) => setDraft((current) => ({ ...current, presetId: "custom", pieceCaps: { ...current.pieceCaps, [piece.type]: clampWholeNumber(event.target.value, numericBounds.pieceCapMin, numericBounds.pieceCapMaximum) } }))} /></label> : null}
                      {draft.gambit.enabled && draft.gambit.draftEnabled && piece.type !== "barricade" ? <label>{piece.type === "king" ? "Starting Kings" : "Shared Draft Pool"}<input type="number" min={piece.type === "king" ? 2 : numericBounds.draftPoolCountMin} max={numericBounds.draftPoolCountMaximum} step="1" disabled={!enabled || piece.type === "king"} value={draft.gambit.draftPool[piece.type] ?? 0} onChange={(event) => setDraft((current) => ({ ...current, presetId: "custom", gambit: { ...current.gambit, draftPool: { ...current.gambit.draftPool, [piece.type]: clampWholeNumber(event.target.value, numericBounds.draftPoolCountMin, numericBounds.draftPoolCountMaximum) } } }))} /><small>{piece.type === "king" ? "One King is automatically assigned to each army." : "Total copies available to both players."}</small></label> : null}
                      {enabled && piece.type === "barricade" ? <label>Starting Walls<input type="number" min={numericBounds.barricadeCountMinimum} max={numericBounds.barricadeCountMaximum} step="1" value={draft.barricadeCount} onChange={(event) => setDraft((current) => ({ ...current, presetId: "custom", barricadeCount: clampWholeNumber(event.target.value, numericBounds.barricadeCountMinimum, numericBounds.barricadeCountMaximum) }))} /></label> : null}
                    </div>
                    {enabled && !draft.gambit.enabled ? <div className="piece-color-tools">{piece.type === "barricade" ? <p className="fixed-piece-note"><PieceGlyph type="barricade" color="neutral" symbol={piece.symbols.neutral} /> Starting walls occupy reserved central squares.</p> : ["white", "black"].map((color) => <button type="button" key={color} className={selectedTool?.type === piece.type && selectedTool?.color === color ? "active" : "secondary"} onClick={() => setSelectedTool({ kind: "piece", type: piece.type, color })}><PieceGlyph type={piece.type} color={color} symbol={piece.symbols[color] || piece.icon} /> {title(color)}</button>)}</div> : null}
                  </article>
                );
              })}
            </div>
          </CollapsibleStudioSection>

          <CollapsibleStudioSection sectionId="studio-victory" title="Win Condition" description="Choose the condition that decides the result." {...studioSectionProps("studio-victory")}>
            <div className="victory-grid" data-setting-key="victory-mode">
              {catalog.victoryModes.map((mode) => {
                const reason = disabledVictoryModes[mode.id];
                return <button type="button" id={`customize-victory-${mode.id}`} key={mode.id} className={draft.victory.mode === mode.id ? "selected" : ""} disabled={Boolean(reason)} title={reason || ""} onClick={() => setDraft((current) => ({ ...current, presetId: "custom", victory: { ...current.victory, mode: mode.id } }))}><i>{mode.icon}</i><span><strong>{mode.name}</strong><small>{reason || mode.summary}</small></span></button>;
              })}
            </div>
            <div className="conditional-fields">
              {draft.victory.mode === "point_race" ? <label data-setting-key="target-points">Target Score<input type="number" min={numericBounds.targetPointsMin} max={numericBounds.targetPointsMax} step="1" value={draft.victory.targetPoints} onChange={(event) => setDraft((current) => ({ ...current, presetId: "custom", victory: { ...current.victory, targetPoints: clampWholeNumber(event.target.value, numericBounds.targetPointsMin, numericBounds.targetPointsMax) } }))} /><small>Captured-piece points needed to win.</small></label> : null}
              {draft.victory.mode === "timed" ? <label>Minutes Per Player<input type="number" min={numericBounds.timeMinutesMin} max={numericBounds.timeMinutesMax} step="1" value={Math.round(draft.victory.timeSeconds / 60)} onChange={(event) => setDraft((current) => ({ ...current, presetId: "custom", victory: { ...current.victory, timeSeconds: clampWholeNumber(event.target.value, numericBounds.timeMinutesMin, numericBounds.timeMinutesMax) * 60 } }))} /><small>The server controls both clocks.</small></label> : null}
              {draft.victory.mode === "center_dominion" ? <label>Rounds To Hold<input type="number" min={numericBounds.dominionRoundsMin} max={numericBounds.dominionRoundsMax} step="1" value={draft.victory.dominionRounds} onChange={(event) => setDraft((current) => ({ ...current, presetId: "custom", victory: { ...current.victory, dominionRounds: clampWholeNumber(event.target.value, numericBounds.dominionRoundsMin, numericBounds.dominionRoundsMax) } }))} /><small>Marked squares begin empty, then must stay occupied through this many opponent turns. Checkmate also wins.</small></label> : null}
              {draft.victory.mode === "check_race" ? <label>Checks To Win<input type="number" min={numericBounds.checkTargetMin} max={numericBounds.checkTargetMax} step="1" value={draft.victory.checkTarget} onChange={(event) => setDraft((current) => ({ ...current, presetId: "custom", victory: { ...current.victory, checkTarget: clampWholeNumber(event.target.value, numericBounds.checkTargetMin, numericBounds.checkTargetMax) } }))} /><small>The first player to give this many checks wins. Checkmate also wins immediately.</small></label> : null}
              {["point_race", "royal_score"].includes(draft.victory.mode) ? <label>King Point Value<input type="number" min={numericBounds.pointMin} max={numericBounds.pointMax} step="1" value={draft.pointValues.king} onChange={(event) => setDraft((current) => normalizeCustomizeNumbers({ ...synchronizeKingPointValue(current, event.target.value, numericBounds.pointMax), presetId: "custom" }, catalog.limits))} /><small>Shared with the King Point Value in Pieces. Zero is allowed.</small></label> : null}
            </div>
          </CollapsibleStudioSection>

          <CollapsibleStudioSection sectionId="studio-custom-rules" title="Custom Rules" description="Add optional board-wide systems to any compatible match." className="ability-config-section" {...studioSectionProps("studio-custom-rules")}>
            <div id="customize-affinity-squares">
              <Toggle settingKey="affinity-rules" checked={draft.customRules.affinityEnabled} onChange={(affinityEnabled) => setDraft((current) => ({ ...current, presetId: "custom", customRules: { ...current.customRules, affinityEnabled } }))} label="Enable Affinity Squares" description="Begin with centered marked squares empty, then control the configured number of your color to earn command points." />
              {draft.customRules.affinityEnabled ? <div className="conditional-fields">
                <label>Affinity Squares<input type="number" min={numericBounds.affinitySquareCountMin} max={numericBounds.affinitySquareCountMaximum} step="2" value={draft.customRules.affinitySquareCount} onChange={(event) => {
                  const affinitySquareCount = clampEvenWholeNumber(
                    event.target.value,
                    numericBounds.affinitySquareCountMin,
                    numericBounds.affinitySquareCountMaximum
                  );
                  setDraft((current) => ({
                    ...current,
                    presetId: "custom",
                    customRules: {
                      ...current.customRules,
                      affinitySquareCount,
                      affinityControlRequired: Math.min(
                        current.customRules.affinityControlRequired,
                        affinitySquareCount / 2
                      ),
                    },
                  }));
                }} /><small>Total centered squares, divided equally between White and Black. Maximum: twice the board width.</small></label>
                <label>Squares Required<input type="number" min={numericBounds.affinityControlRequiredMin} max={numericBounds.affinityControlRequiredMaximum} step="1" value={draft.customRules.affinityControlRequired} onChange={(event) => setDraft((current) => ({ ...current, presetId: "custom", customRules: { ...current.customRules, affinityControlRequired: clampWholeNumber(event.target.value, numericBounds.affinityControlRequiredMin, numericBounds.affinityControlRequiredMaximum) } }))} /><small>Own-color squares a player must hold to prime and earn a command point. The default is 2.</small></label>
                <label>Command Point Cap<input type="number" min={numericBounds.commandPointCapMin} max={numericBounds.commandPointCapMax} step="1" value={draft.customRules.commandPointCap} onChange={(event) => setDraft((current) => ({ ...current, presetId: "custom", customRules: { ...current.customRules, commandPointCap: clampWholeNumber(event.target.value, numericBounds.commandPointCapMin, numericBounds.commandPointCapMax) } }))} /><small>Maximum command points a player may save. The default is 3.</small></label>
              </div> : null}
            </div>
          </CollapsibleStudioSection>

          <CollapsibleStudioSection sectionId="studio-abilities" title="Special Abilities" description="Each player privately chooses the configured number of allowed abilities before play." className="ability-config-section" {...studioSectionProps("studio-abilities")}>
            <Toggle settingKey="ability-options" checked={draft.specialAbilities.enabled} onChange={toggleSpecialAbilities} label="Enable Special Abilities" description="All compatible abilities start enabled. Selections are revealed after both players lock in." />
            {draft.specialAbilities.enabled ? <>
              <div className="conditional-fields" id="customize-ability-count"><label>Abilities Per Player<input type="number" min={numericBounds.abilitySelectionMin} max={numericBounds.abilityCountMaximum} step="1" value={draft.specialAbilities.maxPerPlayer} onChange={(event) => setDraft((current) => ({ ...current, presetId: "custom", specialAbilities: { ...current.specialAbilities, maxPerPlayer: clampWholeNumber(event.target.value, numericBounds.abilitySelectionMin, numericBounds.abilityCountMaximum) } }))} /><small>Cannot exceed the number of enabled abilities. The default is 1.</small></label></div>
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
            <Toggle checked={draft.gambit.enabled} onChange={(enabled) => setDraft((current) => normalizeCustomizeNumbers({ ...current, presetId: enabled ? "gambit" : "custom", formationId: enabled ? "classic" : "custom", gambit: { ...current.gambit, enabled, draftEnabled: enabled ? current.gambit.draftEnabled : false } }, catalog.limits))} label="Enable Chass Gambit" description="Each player builds an army in their closest home rows without exceeding the point limit." />
            {draft.gambit.enabled ? <div className="gambit-settings-grid" data-setting-key="gambit-settings" id="customize-gambit-settings">
              <label>Maximum Points<input type="number" min={numericBounds.gambitBudgetMinimum} max={numericBounds.gambitBudgetMax} step="1" value={draft.gambit.budget} onChange={(event) => setDraft((current) => normalizeCustomizeNumbers({ ...current, presetId: "custom", gambit: { ...current.gambit, budget: event.target.value } }, catalog.limits))} /><small>Players may spend less. The limit must cover the required King.</small></label>
              <label>Maximum Pieces<input type="number" min={numericBounds.gambitMaxPiecesMin} max={numericBounds.gambitMaxPiecesMaximum} step="1" value={draft.gambit.maxPieces} onChange={(event) => setDraft((current) => normalizeCustomizeNumbers({ ...current, presetId: "custom", gambit: { ...current.gambit, maxPieces: event.target.value } }, catalog.limits))} /><small>Includes the required King. Current setup space supports up to {numericBounds.gambitMaxPiecesMaximum}.</small></label>
              <label>Private Setup Rows<input type="number" min={numericBounds.gambitSetupRowsMin} max={numericBounds.gambitSetupRowsMaximum} step="1" value={draft.gambit.setupRows} onChange={(event) => setDraft((current) => normalizeCustomizeNumbers({ ...current, presetId: "custom", gambit: { ...current.gambit, setupRows: event.target.value } }, catalog.limits))} /><small>Rows nearest each player that they may edit.</small></label>
              <label>Maximum Queens<input type="number" min={numericBounds.gambitMaxQueensMin} max={numericBounds.gambitMaxQueensMaximum} step="1" value={draft.gambit.maxQueens} onChange={(event) => setDraft((current) => normalizeCustomizeNumbers({ ...current, presetId: "custom", gambit: { ...current.gambit, maxQueens: event.target.value } }, catalog.limits))} /><small>Reserves one army slot for the King. The current maximum is {numericBounds.gambitMaxQueensMaximum}.</small></label>
              <Toggle checked={draft.gambit.draftEnabled} onChange={(draftEnabled) => setDraft((current) => normalizeCustomizeNumbers({ ...current, presetId: draftEnabled ? "draft_gambit" : "custom", gambit: { ...current.gambit, draftEnabled, draftPool: { ...current.gambit.draftPool, king: 2 } } }, catalog.limits))} label="Enable Shared Draft" description="Alternate public picks from one shared pool before each player privately arranges their drafted army." />
            </div> : null}
          </CollapsibleStudioSection>
        </div>
      </div>

      <section className={`studio-launch-bar validation-${validation.status}`}>
        <div className="launch-validation-copy">
          <span>{launchState.heading}</span>
          <strong>{launchState.detail}</strong>
          {launchState.errors.length ? (
            <div className="validation-inline-issues" aria-label="Configuration issues">
              {launchState.errors.map((issue, index) => (
                <button type="button" key={`${issue}-${index}`} onClick={() => focusValidationIssue(issue)}>
                  <b>{index + 1}</b>{issue}
                </button>
              ))}
            </div>
          ) : (
            botNotice
              ? <small className="bot-launch-notice" role="status">{botNotice}</small>
              : launchState.warning ? <small>{launchState.warning}</small> : null
          )}
        </div>
        <GameBriefing
          boardRows={draft.boardRows}
          boardCols={draft.boardCols}
          configuration={briefingConfiguration}
          catalog={catalog}
          className="studio-launch-summary"
        />
        <div className="launch-actions">
          <Button
            disabled={!canLaunch}
            loading={creatingMode === "local"}
            loadingLabel="Building Game..."
            onClick={() => create("local")}
          >
            Start Local Game
          </Button>
          <Button
            variant="secondary"
            disabled={!canLaunch}
            loading={creatingMode === "online"}
            loadingLabel="Creating Invite..."
            onClick={() => create("online")}
          >
            Create Online Game
          </Button>
          <Button
            variant={botEligible ? "primary" : "secondary"}
            className={`bot-launch-button ${botEligible ? "" : "is-unavailable"}`.trim()}
            disabled={botButtonDisabled}
            aria-disabled={!botEligible}
            loading={creatingMode === "bot"}
            loadingLabel="Starting Bot Match..."
            onClick={openBotSetup}
          >
            Play Against A Bot
          </Button>
        </div>
      </section>
      {error ? <p className="studio-error">{error}</p> : null}
      <Rulebook catalog={catalog} draft={draft} predictorProfile={predictorProfile} />
      <StartingSystemConfirmation
        mode={pendingStartingSystem}
        onCancel={() => setPendingStartingSystem(null)}
        onConfirm={() => {
          const mode = pendingStartingSystem;
          setPendingStartingSystem(null);
          if (mode) applyPopularMode(mode);
        }}
      />
      <BotSetupDialog
        open={showBotSetup}
        profiles={availableBotProfiles(catalog)}
        loading={creatingMode === "bot"}
        error={error}
        onClose={() => setShowBotSetup(false)}
        onStart={(selection) => create("bot", selection)}
      />
    </section>
  );
}

export default CustomizationPanel;
