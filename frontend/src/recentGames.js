import { boardSquareLabel } from "./boardGeometry.js";

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
      ? parsed.filter((entry) => entry && typeof entry.gameId === "string" && Number.isFinite(new Date(entry.updatedAt).getTime()))
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

export function recordRecentGame(storage, { gameId, mode, variant, color, finished, game }, now = Date.now()) {
  if (!gameId) return;
  const entry = {
    gameId,
    mode: mode || "local",
    variant: variant || "classic",
    color: color || null,
    finished: Boolean(finished),
    updatedAt: now,
    ...recentGameDetails(game),
  };
  writeEntries(storage, [entry, ...readEntries(storage).filter((item) => item.gameId !== gameId)]);
}

export function recentGameDetails(game) {
  if (!game) return {};
  const rows = game.boardRows || 8;
  const cols = game.boardCols || 8;
  const side = game.currentPlayer === "black" ? "Black" : "White";
  const setup = { lobby: "Waiting for opponent", draft: "Drafting pieces", deployment: "Placing pieces", handoff: "Setup handoff", ability_selection: "Choosing abilities" };
  const status = setup[game.phase] || (game.phase === "finished" ? "Finished" : `${side} to move${game.gameStatus === "check" ? " (in check)" : ""}`);
  const bot = game.bot?.targetElo ? ` | Bot ~${game.bot.targetElo} Elo` : "";
  return {
    summary: `${rows} x ${cols} | ${status}${bot}`,
    // Store only the public, recent history, not the board or private setup state.
    recentMoves: game.phase === "play" ? (game.history || []).slice(-3).map((move) => {
      const piece = String(move.piece || "Piece");
      const name = piece.charAt(0).toUpperCase() + piece.slice(1).replaceAll("_", " ");
      const color = move.player === "black" ? "Black" : "White";
      if (move.actionType && move.actionType !== "move") {
        return `${move.moveNumber}. ${color}: ${move.explanation || move.actionType.replaceAll("_", " ")}`.slice(0, 180);
      }
      return `${move.moveNumber}. ${color} ${name} ${boardSquareLabel(move.from, rows)}-${boardSquareLabel(move.to, rows)}`;
    }) : [],
  };
}

export function lastPlayedTimestamp(updatedAt) {
  const date = new Date(updatedAt);
  if (!Number.isFinite(date.getTime())) return "";
  return date.toLocaleString(undefined, {
    month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
  });
}

export function forgetRecentGame(storage, gameId) {
  const entries = readEntries(storage);
  const remaining = entries.filter((item) => item.gameId !== gameId);
  if (remaining.length !== entries.length) writeEntries(storage, remaining);
}

export function resumableGames(storage, now = Date.now(), limit = MAX_RECENT_GAMES) {
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
