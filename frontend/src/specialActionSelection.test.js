import assert from "node:assert/strict";
import test from "node:test";

import {
  actionsForGlobalSelection,
  globalActionSelectionKey,
  necromancyPurchaseOptions,
} from "./specialActionSelection.js";

const capturedPieces = [
  {
    pieceId: "rook-1",
    type: "rook",
    name: "Rook",
    color: "black",
    points: 5,
    symbol: "♜",
  },
  {
    pieceId: "pawn-1",
    type: "pawn",
    name: "Pawn",
    color: "black",
    points: 1,
    symbol: "♟",
  },
];

const necromancyActions = [
  {
    id: "necromancy:rook-1:7:0",
    actionType: "necromancy",
    owner: "white",
    target: { row: 7, col: 0 },
    params: { capturedPieceId: "rook-1" },
  },
  {
    id: "necromancy:rook-1:7:1",
    actionType: "necromancy",
    owner: "white",
    target: { row: 7, col: 1 },
    params: { capturedPieceId: "rook-1" },
  },
  {
    id: "necromancy:pawn-1:7:0",
    actionType: "necromancy",
    owner: "white",
    target: { row: 7, col: 0 },
    params: { capturedPieceId: "pawn-1" },
  },
];

test("Necromancy selection identifies a specific captured piece", () => {
  assert.equal(globalActionSelectionKey(necromancyActions[0]), "necromancy:rook-1");
  assert.equal(
    globalActionSelectionKey({ actionType: "scorch", target: { row: 3, col: 3 } }),
    "scorch"
  );
  assert.equal(
    globalActionSelectionKey({ actionType: "episcopal", source: { row: 2, col: 2 } }),
    null
  );
});

test("Necromancy inventory lists pieces instead of every placement square", () => {
  const purchases = necromancyPurchaseOptions(necromancyActions, capturedPieces);

  assert.equal(purchases.length, 2);
  assert.deepEqual(
    purchases.map(({ capturedPieceId, cost, targetCount }) => ({
      capturedPieceId,
      cost,
      targetCount,
    })),
    [
      { capturedPieceId: "rook-1", cost: 5, targetCount: 2 },
      { capturedPieceId: "pawn-1", cost: 1, targetCount: 1 },
    ]
  );
});

test("Selecting a purchase exposes only that piece's legal board squares", () => {
  const selected = actionsForGlobalSelection(
    necromancyActions,
    "necromancy:rook-1"
  );

  assert.deepEqual(
    selected.map((action) => action.target),
    [{ row: 7, col: 0 }, { row: 7, col: 1 }]
  );
  assert.ok(selected.every((action) => action.params.capturedPieceId === "rook-1"));
});
