const PLAYER_COLORS = new Set(["white", "black"]);

function colorName(color) {
  return color ? color.charAt(0).toUpperCase() + color.slice(1) : "";
}

export function effectPerspectiveColor(game, playerColor = null) {
  if (PLAYER_COLORS.has(playerColor)) return playerColor;
  if (game?.mode === "bot" && PLAYER_COLORS.has(game.bot?.humanColor)) {
    return game.bot.humanColor;
  }
  if (game?.mode === "local" && PLAYER_COLORS.has(game.currentPlayer)) {
    return game.currentPlayer;
  }
  return null;
}

export function effectOwnerDescriptor(owner, perspectiveColor, mode) {
  if (owner === "neutral") {
    return {
      label: "Neutral · Shared",
      relation: "neutral",
    };
  }

  const ownerColor = colorName(owner);
  if (!PLAYER_COLORS.has(owner) || !PLAYER_COLORS.has(perspectiveColor)) {
    return {
      label: ownerColor || "Unknown side",
      relation: "unassigned",
    };
  }

  const isPlayer = owner === perspectiveColor;
  const relation = mode === "local"
    ? (isPlayer ? "Current Player" : "Other Player")
    : (isPlayer ? "You" : "Opponent");
  return {
    label: `${relation} · ${ownerColor}`,
    relation: isPlayer ? "self" : "opponent",
  };
}

export function pieceCountsByOwner(board, pieceType) {
  const counts = { white: 0, black: 0, neutral: 0 };
  (board || []).flat().forEach((piece) => {
    if (
      piece?.type === pieceType
      && Object.prototype.hasOwnProperty.call(counts, piece.color)
    ) {
      counts[piece.color] += 1;
    }
  });
  return counts;
}
