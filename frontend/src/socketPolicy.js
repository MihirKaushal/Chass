// The server closes with 1008 when it rejects a session (missing, expired, or
// invalid game or token). Retrying cannot succeed, so the client stops.
const POLICY_VIOLATION_CLOSE = 1008;
const FATAL_ERROR_STATUSES = new Set([401, 403, 404, 410]);

// While the socket is live it pushes bot moves and analysis results, so
// polling is only a slow safety net. Without it, polling carries updates.
const FALLBACK_POLL_MS = {
  botTurn: { connected: 5000, disconnected: 1000 },
  analysis: { connected: 4000, disconnected: 1500 },
};

export function socketShouldReconnect(closeCode, lastErrorStatus) {
  return closeCode !== POLICY_VIOLATION_CLOSE && !FATAL_ERROR_STATUSES.has(lastErrorStatus);
}

export function fallbackPollDelayMs(kind, connectionStatus) {
  const delays = FALLBACK_POLL_MS[kind];
  if (!delays) throw new Error(`Unknown poll kind: ${kind}`);
  return connectionStatus === "connected" ? delays.connected : delays.disconnected;
}
