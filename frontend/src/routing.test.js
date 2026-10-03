import assert from "node:assert/strict";
import test from "node:test";

import { routeFromPath } from "./routing.js";

test("the Rulebook has a dedicated route", () => {
  assert.deepEqual(routeFromPath("/rulebook"), { name: "rulebook" });
  assert.deepEqual(routeFromPath("/rulebook/"), { name: "rulebook" });
});

test("customize presets are parsed from the supplied search string", () => {
  assert.deepEqual(routeFromPath("/customize", "?preset=gambit"), {
    name: "customize",
    preset: "gambit",
  });
});
