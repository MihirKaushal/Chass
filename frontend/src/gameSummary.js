import { formatMatchDuration } from "./victoryDisplay.js";

function positiveInteger(value, fallback) {
  const parsed = Math.trunc(Number(value));
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function victorySummary(victory = {}) {
  switch (victory.mode) {
    case "king_capture":
      return "Capture the opposing King to win.";
    case "point_race":
      return `Reach ${positiveInteger(victory.targetPoints, 21)} captured points first.`;
    case "elimination":
      return "Capture every opposing combat piece to win.";
    case "timed":
      return `${formatMatchDuration(victory.timeSeconds)} per player; running out of time loses.`;
    case "royal_score":
      return "Defeat a King; the player with the higher captured score wins.";
    case "center_dominion":
      return `Begin with the center empty, then hold both squares for ${positiveInteger(victory.dominionRounds, 3)} consecutive rounds; checkmate also wins.`;
    case "royal_center":
      return "Begin with the center empty, then move your King onto an objective square; checkmate also wins.";
    case "check_race":
      return `Give check ${positiveInteger(victory.checkTarget, 3)} times first; checkmate also wins.`;
    default:
      return "Checkmate the opposing King to win.";
  }
}

function configuredTitle(configuration, catalog, rows, cols) {
  const gambit = configuration.gambit || {};
  if (gambit.enabled && gambit.draftEnabled) return `${rows}x${cols} Draft Gambit`;
  if (gambit.enabled) return `${rows}x${cols} Chass Gambit`;

  const preset = (catalog?.popularModes || []).find(
    (mode) => mode.id === configuration.presetId
  );
  if (preset) return `${rows}x${cols} ${preset.name}`;

  const formation = (catalog?.formations || []).find(
    (item) => item.id === configuration.formationId && item.id !== "custom"
  );
  if (formation) return `${rows}x${cols} ${formation.name}`;
  return `${rows}x${cols} Custom Match`;
}

export function buildGameBriefing({
  boardRows = 8,
  boardCols = 8,
  configuration = {},
  catalog,
}) {
  const tags = [];
  const enabledTypes = new Set(configuration.enabledPieces || []);
  const customPieceCount = (catalog?.pieces || []).filter(
    (piece) => piece.isCustom && enabledTypes.has(piece.type)
  ).length;
  const gambit = configuration.gambit || {};
  const customRules = configuration.customRules || {};
  const abilities = configuration.specialAbilities || {};

  if (gambit.enabled) {
    tags.push(
      gambit.draftEnabled
        ? "Shared draft and private deployment"
        : `Private armies with a ${Math.max(0, Number(gambit.budget) || 0)}-point cap`
    );
  }
  if (customRules.affinityEnabled) tags.push("Affinity squares start empty");
  if (abilities.enabled && abilities.allowed?.length) {
    const maximum = positiveInteger(abilities.maxPerPlayer, 1);
    tags.push(`${maximum} ${maximum === 1 ? "ability" : "abilities"} per player`);
  }
  if (customPieceCount) {
    tags.push(`${customPieceCount} custom piece type${customPieceCount === 1 ? "" : "s"}`);
  }

  return {
    title: configuredTitle(configuration, catalog, boardRows, boardCols),
    summary: victorySummary(configuration.victory),
    tags,
  };
}
