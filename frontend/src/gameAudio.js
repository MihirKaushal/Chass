export const SOUND_PREFERENCE_STORAGE_KEY = "chass:sound-preferences";
export const DEFAULT_SOUND_VOLUME = 0.7;

export const SOUND_ASSETS = {
  move: "/sounds/chass_piece_move.mp3",
  win: "/sounds/chass_win.mp3",
  lose: "/sounds/chass_lose.mp3",
};

const MOVEMENT_ACTION_TYPES = new Set([
  "move",
  "move_barricade",
  "episcopal",
  "getaway",
]);

export function clampSoundVolume(value) {
  const numericValue = Number(value);
  if (!Number.isFinite(numericValue)) return DEFAULT_SOUND_VOLUME;
  return Math.max(0, Math.min(1, numericValue));
}

export function normalizeSoundPreferences(preferences = {}) {
  const volume = clampSoundVolume(preferences.volume ?? DEFAULT_SOUND_VOLUME);
  return {
    volume,
    muted: volume === 0 || Boolean(preferences.muted),
  };
}

export function readSoundPreferences(storage) {
  try {
    const serialized = storage?.getItem(SOUND_PREFERENCE_STORAGE_KEY);
    return normalizeSoundPreferences(serialized ? JSON.parse(serialized) : {});
  } catch {
    return normalizeSoundPreferences();
  }
}

export function writeSoundPreferences(storage, preferences) {
  const normalized = normalizeSoundPreferences(preferences);
  try {
    storage?.setItem(SOUND_PREFERENCE_STORAGE_KEY, JSON.stringify(normalized));
  } catch {
    // Sound controls still work for this page when browser storage is unavailable.
  }
  return normalized;
}

export function isMovementActionType(actionType) {
  return MOVEMENT_ACTION_TYPES.has(actionType || "move");
}

export function gameSoundSnapshot(game, playerColor = null) {
  if (!game?.id) return null;
  const history = Array.isArray(game.history) ? game.history : [];
  const lastRecord = history[history.length - 1] || null;

  return {
    gameId: game.id,
    mode: game.mode,
    playerColor,
    winner: game.winner || null,
    moveCount: Number(game.historyPagination?.totalMoves ?? history.length) || 0,
    lastActionType: lastRecord?.actionType || (history.length ? "move" : null),
  };
}

export function outcomeSoundForSnapshot(snapshot) {
  if (!snapshot?.winner) return null;
  if (snapshot.mode === "local") return "win";
  if (!["white", "black"].includes(snapshot.playerColor)) return null;
  return snapshot.winner === snapshot.playerColor ? "win" : "lose";
}

export function soundForGameTransition(previous, current) {
  if (!previous || !current || previous.gameId !== current.gameId) return null;

  if (current.winner && current.winner !== previous.winner) {
    const outcomeSound = outcomeSoundForSnapshot(current);
    if (outcomeSound) return outcomeSound;
  }

  if (
    current.moveCount > previous.moveCount
    && isMovementActionType(current.lastActionType)
  ) {
    return "move";
  }

  return null;
}
