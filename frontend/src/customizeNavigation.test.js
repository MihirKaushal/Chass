import assert from "node:assert/strict";
import test from "node:test";

import {
  CUSTOMIZE_SECTION_LINKS,
  matchingCustomizeResults,
  nextCustomizeResultIndex,
} from "./customizeNavigation.js";

const catalog = {
  popularModes: [
    { id: "classic", name: "Classic Chass", summary: "Standard chess setup." },
  ],
  formations: [
    { id: "castle_siege", name: "Castle Siege", summary: "Extra Rooks and Pawns." },
  ],
  pieces: [
    {
      type: "catapult",
      name: "Catapult",
      isCustom: true,
      description: "Launches projectiles.",
      movement: "Moves forward.",
      rules: [],
      tunableParameters: [],
    },
  ],
  victoryModes: [
    { id: "timed", name: "Timed Match", summary: "The clock decides the result." },
  ],
  specialAbilities: [
    {
      id: "necromancy",
      name: "Necromancy",
      summary: "Buy captured enemy pieces.",
      rules: [],
      tunableParameters: [],
    },
  ],
};

test("an empty customize search preserves all eight sections in page order", () => {
  const results = matchingCustomizeResults("", catalog);
  assert.equal(results.length, 8);
  assert.deepEqual(
    results.map(({ id }) => id),
    CUSTOMIZE_SECTION_LINKS.map(({ id }) => id)
  );
});

test("customize search returns direct setting and catalog destinations", () => {
  const timed = matchingCustomizeResults("timer", catalog)[0];
  assert.equal(timed.label, "Timed Match");
  assert.equal(timed.category, "Win Condition");
  assert.equal(timed.targetId, "customize-victory-timed");

  const formation = matchingCustomizeResults("castle siege", catalog)[0];
  assert.equal(formation.label, "Castle Siege");
  assert.equal(formation.category, "Starting Layout Presets");
  assert.equal(formation.targetId, "customize-formation-castle_siege");

  const catapult = matchingCustomizeResults("catapult", catalog)[0];
  assert.equal(catapult.label, "Catapult");
  assert.equal(catapult.category, "Pieces");
  assert.equal(catapult.targetId, "customize-piece-catapult");
  assert.equal(catapult.pieceFilter, "custom");

  const necromancy = matchingCustomizeResults("necromancy", catalog)[0];
  assert.equal(necromancy.label, "Necromancy");
  assert.equal(necromancy.category, "Special Abilities");
  assert.equal(necromancy.targetId, "customize-ability-necromancy");

  const dimensions = matchingCustomizeResults("board dimensions", catalog)[0];
  assert.equal(dimensions.label, "Board Dimensions");
  assert.equal(dimensions.category, "Board Size");
  assert.equal(dimensions.targetId, "customize-board-dimensions");

  const analysis = matchingCustomizeResults("match analysis", catalog)[0];
  assert.equal(analysis.label, "Match Analysis");
  assert.equal(analysis.category, "Rulebook");
  assert.equal(analysis.targetId, "rulebook-match-analysis");
});

test("broad reference searches still navigate to the Rulebook section", () => {
  assert.deepEqual(
    matchingCustomizeResults("reference", catalog).map(({ label }) => label),
    ["Rulebook"]
  );
});

test("keyboard result selection starts predictably and wraps in both directions", () => {
  assert.equal(nextCustomizeResultIndex(-1, 4, 1), 0);
  assert.equal(nextCustomizeResultIndex(-1, 4, -1), 3);
  assert.equal(nextCustomizeResultIndex(3, 4, 1), 0);
  assert.equal(nextCustomizeResultIndex(0, 4, -1), 3);
  assert.equal(nextCustomizeResultIndex(0, 0, 1), -1);
});
