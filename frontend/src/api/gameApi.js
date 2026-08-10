const API_BASE = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

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
      typeof payload.detail === "string" ? payload.detail : "The game server rejected the request.";
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

export function joinGame(inviteToken) {
  return request("/game/join", {
    method: "POST",
    body: JSON.stringify({ inviteToken }),
  });
}

export function getGame(gameId, token) {
  return request(`/game/${gameId}`, { token });
}

export function makeMove(gameId, payload, token) {
  return request(`/game/${gameId}/move`, {
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

export function useGambitPower(gameId, payload, token) {
  return request(`/game/${gameId}/gambit/power`, {
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

export function resetGame(gameId, payload = {}, token) {
  return request(`/game/${gameId}/reset`, {
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
