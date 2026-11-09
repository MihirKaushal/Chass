import assert from "node:assert/strict";
import test from "node:test";

import {
  configurationIssueSquares,
  locateConfigurationIssue,
} from "./configurationIssues.js";

test("configuration issues route to the setting that can fix them", () => {
  assert.deepEqual(locateConfigurationIssue("Insufficient material."), {
    sectionId: "studio-pieces",
    settingKey: "board-editor",
  });
  assert.deepEqual(
    locateConfigurationIssue("The point target cannot exceed 9; both players need enough opposing material to reach it."),
    { sectionId: "studio-victory", settingKey: "target-points" }
  );
  assert.deepEqual(locateConfigurationIssue("Getaway requires an enabled Queen."), {
    sectionId: "studio-abilities",
    settingKey: "ability-options",
  });
  assert.deepEqual(locateConfigurationIssue("The Queen limit must leave one army slot for the King."), {
    sectionId: "studio-gambit",
    settingKey: "gambit-settings",
  });
  assert.deepEqual(locateConfigurationIssue("Kings must begin outside the Royal Center objective squares."), {
    sectionId: "studio-pieces",
    settingKey: "board-editor",
  });
  assert.deepEqual(locateConfigurationIssue("Every starting piece must be inside the board."), {
    sectionId: "studio-pieces",
    settingKey: "board-editor",
  });
  assert.deepEqual(
    locateConfigurationIssue("White King cannot begin in check or checkmate."),
    { sectionId: "studio-pieces", settingKey: "board-editor" }
  );
  assert.deepEqual(locateConfigurationIssue("Barricades are neutral and cannot enter the army draft."), {
    sectionId: "studio-gambit",
    settingKey: "gambit-settings",
  });
  assert.deepEqual(locateConfigurationIssue("Marked center squares must begin empty when they affect the rules; only Barricades may start there."), {
    sectionId: "studio-pieces",
    settingKey: "board-editor",
  });
});

test("configuration issues identify promotion-rank and touching-King squares", () => {
  const draft = {
    boardRows: 8,
    boardCols: 8,
    placements: [
      { row: 0, col: 0, type: "pawn", color: "white" },
      { row: 7, col: 7, type: "pawn", color: "black" },
      { row: 7, col: 0, type: "pawn", color: "white" },
      { row: 4, col: 4, type: "king", color: "white" },
      { row: 5, col: 5, type: "king", color: "black" },
    ],
  };

  assert.deepEqual(
    configurationIssueSquares("Pawns cannot begin on a promotion rank.", draft),
    [{ row: 0, col: 0 }, { row: 7, col: 7 }]
  );
  assert.deepEqual(
    configurationIssueSquares("The two Kings cannot begin on touching squares.", draft),
    [{ row: 4, col: 4 }, { row: 5, col: 5 }]
  );
  assert.deepEqual(
    configurationIssueSquares("White King cannot begin in check or checkmate.", draft),
    [{ row: 4, col: 4 }]
  );
});

test("configuration issues identify occupied center and reserved Barricade squares", () => {
  const draft = {
    boardRows: 8,
    boardCols: 8,
    barricadeCount: 2,
    victory: { mode: "center_dominion" },
    customRules: { affinityEnabled: false },
    placements: [
      { row: 3, col: 3, type: "bishop", color: "white" },
      { row: 4, col: 4, type: "pawn", color: "black" },
      { row: 0, col: 0, type: "rook", color: "white" },
    ],
  };

  assert.deepEqual(
    configurationIssueSquares(
      "Marked center squares must begin empty when they affect the rules; only Barricades may start there.",
      draft
    ),
    [{ row: 3, col: 3 }, { row: 4, col: 4 }]
  );
  assert.deepEqual(
    configurationIssueSquares(
      "Starting Barricade positions must remain empty in the board center.",
      draft
    ),
    [{ row: 3, col: 3 }, { row: 4, col: 4 }]
  );
});
