export function onlineInviteState({
  mode,
  gameReady,
  playerColor,
  playerRole,
  presence,
  connectionStatus,
}) {
  if (mode !== "online") return null;

  if (!gameReady) {
    return playerRole === "host"
      ? { targetColor: "black", reconnect: false }
      : null;
  }

  if (
    !["white", "black"].includes(playerColor)
    || connectionStatus !== "connected"
    || presence?.[playerColor] !== true
  ) {
    return null;
  }

  const targetColor = playerColor === "white" ? "black" : "white";
  return presence?.[targetColor] === false
    ? { targetColor, reconnect: true }
    : null;
}
