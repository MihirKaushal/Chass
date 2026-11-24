import { useEffect, useRef, useState } from "react";

import { getWebSocketUrl } from "../api/gameApi";
import { socketShouldReconnect } from "../socketPolicy";


const HEARTBEAT_MS = 25000;
const MAX_RECONNECT_MS = 10000;

export default function useGameSocket({
  gameId,
  token,
  enabled = true,
  onGame,
  onPresence,
  onEvent,
  onError,
}) {
  const callbacksRef = useRef({ onGame, onPresence, onEvent, onError });
  const [connectionStatus, setConnectionStatus] = useState(enabled ? "connecting" : "offline");

  callbacksRef.current = { onGame, onPresence, onEvent, onError };

  useEffect(() => {
    if (!enabled || !gameId) {
      setConnectionStatus("offline");
      return undefined;
    }

    let socket = null;
    let heartbeatTimer = null;
    let reconnectTimer = null;
    let stopped = false;
    let reconnectAttempt = 0;
    let lastErrorStatus = null;

    const clearHeartbeat = () => {
      if (heartbeatTimer) {
        window.clearInterval(heartbeatTimer);
        heartbeatTimer = null;
      }
    };

    const connect = () => {
      if (stopped) {
        return;
      }

      setConnectionStatus(reconnectAttempt > 0 ? "reconnecting" : "connecting");
      socket = new WebSocket(getWebSocketUrl(gameId));

      socket.onopen = () => {
        reconnectAttempt = 0;
        lastErrorStatus = null;
        setConnectionStatus("connected");
        // The server replies to authentication with the current game state.
        socket.send(JSON.stringify({ type: "authenticate", token: token || null }));
        heartbeatTimer = window.setInterval(() => {
          if (socket?.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: "ping" }));
          }
        }, HEARTBEAT_MS);
      };

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (
            payload.type === "game_state" ||
            payload.type === "game_ended" ||
            payload.type === "rematch_state"
          ) {
            if (payload.game) {
              callbacksRef.current.onGame?.(payload.game);
            }
          } else if (payload.type === "presence") {
            callbacksRef.current.onPresence?.(payload);
          } else if (payload.type === "error") {
            lastErrorStatus = payload.status ?? null;
            callbacksRef.current.onError?.(payload.message || "Real-time connection failed.");
          } else {
            callbacksRef.current.onEvent?.(payload);
          }
        } catch {
          callbacksRef.current.onError?.("Received an unreadable real-time update.");
        }
      };

      socket.onerror = () => {
        setConnectionStatus("reconnecting");
      };

      socket.onclose = (event) => {
        clearHeartbeat();
        if (stopped) {
          return;
        }
        if (!socketShouldReconnect(event.code, lastErrorStatus)) {
          setConnectionStatus("offline");
          return;
        }

        reconnectAttempt += 1;
        setConnectionStatus("reconnecting");
        const delay = Math.min(1000 * 2 ** (reconnectAttempt - 1), MAX_RECONNECT_MS);
        reconnectTimer = window.setTimeout(connect, delay);
      };
    };

    const requestSync = () => {
      if (document.visibilityState === "visible" && socket?.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({ type: "sync" }));
      }
    };

    connect();
    document.addEventListener("visibilitychange", requestSync);

    return () => {
      stopped = true;
      clearHeartbeat();
      if (reconnectTimer) {
        window.clearTimeout(reconnectTimer);
      }
      document.removeEventListener("visibilitychange", requestSync);
      socket?.close();
    };
  }, [enabled, gameId, token]);

  return connectionStatus;
}
