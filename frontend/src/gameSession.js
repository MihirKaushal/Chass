const SESSION_PREFIX = "chass:game:";
const memorySessions = new Map();


function storageKey(gameId) {
  return `${SESSION_PREFIX}${gameId}`;
}

export function saveGameSession(gameId, session) {
  const normalized = {
    gameId,
    mode: session.mode,
    variant: session.variant || "classic",
    token: session.token || null,
    color: session.color || null,
    role: session.role,
    inviteToken: session.inviteToken || null,
    inviteCode: session.inviteCode || null,
    inviteUrl: session.inviteUrl || null,
    inviteExpiresAt: session.inviteExpiresAt || null,
  };
  const serialized = JSON.stringify(normalized);
  memorySessions.set(gameId, normalized);

  try {
    localStorage.setItem(storageKey(gameId), serialized);
  } catch {
    try {
      sessionStorage.setItem(storageKey(gameId), serialized);
    } catch {
      // In-memory storage still supports navigation during this page lifetime.
    }
  }
}

export function loadGameSession(gameId) {
  const inMemory = memorySessions.get(gameId);
  if (inMemory) {
    return inMemory;
  }

  try {
    const value =
      localStorage.getItem(storageKey(gameId)) || sessionStorage.getItem(storageKey(gameId));
    if (!value) {
      return null;
    }
    const parsed = JSON.parse(value);
    memorySessions.set(gameId, parsed);
    return parsed;
  } catch {
    return null;
  }
}

export function updateGameSession(gameId, patch) {
  const current = loadGameSession(gameId) || { gameId };
  const updated = { ...current, ...patch };
  saveGameSession(gameId, updated);
  return updated;
}

export function createInviteUrl(inviteToken) {
  return `${window.location.origin}/join/${encodeURIComponent(inviteToken)}`;
}
