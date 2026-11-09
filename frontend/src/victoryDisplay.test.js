import assert from "node:assert/strict";
import test from "node:test";

import { formatMatchDuration, victoryDisplayMetadata } from "./victoryDisplay.js";

test("match durations use concise human-readable units", () => {
  assert.equal(formatMatchDuration(600), "10 minutes");
  assert.equal(formatMatchDuration(90), "1 minute 30 seconds");
  assert.equal(formatMatchDuration(3660), "1 hour 1 minute");
});

test("each victory mode exposes only its relevant settings", () => {
  const victory = {
    targetPoints: 21,
    timeSeconds: 600,
    kingPoints: 1,
    dominionRounds: 3,
    checkTarget: 3,
  };

  assert.deepEqual(victoryDisplayMetadata({ ...victory, mode: "timed" }), [
    { label: "Total Time", value: "10 minutes" },
  ]);
  assert.deepEqual(victoryDisplayMetadata({ ...victory, mode: "point_race" }), [
    { label: "Target Score", value: "21 points" },
    { label: "King Value", value: "1 point" },
  ]);
  assert.deepEqual(victoryDisplayMetadata({ ...victory, mode: "royal_score" }), [
    { label: "King Value", value: "1 point" },
  ]);
  assert.deepEqual(victoryDisplayMetadata({ ...victory, mode: "center_dominion" }), [
    { label: "Rounds To Hold", value: "3 rounds" },
  ]);
  assert.deepEqual(victoryDisplayMetadata({ ...victory, mode: "check_race" }), [
    { label: "Checks To Win", value: "3 checks" },
  ]);

  for (const mode of ["checkmate", "king_capture", "elimination", "royal_center"]) {
    assert.deepEqual(victoryDisplayMetadata({ ...victory, mode }), [], mode);
  }
});
