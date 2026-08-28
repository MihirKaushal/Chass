import assert from "node:assert/strict";
import test from "node:test";

import {
  FALLBACK_BOT_PROFILES,
  FALLBACK_CHASS_BOT_PROFILES,
  FALLBACK_FAIRY_BOT_PROFILES,
  availableBotProfiles,
  botTurnIsPending,
  buildClassicBotRequest,
  profilesForBotCompatibility,
  sessionForPublicGame,
} from "./botGame.js";

test("Classic bot requests carry only canonical launch settings", () => {
  assert.deepEqual(
    buildClassicBotRequest({ profileId: "stockfish-800", humanColor: "black" }),
    {
      mode: "bot",
      variant: "classic",
      boardRows: 8,
      boardCols: 8,
      rules: [],
      customPieces: [],
      bot: { profileId: "stockfish-800", humanColor: "black" },
    }
  );
});

test("bot profiles fall back safely while an older catalog cache expires", () => {
  assert.equal(availableBotProfiles({})[1].targetElo, 800);
  assert.equal(availableBotProfiles({}, "fairy-stockfish")[2].targetElo, 1000);
  assert.equal(availableBotProfiles({}, "chass")[1].targetElo, 800);
  const profiles = [{ id: "server-profile", engineId: "stockfish" }];
  assert.deepEqual(availableBotProfiles({ botProfiles: profiles }), profiles);
  assert.equal(FALLBACK_BOT_PROFILES.length, 7);
  assert.equal(FALLBACK_FAIRY_BOT_PROFILES.length, 3);
  assert.equal(FALLBACK_CHASS_BOT_PROFILES.length, 2);
});

test("validated compatibility supplies only profiles for the selected engine", () => {
  const profiles = [{ id: "fairy-profile", engineId: "fairy-stockfish" }];
  assert.equal(
    profilesForBotCompatibility({}, {
      engineId: "fairy-stockfish",
      profiles,
    }),
    profiles
  );
  assert.equal(
    profilesForBotCompatibility({}, { engineId: "fairy-stockfish" })[0].engineId,
    "fairy-stockfish"
  );
});

test("public local and bot games can restore their browser session", () => {
  assert.equal(sessionForPublicGame("online", { mode: "online" }), null);
  assert.deepEqual(sessionForPublicGame("bot-1", {
    mode: "bot",
    variant: "classic",
    bot: { humanColor: "black" },
  }), {
    gameId: "bot-1",
    mode: "bot",
    variant: "classic",
    role: "human",
    token: null,
    color: "black",
  });
});

test("bot pending state follows the authoritative side to move", () => {
  const game = {
    mode: "bot",
    phase: "play",
    currentPlayer: "black",
    bot: { botColor: "black" },
  };
  assert.equal(botTurnIsPending(game), true);
  assert.equal(botTurnIsPending({ ...game, currentPlayer: "white" }), false);
  assert.equal(botTurnIsPending({ ...game, winner: "white" }), false);
  assert.equal(botTurnIsPending({
    mode: "bot",
    phase: "ability_selection",
    bot: { status: "thinking" },
  }), true);
  assert.equal(botTurnIsPending({
    mode: "bot",
    phase: "deployment",
    bot: { status: "idle" },
  }), false);
});
