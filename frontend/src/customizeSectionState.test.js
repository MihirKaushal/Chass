import assert from "node:assert/strict";
import test from "node:test";

import {
  configurationSectionStatuses,
  hasConfigurationModifications,
  reconcileDraftIdentity,
  sectionIsModified,
} from "./customizeSectionState.js";

function classicDraft() {
  return {
    presetId: "classic",
    formationId: "classic",
    matchPredictorEnabled: true,
    boardRows: 8,
    boardCols: 8,
    enabledPieces: ["pawn", "king"],
    pieceParameters: {},
    pointValues: { pawn: 1, king: 0 },
    pieceCaps: { pawn: 8, king: 1 },
    barricadeCount: 1,
    placements: [
      { row: 7, col: 4, type: "king", color: "white" },
      { row: 0, col: 4, type: "king", color: "black" },
    ],
    victory: { mode: "checkmate", kingPoints: 0 },
    customRules: { affinityEnabled: false, commandPointCap: 3 },
    specialAbilities: { enabled: false, allowed: [], maxPerPlayer: 1 },
    gambit: { enabled: false, budget: 39 },
  };
}

test("section modification is scoped to the setting group that changed", () => {
  const baseline = classicDraft();
  const changed = {
    ...baseline,
    pointValues: { ...baseline.pointValues, pawn: 4 },
  };
  assert.equal(sectionIsModified(changed, baseline, "studio-pieces"), true);
  assert.equal(sectionIsModified(changed, baseline, "studio-board-size"), false);
  assert.equal(sectionIsModified(changed, baseline, "studio-victory"), false);
});

test("disabled rules and abilities ignore inactive latent values", () => {
  const baseline = classicDraft();
  const changed = {
    ...baseline,
    customRules: { affinityEnabled: false, commandPointCap: 12 },
    specialAbilities: { enabled: false, allowed: ["necromancy"], maxPerPlayer: 3 },
  };
  assert.equal(sectionIsModified(changed, baseline, "studio-custom-rules"), false);
  assert.equal(sectionIsModified(changed, baseline, "studio-abilities"), false);
});

test("validation errors are counted against their owning sections", () => {
  const baseline = classicDraft();
  const statuses = configurationSectionStatuses(baseline, baseline, [
    "Pawns cannot begin on a promotion rank.",
    "White must begin with exactly one King.",
    "Getaway requires an enabled Queen.",
  ]);
  assert.equal(statuses["studio-pieces"].issueCount, 2);
  assert.equal(statuses["studio-abilities"].issueCount, 1);
});

test("restoring every section restores preset identity", () => {
  const baseline = classicDraft();
  const changed = {
    ...baseline,
    presetId: "custom",
    formationId: "custom",
  };
  assert.deepEqual(
    reconcileDraftIdentity(changed, baseline),
    baseline
  );
});

test("configuration replacement warnings only trigger for modified sections", () => {
  assert.equal(hasConfigurationModifications({
    pieces: { modified: false, issueCount: 2 },
    victory: { modified: false, issueCount: 0 },
  }), false);
  assert.equal(hasConfigurationModifications({
    pieces: { modified: true, issueCount: 0 },
    victory: { modified: false, issueCount: 0 },
  }), true);
});
