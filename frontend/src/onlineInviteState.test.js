import assert from "node:assert/strict";
import test from "node:test";

import { onlineInviteState } from "./onlineInviteState.js";


test("the host keeps the initial Black invitation before the room is ready", () => {
  assert.deepEqual(
    onlineInviteState({
      mode: "online",
      gameReady: false,
      playerColor: "white",
      playerRole: "host",
      presence: { white: true, black: false },
      connectionStatus: "connected",
    }),
    { targetColor: "black", reconnect: false }
  );
});

test("either connected player can invite the disconnected opponent", () => {
  assert.deepEqual(
    onlineInviteState({
      mode: "online",
      gameReady: true,
      playerColor: "white",
      playerRole: "host",
      presence: { white: true, black: false },
      connectionStatus: "connected",
    }),
    { targetColor: "black", reconnect: true }
  );
  assert.deepEqual(
    onlineInviteState({
      mode: "online",
      gameReady: true,
      playerColor: "black",
      playerRole: "player",
      presence: { white: false, black: true },
      connectionStatus: "connected",
    }),
    { targetColor: "white", reconnect: true }
  );
});

test("reconnect invitations stay hidden during local socket outages", () => {
  const input = {
    mode: "online",
    gameReady: true,
    playerColor: "white",
    playerRole: "host",
    presence: { white: true, black: false },
  };
  assert.equal(onlineInviteState({ ...input, connectionStatus: "reconnecting" }), null);
  assert.equal(
    onlineInviteState({
      ...input,
      connectionStatus: "connected",
      presence: { white: false, black: false },
    }),
    null
  );
});

test("the invitation closes as soon as the opponent reconnects", () => {
  assert.equal(
    onlineInviteState({
      mode: "online",
      gameReady: true,
      playerColor: "black",
      playerRole: "player",
      presence: { white: true, black: true },
      connectionStatus: "connected",
    }),
    null
  );
});
