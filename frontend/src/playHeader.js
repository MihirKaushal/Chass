function title(value) {
  return value ? value.replace(/\b\w/g, (letter) => letter.toUpperCase()) : "";
}

export function onlinePlayerSummary(playerColor, presence, gameReady) {
  if (!["white", "black"].includes(playerColor)) {
    return "You are spectating this online room.";
  }
  const opponent = playerColor === "white" ? "black" : "white";
  const opponentState = !gameReady
    ? "has not joined"
    : presence?.[opponent]
      ? "is connected"
      : "is disconnected";
  return `You are playing as ${title(playerColor)}. ${title(opponent)} ${opponentState}.`;
}

export function roomLabel(mode) {
  return mode === "online" ? "Online Room" : "Local Room";
}
