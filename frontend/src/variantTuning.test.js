import assert from "node:assert/strict";
import test from "node:test";

import {
  applyParameterChange,
  effectiveCatalogEntry,
  parameterDefaults,
  parameterMaximum,
  scorchUsageDefault,
} from "./variantTuning.js";

const scorch = {
  id: "scorch",
  summary: "Scorch squares.",
  summaryTemplate: "Scorch {usesPerGame} square(s) with {cooldownTurns} turn(s) between uses.",
  details: [],
  tunableParameters: [
    { id: "usesPerGame", default: 2, dynamicDefault: "board_sqrt_quarter", unit: "use" },
    { id: "cooldownTurns", default: 10, unit: "turn" },
  ],
};

test("Scorch derives its default usage limit from board area", () => {
  assert.equal(scorchUsageDefault(8, 8), 2);
  assert.equal(scorchUsageDefault(10, 10), 3);
  assert.equal(scorchUsageDefault(16, 16), 4);
  assert.deepEqual(parameterDefaults([scorch], { rows: 10, cols: 10 }).scorch, {
    usesPerGame: 3,
    cooldownTurns: 10,
  });
});

test("Scorch renders configured values in descriptions", () => {
  const configured = effectiveCatalogEntry(scorch, {
    usesPerGame: 5,
    cooldownTurns: 3,
  });

  assert.equal(configured.summary, "Scorch 5 squares with 3 turns between uses.");
});

const elephantParameters = [
  { id: "chargeDistance", min: 1, max: 16, default: 2 },
  {
    id: "alliedChargeLimit",
    min: 0,
    max: 16,
    default: 1,
    maxParameter: "chargeDistance",
  },
];

test("Elephant allied charge limit follows the configured charge distance", () => {
  const alliedLimit = elephantParameters[1];

  assert.equal(parameterMaximum(alliedLimit, { chargeDistance: 2 }), 2);
  assert.equal(parameterMaximum(alliedLimit, { chargeDistance: 5 }), 5);
});

test("Lowering Elephant charge distance clamps its allied charge limit", () => {
  assert.deepEqual(
    applyParameterChange(
      elephantParameters,
      { chargeDistance: 4, alliedChargeLimit: 3 },
      "chargeDistance",
      2
    ),
    { chargeDistance: 2, alliedChargeLimit: 2 }
  );

  assert.deepEqual(
    applyParameterChange(
      elephantParameters,
      { chargeDistance: 2, alliedChargeLimit: 1 },
      "chargeDistance",
      4
    ),
    { chargeDistance: 4, alliedChargeLimit: 1 }
  );
});
