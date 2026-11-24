import assert from "node:assert/strict";
import test from "node:test";

import { gameDocumentTitle, pageTitle } from "./documentTitle.js";

test("page titles share one site suffix", () => {
  assert.equal(pageTitle("Rulebook"), "Rulebook | Chass!");
  assert.equal(pageTitle(""), "Chass!");
});

test("remote games tell the player when it is their move", () => {
  const game = { mode: "online", phase: "play", currentPlayer: "black" };
  assert.equal(gameDocumentTitle(game, "black"), "Your move | Chass!");
  assert.equal(gameDocumentTitle(game, "white"), "Waiting for Black | Chass!");
  assert.equal(
    gameDocumentTitle({ mode: "bot", phase: "play", currentPlayer: "white" }, "black"),
    "Bot is thinking | Chass!"
  );
});

test("local games name the side to move and setup or finished states", () => {
  assert.equal(
    gameDocumentTitle({ mode: "local", phase: "play", currentPlayer: "white" }),
    "White to move | Chass!"
  );
  assert.equal(gameDocumentTitle({ mode: "online", phase: "lobby" }, "white"), "Waiting for opponent | Chass!");
  assert.equal(gameDocumentTitle({ mode: "local", phase: "deployment" }), "Game setup | Chass!");
  assert.equal(gameDocumentTitle({ mode: "local", phase: "finished", winner: "white" }), "Game over | Chass!");
});
