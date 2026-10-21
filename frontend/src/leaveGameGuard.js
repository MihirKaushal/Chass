export function shouldConfirmGameNavigation(game) {
  return Boolean(game && game.phase !== "finished");
}

export function shouldConfirmDiscardingCustomization(configurationModified, destination = "") {
  const path = destination.split(/[?#]/, 1)[0];
  return configurationModified === true && !/^\/rulebook\/?$/.test(path);
}
