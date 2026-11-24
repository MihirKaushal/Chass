const RELOAD_FLAG = "chass:chunk-reload";

function sessionStorageOrNull() {
  try {
    return globalThis.sessionStorage ?? null;
  } catch {
    return null;
  }
}

// After a deploy, an open tab may request route chunks whose hashed names no
// longer exist. Reload once to fetch the current build; if the import still
// fails, surface the error instead of reloading forever.
export function importWithReload(
  load,
  { storage = sessionStorageOrNull(), reload = () => window.location.reload() } = {}
) {
  return load().then(
    (module) => {
      storage?.removeItem(RELOAD_FLAG);
      return module;
    },
    (error) => {
      if (!storage || storage.getItem(RELOAD_FLAG)) throw error;
      storage.setItem(RELOAD_FLAG, "1");
      reload();
      return new Promise(() => {});
    }
  );
}
