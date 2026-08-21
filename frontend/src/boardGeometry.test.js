import assert from "node:assert/strict";
import test from "node:test";

import { significantCenterSquares } from "./boardGeometry.js";

test("center-significance squares adapt to even and odd boards", () => {
  assert.deepEqual(
    significantCenterSquares(8, 8, { victoryMode: "center_dominion" }),
    [
      { row: 3, col: 3 },
      { row: 3, col: 4 },
      { row: 4, col: 3 },
      { row: 4, col: 4 },
    ]
  );
  assert.deepEqual(
    significantCenterSquares(7, 7, { affinityEnabled: true }),
    [
      { row: 3, col: 1 },
      { row: 3, col: 2 },
      { row: 3, col: 4 },
      { row: 3, col: 5 },
    ]
  );
});

test("only center-focused configurations reserve starting squares", () => {
  assert.deepEqual(significantCenterSquares(8, 8), []);
  assert.equal(
    significantCenterSquares(8, 8, {
      victoryMode: "royal_center",
      affinityEnabled: true,
    }).length,
    4
  );
});
