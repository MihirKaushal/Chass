import { useEffect, useState } from "react";


function routeFromPath(pathname) {
  if (/^\/gambit\/?$/.test(pathname)) {
    return { name: "gambit" };
  }

  const joinMatch = pathname.match(/^\/join\/([^/]+)\/?$/);
  if (joinMatch) {
    return { name: "join", inviteToken: decodeURIComponent(joinMatch[1]) };
  }

  const gameMatch = pathname.match(/^\/game\/([^/]+)\/?$/);
  if (gameMatch) {
    return { name: "game", gameId: decodeURIComponent(gameMatch[1]) };
  }

  return { name: "home" };
}

export function navigate(path, { replace = false } = {}) {
  if (replace) {
    window.history.replaceState({}, "", path);
  } else {
    window.history.pushState({}, "", path);
  }
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function useRoute() {
  const [route, setRoute] = useState(() => routeFromPath(window.location.pathname));

  useEffect(() => {
    const handleLocationChange = () => setRoute(routeFromPath(window.location.pathname));
    window.addEventListener("popstate", handleLocationChange);
    return () => window.removeEventListener("popstate", handleLocationChange);
  }, []);

  return route;
}
