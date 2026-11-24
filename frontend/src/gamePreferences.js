export const GAME_PREFERENCES_KEY = "chass:play-preferences";
const FIELDS = ["autoFlip", "flipped", "analysis"];

function booleans(value) {
  return Object.fromEntries(FIELDS.filter((key) => typeof value?.[key] === "boolean").map((key) => [key, value[key]]));
}
function read(storage) {
  try {
    const value = JSON.parse(storage?.getItem(GAME_PREFERENCES_KEY) || "{}");
    return value && typeof value === "object" ? value : {};
  } catch { return {}; }
}
export function preferenceSeat({ gameId, mode, color }) {
  return `${gameId}:${mode}:${color || "local"}`;
}
export function readGamePreferences(storage, context) {
  const saved = read(storage);
  const defaults = booleans(saved.defaults?.[context.mode]);
  delete defaults.flipped;
  return {
    autoFlip: context.mode === "local",
    flipped: context.color === "black",
    analysis: true,
    ...defaults,
    ...booleans(saved.games?.[preferenceSeat(context)]),
  };
}
export function saveGamePreferences(storage, context, preferences) {
  const saved = read(storage);
  const values = booleans(preferences);
  const key = preferenceSeat(context);
  const games = Object.entries(saved.games || {}).filter(([id]) => id !== key).slice(-31);
  try {
    storage?.setItem(GAME_PREFERENCES_KEY, JSON.stringify({
      defaults: { ...saved.defaults, [context.mode]: { autoFlip: values.autoFlip, analysis: values.analysis } },
      games: Object.fromEntries([...games, [key, values]]),
    }));
  } catch { /* Preferences are optional when browser storage is unavailable. */ }
}
