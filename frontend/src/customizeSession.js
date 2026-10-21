const STORAGE_KEY = "chass-customizer-session";
const SESSION_VERSION = 1;

function validSession(session) {
  const draft = session?.draft;
  return (
    session?.version === SESSION_VERSION &&
    typeof session.initialPreset === "string" &&
    draft &&
    typeof draft === "object" &&
    Array.isArray(draft.enabledPieces) &&
    Array.isArray(draft.placements) &&
    [
      "pointValues",
      "pieceParameters",
      "pieceCaps",
      "victory",
      "customRules",
      "specialAbilities",
      "gambit",
    ].every((key) => draft[key] && typeof draft[key] === "object")
  );
}

export function createCustomizeSessionStore(
  storage = () => window.sessionStorage,
) {
  let current;
  const read = () => {
    if (current !== undefined) return current;
    try {
      const saved = JSON.parse(storage().getItem(STORAGE_KEY));
      current = validSession(saved) ? saved : null;
    } catch {
      current = null;
    }
    return current;
  };
  return {
    read,
    save(snapshot) {
      const session = { ...snapshot, version: SESSION_VERSION };
      if (!validSession(session)) return;
      current = session;
      try {
        storage().setItem(STORAGE_KEY, JSON.stringify(session));
      } catch {
        // Keep navigation safe even when tab storage is blocked or full.
      }
    },
    clear() {
      current = null;
      try {
        storage().removeItem(STORAGE_KEY);
      } catch {
        // The in-memory copy is still discarded.
      }
    },
    returnPath() {
      const path = read()?.path;
      return typeof path === "string" &&
        /^\/(customize|gambit)\/?(?:[?#]|$)/.test(path)
        ? path
        : "/customize";
    },
  };
}

export const customizeSession = createCustomizeSessionStore();
