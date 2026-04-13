const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
    },
    ...options,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    const detail = payload.detail || "Request failed";
    throw new Error(detail);
  }

  return response.json();
}

export function createGame(payload) {
  return request("/game/create", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getGame(gameId) {
  return request(`/game/${gameId}`);
}

export function makeMove(gameId, payload) {
  return request(`/game/${gameId}/move`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateRules(gameId, payload) {
  return request(`/game/${gameId}/rules`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updatePieces(gameId, payload) {
  return request(`/game/${gameId}/pieces`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function resetGame(gameId, payload = {}) {
  return request(`/game/${gameId}/reset`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getWebSocketUrl(gameId) {
  const normalized = API_BASE.replace("http://", "ws://").replace("https://", "wss://");
  return `${normalized}/game/ws/${gameId}`;
}
