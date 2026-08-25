import { locateConfigurationIssue } from "./configurationIssues.js";

export const CONFIGURATION_SECTION_IDS = [
  "studio-popular-modes",
  "studio-board-size",
  "studio-pieces",
  "studio-victory",
  "studio-custom-rules",
  "studio-abilities",
  "studio-gambit",
];

function orderedPlacements(placements = []) {
  return [...placements].sort((left, right) => (
    left.row - right.row
    || left.col - right.col
    || String(left.color).localeCompare(String(right.color))
    || String(left.type).localeCompare(String(right.type))
  ));
}

function stableValue(value) {
  if (Array.isArray(value)) return value.map(stableValue);
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(
    Object.keys(value).sort().map((key) => [key, stableValue(value[key])])
  );
}

function sectionSnapshot(draft, sectionId) {
  if (!draft) return null;
  switch (sectionId) {
    case "studio-popular-modes":
      return { matchPredictorEnabled: Boolean(draft.matchPredictorEnabled) };
    case "studio-board-size":
      return { boardRows: draft.boardRows, boardCols: draft.boardCols };
    case "studio-pieces":
      return {
        enabledPieces: [...(draft.enabledPieces || [])].sort(),
        pieceParameters: draft.pieceParameters,
        pointValues: draft.pointValues,
        pieceCaps: draft.pieceCaps,
        barricadeCount: draft.barricadeCount,
        placements: orderedPlacements(draft.placements),
      };
    case "studio-victory":
      return {
        victory: draft.victory,
        kingPoints: draft.pointValues?.king,
      };
    case "studio-custom-rules":
      return draft.customRules?.affinityEnabled
        ? draft.customRules
        : { affinityEnabled: false };
    case "studio-abilities":
      return draft.specialAbilities?.enabled
        ? draft.specialAbilities
        : { enabled: false };
    case "studio-gambit":
      return draft.gambit?.enabled
        ? draft.gambit
        : { enabled: false };
    default:
      return null;
  }
}

export function sectionIsModified(draft, baseline, sectionId) {
  if (!draft || !baseline) return false;
  return JSON.stringify(stableValue(sectionSnapshot(draft, sectionId)))
    !== JSON.stringify(stableValue(sectionSnapshot(baseline, sectionId)));
}

export function configurationSectionStatuses(draft, baseline, errors = []) {
  const statuses = Object.fromEntries(
    CONFIGURATION_SECTION_IDS.map((sectionId) => [
      sectionId,
      {
        modified: sectionIsModified(draft, baseline, sectionId),
        issueCount: 0,
      },
    ])
  );
  errors.forEach((message) => {
    const { sectionId } = locateConfigurationIssue(message);
    if (statuses[sectionId]) statuses[sectionId].issueCount += 1;
  });
  return statuses;
}

export function reconcileDraftIdentity(draft, baseline) {
  if (!draft || !baseline) return draft;
  const modified = Object.fromEntries(
    CONFIGURATION_SECTION_IDS.map((sectionId) => [
      sectionId,
      sectionIsModified(draft, baseline, sectionId),
    ])
  );
  const configurationMatches = Object.values(modified).every((value) => !value);
  const formationMatches = !modified["studio-board-size"] && !modified["studio-pieces"];
  return {
    ...draft,
    presetId: configurationMatches ? baseline.presetId : "custom",
    formationId: formationMatches ? baseline.formationId : "custom",
  };
}
