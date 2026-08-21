import assert from "node:assert/strict";
import test from "node:test";

import { buildGameBriefing } from "./gameSummary.js";

const catalog = {
  popularModes: [{ id: "classic", name: "Classic Chass" }],
  formations: [{ id: "horde", name: "Horde" }],
  pieces: [
    { type: "king", isCustom: false },
    { type: "catapult", isCustom: true },
    { type: "elephant", isCustom: true },
  ],
};

test("briefing keeps the selected victory and modifiers concise", () => {
  assert.deepEqual(
    buildGameBriefing({
      boardRows: 10,
      boardCols: 8,
      catalog,
      configuration: {
        presetId: "custom",
        enabledPieces: ["king", "catapult", "elephant"],
        victory: { mode: "check_race", checkTarget: 4 },
        customRules: { affinityEnabled: true },
        specialAbilities: {
          enabled: true,
          allowed: ["scorch", "getaway"],
          maxPerPlayer: 2,
        },
        gambit: { enabled: false },
      },
    }),
    {
      title: "10x8 Custom Match",
      summary: "Give check 4 times first; checkmate also wins.",
      tags: [
        "Affinity squares start empty",
        "2 abilities per player",
        "2 custom piece types",
      ],
    }
  );
});

test("briefing recognizes presets and Gambit setup", () => {
  const classic = buildGameBriefing({
    catalog,
    configuration: {
      presetId: "classic",
      victory: { mode: "checkmate" },
      gambit: { enabled: false },
    },
  });
  assert.equal(classic.title, "8x8 Classic Chass");
  assert.equal(classic.summary, "Checkmate the opposing King to win.");

  const gambit = buildGameBriefing({
    catalog,
    configuration: {
      enabledPieces: ["king"],
      victory: { mode: "timed", timeSeconds: 600 },
      gambit: { enabled: true, draftEnabled: true, budget: 39 },
    },
  });
  assert.equal(gambit.title, "8x8 Draft Gambit");
  assert.equal(gambit.summary, "10 minutes per player; running out of time loses.");
  assert.deepEqual(gambit.tags, ["Shared draft and private deployment"]);
});

test("center-focused briefings explain the empty starting objective", () => {
  const dominion = buildGameBriefing({
    configuration: {
      victory: { mode: "center_dominion", dominionRounds: 2 },
      gambit: { enabled: false },
    },
  });
  const royalCenter = buildGameBriefing({
    configuration: {
      victory: { mode: "royal_center" },
      gambit: { enabled: false },
    },
  });

  assert.match(dominion.summary, /Begin with the center empty/);
  assert.match(royalCenter.summary, /Begin with the center empty/);
});
