function title(value) {
  return value ? value.replace(/\b\w/g, (letter) => letter.toUpperCase()) : "";
}

export function onlinePlayerSummary(playerColor, presence, gameReady) {
  const status = onlinePlayerStatus(playerColor, presence, gameReady);
  if (status.role === "spectator") {
    return "You are spectating this online room.";
  }
  const opponentState = status.connection === "waiting"
    ? "has not joined"
    : status.connection === "connected"
      ? "is connected"
      : "is disconnected";
  return `You are playing as ${title(status.playerColor)}. ${title(status.opponentColor)} ${opponentState}.`;
}

export function onlinePlayerStatus(playerColor, presence, gameReady) {
  if (!["white", "black"].includes(playerColor)) {
    return { role: "spectator" };
  }
  const opponentColor = playerColor === "white" ? "black" : "white";
  return {
    role: "player",
    playerColor,
    opponentColor,
    connection: !gameReady
      ? "waiting"
      : presence?.[opponentColor]
        ? "connected"
        : "disconnected",
  };
}

export function roomLabel(mode) {
  return mode === "online" ? "Online Room" : "Local Room";
}
