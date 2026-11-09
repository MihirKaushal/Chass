import assert from "node:assert/strict";
import test from "node:test";

import { matchesRulebookSearch } from "./rulebookSearch.js";
import { SCANNER_REFERENCE } from "./scannerReference.js";

test("scanner training data and credits are searchable", () => {
  for (const query of ["training photos", "green and white", "Public Wspace", "Chess Top Down", "CC BY 4.0"]) {
    assert.equal(matchesRulebookSearch(query, SCANNER_REFERENCE), true, query);
  }
});

test("rulebook search includes nested descriptions and configured values", () => {
  const catapult = {
    name: "Catapult",
    movement: "Launches a projectile without moving.",
    configuredParameters: [{ label: "Recharge", valueLabel: "4 rounds" }],
  };

  assert.equal(matchesRulebookSearch("projectile", catapult), true);
  assert.equal(matchesRulebookSearch("4 ROUNDS", catapult), true);
  assert.equal(matchesRulebookSearch("necromancy", catapult), false);
});

test("an empty rulebook query keeps every entry visible", () => {
  assert.equal(matchesRulebookSearch("", { name: "Elephant" }), true);
  assert.equal(matchesRulebookSearch("   ", null), true);
});
