export function recordedTurnCount(game) {
  const totalMoves = game?.historyPagination?.totalMoves;
  if (Number.isInteger(totalMoves) && totalMoves >= 0) return totalMoves;
  return Array.isArray(game?.history) ? game.history.length : 0;
}

export function shouldConfirmCustomizeNavigation(game) {
  return (
    game?.phase === "play"
    && !game?.winner
    && recordedTurnCount(game) > 0
  );
}

export function shouldConfirmDiscardingCustomization(configurationModified) {
  return configurationModified === true;
}
