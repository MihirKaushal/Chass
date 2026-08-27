import assert from "node:assert/strict";
import test from "node:test";

import { affinitySquares, significantCenterSquares } from "./boardGeometry.js";

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

test("affinity layouts expand from center and stay color-balanced", () => {
  const oddExpanded = affinitySquares(7, 7, 8);
  assert.equal(oddExpanded.white.length, 4);
  assert.equal(oddExpanded.black.length, 4);
  assert.equal(
    new Set([...oddExpanded.white, ...oddExpanded.black].map(({ row, col }) => `${row}-${col}`)).size,
    8
  );
  assert.deepEqual(
    new Set([...oddExpanded.white, ...oddExpanded.black].map(({ row }) => row)),
    new Set([2, 3, 4])
  );

  const maximum = affinitySquares(16, 16, 32);
  assert.equal(maximum.white.length, 16);
  assert.equal(maximum.black.length, 16);
  assert.deepEqual(
    new Set([...maximum.white, ...maximum.black].map(({ row }) => row)),
    new Set([7, 8])
  );
});

test("configured affinity counts reserve the matching number of center squares", () => {
  assert.equal(
    significantCenterSquares(8, 8, {
      affinityEnabled: true,
      affinitySquareCount: 10,
    }).length,
    10
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
