export function shouldConfirmGameNavigation(game) {
  return Boolean(game && game.phase !== "finished");
}

export function shouldConfirmDiscardingCustomization(configurationModified) {
  return configurationModified === true;
}
