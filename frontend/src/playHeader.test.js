import assert from "node:assert/strict";
import test from "node:test";

import { onlinePlayerStatus, onlinePlayerSummary, roomLabel } from "./playHeader.js";

test("play header uses stable local and online room labels", () => {
  assert.equal(roomLabel("local"), "Local Room");
  assert.equal(roomLabel("online"), "Online Room");
});

test("online play header identifies the player and connected opponent", () => {
  assert.equal(
    onlinePlayerSummary("white", { white: true, black: true }, true),
    "You are playing as White. Black is connected."
  );
  assert.equal(
    onlinePlayerSummary("black", { white: true, black: true }, true),
    "You are playing as Black. White is connected."
  );
});

test("online play header distinguishes open and disconnected seats", () => {
  assert.equal(
    onlinePlayerSummary("white", { white: true, black: false }, false),
    "You are playing as White. Black has not joined."
  );
  assert.equal(
    onlinePlayerSummary("white", { white: true, black: false }, true),
    "You are playing as White. Black is disconnected."
  );
});

test("online play header exposes structured colors and connection state for styled status", () => {
  assert.deepEqual(
    onlinePlayerStatus("black", { white: true, black: true }, true),
    {
      role: "player",
      playerColor: "black",
      opponentColor: "white",
      connection: "connected",
    }
  );
  assert.deepEqual(onlinePlayerStatus(null, {}, false), { role: "spectator" });
});
