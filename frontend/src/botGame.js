export const FALLBACK_BOT_PROFILES = [
  [500, "Beginner", "Learning the basics"],
  [800, "Learner", "Sees simple tactics"],
  [1000, "Developing", "Plays sensible chess"],
  [1200, "Intermediate", "Usually finds solid moves"],
  [1500, "Advanced", "Strong club-level challenge"],
  [2000, "Expert", "Punishes most mistakes"],
  [2500, "Master", "Elite engine challenge"],
].map(([targetElo, label, description]) => ({
  id: `stockfish-${targetElo}`,
  targetElo,
  label,
  description,
  engineId: "stockfish",
  engineName: "Stockfish 18",
  estimated: true,
}));

export const FALLBACK_FAIRY_BOT_PROFILES = [
  [500, "Beginner", "Explores unfamiliar variants"],
  [800, "Variant Learner", "Handles basic variant tactics"],
  [1000, "Variant Challenger", "A steadier static-variant opponent"],
].map(([targetElo, label, description]) => ({
  id: `fairy-stockfish-${targetElo}`,
  targetElo,
  label,
  description,
  engineId: "fairy-stockfish",
  engineName: "Fairy-Stockfish",
  estimated: true,
}));

export const FALLBACK_CHASS_BOT_PROFILES = [
  [500, "Variant Explorer", "Learns unusual pieces and powers"],
  [800, "Variant Tactician", "Uses deeper custom-rule search"],
].map(([targetElo, label, description]) => ({
  id: `chass-${targetElo}`,
  targetElo,
  label,
  description,
  engineId: "chass",
  engineName: "Chass Engine",
  estimated: true,
}));

const FALLBACK_PROFILES_BY_ENGINE = {
  stockfish: FALLBACK_BOT_PROFILES,
  "fairy-stockfish": FALLBACK_FAIRY_BOT_PROFILES,
  chass: FALLBACK_CHASS_BOT_PROFILES,
};

export function availableBotProfiles(catalog, engineId = "stockfish") {
  const catalogProfiles = catalog?.botProfiles || [];
  const matchingProfiles = catalogProfiles.filter(
    (profile) => profile.engineId === engineId
  );
  if (matchingProfiles.length) return matchingProfiles;
  return FALLBACK_PROFILES_BY_ENGINE[engineId] || FALLBACK_BOT_PROFILES;
}

export function profilesForBotCompatibility(catalog, compatibility) {
  if (compatibility?.profiles?.length) return compatibility.profiles;
  return availableBotProfiles(catalog, compatibility?.engineId || "stockfish");
}

export function buildClassicBotRequest({ profileId, humanColor = "white" }) {
  return {
    mode: "bot",
    variant: "classic",
    boardRows: 8,
    boardCols: 8,
    rules: [],
    customPieces: [],
    bot: { profileId, humanColor },
  };
}

export function sessionForPublicGame(gameId, game) {
  if (game?.mode === "local") {
    return {
      gameId,
      mode: "local",
      variant: game.variant || "classic",
      role: "local",
      token: null,
      color: null,
    };
  }
  if (game?.mode === "bot" && game.bot?.humanColor) {
    return {
      gameId,
      mode: "bot",
      variant: game.variant || "classic",
      role: "human",
      token: null,
      color: game.bot.humanColor,
    };
  }
  return null;
}

export function botTurnIsPending(game) {
  if (game?.mode !== "bot" || game.winner) return false;
  if (game.bot?.status) return game.bot.status === "thinking";
  return Boolean(
    game.bot?.botColor === game.currentPlayer
    && game.phase === "play"
  );
}
