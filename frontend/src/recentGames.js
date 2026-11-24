// A small index of games this browser has played, so Home can offer a way back.
// Seat tokens stay in the per-game session store; this list holds no credentials.
export const RECENT_GAMES_KEY = "chass:recent-games";
const MAX_RECENT_GAMES = 8;
// The server deletes games after 24 idle hours by default (GAME_IDLE_TTL_HOURS).
export const RESUMABLE_WINDOW_MS = 24 * 60 * 60 * 1000;

function readEntries(storage) {
  try {
    const parsed = JSON.parse(storage?.getItem(RECENT_GAMES_KEY) || "[]");
    return Array.isArray(parsed)
      ? parsed.filter((entry) => entry && typeof entry.gameId === "string")
      : [];
  } catch {
    return [];
  }
}

function writeEntries(storage, entries) {
  try {
    storage?.setItem(RECENT_GAMES_KEY, JSON.stringify(entries.slice(0, MAX_RECENT_GAMES)));
  } catch {
    // Storage can be full or disabled; resuming is a convenience only.
  }
}

export function recordRecentGame(storage, { gameId, mode, variant, color, finished }, now = Date.now()) {
  if (!gameId) return;
  const entry = {
    gameId,
    mode: mode || "local",
    variant: variant || "classic",
    color: color || null,
    finished: Boolean(finished),
    updatedAt: now,
  };
  writeEntries(storage, [entry, ...readEntries(storage).filter((item) => item.gameId !== gameId)]);
}

export function forgetRecentGame(storage, gameId) {
  const entries = readEntries(storage);
  const remaining = entries.filter((item) => item.gameId !== gameId);
  if (remaining.length !== entries.length) writeEntries(storage, remaining);
}

export function resumableGames(storage, now = Date.now(), limit = 3) {
  return readEntries(storage)
    .filter((entry) => !entry.finished && now - Number(entry.updatedAt || 0) < RESUMABLE_WINDOW_MS)
    .sort((left, right) => right.updatedAt - left.updatedAt)
    .slice(0, limit);
}

export function recentGameLabel(entry) {
  const variant = entry.variant === "gambit" ? "Chass Gambit" : null;
  const side = entry.color ? ` as ${entry.color === "black" ? "Black" : "White"}` : "";
  if (entry.mode === "online") return `${variant || "Online game"}${variant ? " online" : ""}${side}`;
  if (entry.mode === "bot") return `${variant || "Bot game"}${variant ? " against a bot" : ""}${side}`;
  return variant ? `${variant} on this device` : "Game on this device";
}

export function lastPlayedLabel(updatedAt, now = Date.now()) {
  const minutes = Math.max(0, Math.round((now - updatedAt) / 60000));
  if (minutes < 1) return "Played just now";
  if (minutes < 60) return `Played ${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  return `Played ${hours} hour${hours === 1 ? "" : "s"} ago`;
}

export function browserLocalStorage() {
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}
