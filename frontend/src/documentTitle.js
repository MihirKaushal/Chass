export const SITE_TITLE = "Chass!";

const SETUP_PHASES = new Set(["ability_selection", "handoff", "draft", "deployment"]);

function colorName(color) {
  return color === "black" ? "Black" : "White";
}

export function pageTitle(label) {
  return label ? `${label} | ${SITE_TITLE}` : SITE_TITLE;
}

// Tab titles let a player in another tab see when the game needs them.
export function gameDocumentTitle(game, playerColor = null) {
  if (!game) return pageTitle("Game");
  if (game.phase === "finished" || game.winner) return pageTitle("Game over");
  if (game.phase === "lobby") return pageTitle("Waiting for opponent");
  if (SETUP_PHASES.has(game.phase)) return pageTitle("Game setup");

  const remote = game.mode === "online" || game.mode === "bot";
  if (remote && playerColor) {
    if (game.currentPlayer === playerColor) return pageTitle("Your move");
    return pageTitle(game.mode === "bot" ? "Bot is thinking" : `Waiting for ${colorName(game.currentPlayer)}`);
  }
  return pageTitle(`${colorName(game.currentPlayer)} to move`);
}
