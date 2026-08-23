const API_BASE = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");
let catalogPromise = null;

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request(path, { token, headers, ...options } = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
    ...options,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const detail =
      typeof payload.detail === "string"
        ? payload.detail
        : Array.isArray(payload.detail) && payload.detail[0]?.msg
          ? payload.detail[0].msg
          : "The game server rejected the request.";
    throw new ApiError(detail, response.status);
  }

  return response.json();
}

export function createGame(payload) {
  return request("/game/create", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getCatalog() {
  if (!catalogPromise) {
    catalogPromise = request("/game/catalog").catch((error) => {
      catalogPromise = null;
      throw error;
    });
  }
  return catalogPromise;
}

export function validateGameConfiguration(payload) {
  return request("/game/validate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function joinGame(inviteCredential) {
  const compactCode = inviteCredential.trim().replace(/[\s-]/g, "");
  const payload = /^[a-z0-9]{8}$/i.test(compactCode)
    ? { inviteCode: compactCode.toUpperCase() }
    : { inviteToken: inviteCredential };
  return request("/game/join", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getGame(gameId, token) {
  return request(`/game/${gameId}`, { token });
}

export function getMatchAnalysis(gameId, token) {
  return request(`/game/${gameId}/analysis`, { token });
}

export function getGameHistory(gameId, { before, limit = 50 } = {}, token) {
  const query = new URLSearchParams({ limit: String(limit) });
  if (before) {
    query.set("before", String(before));
  }
  return request(`/game/${gameId}/history?${query.toString()}`, { token });
}

export function makeMove(gameId, payload, token) {
  return request(`/game/${gameId}/move`, {
    method: "POST",
    body: JSON.stringify(payload),
    token,
  });
}

export function useGameAction(gameId, payload, token) {
  return request(`/game/${gameId}/action`, {
    method: "POST",
    body: JSON.stringify(payload),
    token,
  });
}

export function selectAbility(gameId, payload, token) {
  return request(`/game/${gameId}/ability`, {
    method: "POST",
    body: JSON.stringify(payload),
    token,
  });
}

export function completeSetupHandoff(gameId, payload, token) {
  return request(`/game/${gameId}/setup/handoff`, {
    method: "POST",
    body: JSON.stringify(payload),
    token,
  });
}

export function updateGambitDeployment(gameId, payload, token) {
  return request(`/game/${gameId}/gambit/deployment`, {
    method: "POST",
    body: JSON.stringify(payload),
    token,
  });
}

export function updateGambitDraft(gameId, payload, token) {
  return request(`/game/${gameId}/gambit/draft`, {
    method: "POST",
    body: JSON.stringify(payload),
    token,
  });
}

export function readyGambitDeployment(gameId, payload, token) {
  return request(`/game/${gameId}/gambit/ready`, {
    method: "POST",
    body: JSON.stringify(payload),
    token,
  });
}

export function completeGambitHandoff(gameId, payload, token) {
  return request(`/game/${gameId}/gambit/handoff`, {
    method: "POST",
    body: JSON.stringify(payload),
    token,
  });
}

export function useCommandPower(gameId, payload, token) {
  return request(`/game/${gameId}/command`, {
    method: "POST",
    body: JSON.stringify(payload),
    token,
  });
}

export function updateRules(gameId, payload, token) {
  return request(`/game/${gameId}/rules`, {
    method: "POST",
    body: JSON.stringify(payload),
    token,
  });
}

export function updatePieces(gameId, payload, token) {
  return request(`/game/${gameId}/pieces`, {
    method: "POST",
    body: JSON.stringify(payload),
    token,
  });
}

export function updateBoardLayout(gameId, payload, token) {
  return request(`/game/${gameId}/layout`, {
    method: "POST",
    body: JSON.stringify(payload),
    token,
  });
}

export function requestRematch(gameId, payload, token) {
  return request(`/game/${gameId}/rematch`, {
    method: "POST",
    body: JSON.stringify(payload),
    token,
  });
}

export function replaceInvite(gameId, token) {
  return request(`/game/${gameId}/invite`, {
    method: "POST",
    body: JSON.stringify({}),
    token,
  });
}

export function getWebSocketUrl(gameId) {
  const normalized = API_BASE.replace("http://", "ws://").replace("https://", "wss://");
  return `${normalized}/game/ws/${encodeURIComponent(gameId)}`;
}
