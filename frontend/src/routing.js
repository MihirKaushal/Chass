import { useEffect, useRef, useState } from "react";


let activeNavigationBlocker = null;

function currentLocation() {
  return `${window.location.pathname}${window.location.search}${window.location.hash}`;
}

function navigationAllowed(path) {
  return !activeNavigationBlocker || activeNavigationBlocker(path) !== false;
}


function routeFromPath(pathname) {
  if (/^\/gambit\/?$/.test(pathname)) {
    return { name: "customize", preset: "gambit" };
  }

  if (/^\/customize\/?$/.test(pathname)) {
    const preset = new URLSearchParams(window.location.search).get("preset") || "";
    return { name: "customize", preset };
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

export function navigate(path, { replace = false, bypassBlocker = false } = {}) {
  if (!bypassBlocker && !navigationAllowed(path)) return false;
  if (replace) {
    window.history.replaceState({}, "", path);
  } else {
    window.history.pushState({}, "", path);
  }
  window.dispatchEvent(new PopStateEvent("popstate", {
    state: { chassNavigationApproved: true },
  }));
  return true;
}

export function useNavigationBlocker(blocker, enabled) {
  const blockerRef = useRef(blocker);
  blockerRef.current = blocker;

  useEffect(() => {
    if (!enabled) return undefined;
    const registered = (path) => blockerRef.current(path);
    activeNavigationBlocker = registered;
    const warnBeforeUnload = (event) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", warnBeforeUnload);
    return () => {
      if (activeNavigationBlocker === registered) activeNavigationBlocker = null;
      window.removeEventListener("beforeunload", warnBeforeUnload);
    };
  }, [enabled]);
}

export function useRoute() {
  const [route, setRoute] = useState(() => routeFromPath(window.location.pathname));
  const acceptedLocationRef = useRef(currentLocation());

  useEffect(() => {
    const handleLocationChange = (event) => {
      const nextLocation = currentLocation();
      const approved = event.state?.chassNavigationApproved === true;
      if (!approved && nextLocation !== acceptedLocationRef.current) {
        if (!navigationAllowed(nextLocation)) {
          window.history.pushState({}, "", acceptedLocationRef.current);
          return;
        }
      }
      acceptedLocationRef.current = nextLocation;
      setRoute(routeFromPath(window.location.pathname));
    };
    window.addEventListener("popstate", handleLocationChange);
    return () => window.removeEventListener("popstate", handleLocationChange);
  }, []);

  return route;
}
