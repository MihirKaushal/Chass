import assert from "node:assert/strict";
import test from "node:test";

import { locateConfigurationIssue } from "./configurationIssues.js";

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
  assert.deepEqual(locateConfigurationIssue("Barricades are neutral and cannot enter the army draft."), {
    sectionId: "studio-gambit",
    settingKey: "gambit-settings",
  });
  assert.deepEqual(locateConfigurationIssue("Marked center squares must begin empty when they affect the rules; only Barricades may start there."), {
    sectionId: "studio-pieces",
    settingKey: "board-editor",
  });
});
