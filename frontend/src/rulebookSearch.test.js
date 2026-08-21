import assert from "node:assert/strict";
import test from "node:test";

import { matchesRulebookSearch } from "./rulebookSearch.js";

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
