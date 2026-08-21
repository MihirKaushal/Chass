import { useEffect, useRef, useState } from "react";

const COMPACT_QUERY = "(max-width: 1300px)";

function useCompactPlayLayout() {
  const [compact, setCompact] = useState(
    () => typeof window !== "undefined" && window.matchMedia(COMPACT_QUERY).matches
  );

  useEffect(() => {
    const media = window.matchMedia(COMPACT_QUERY);
    const update = () => setCompact(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);

  return compact;
}

function Drawer({ id, label, openPanel, compact, onClose, children }) {
  const isOpen = compact && openPanel === id;
  return (
    <div
      className={`responsive-play-panel panel-${id}${isOpen ? " is-open" : ""}`}
      aria-hidden={compact ? !isOpen : undefined}
      inert={compact && !isOpen ? "" : undefined}
    >
      <header className="play-panel-drawer-header">
        <button
          type="button"
          className="play-panel-grab"
          aria-label={`Close ${label}`}
          onClick={onClose}
        >
          <i />
        </button>
        <strong>{label}</strong>
        <button
          type="button"
          className="play-panel-close"
          aria-label={`Close ${label}`}
          onClick={onClose}
        >
          ×
        </button>
      </header>
      {children}
    </div>
  );
}

function ResponsivePlayLayout({
  className = "",
  effects,
  board,
  info,
  effectCount = 0,
  moveCount = 0,
}) {
  const compact = useCompactPlayLayout();
  const [openPanel, setOpenPanel] = useState(null);
  const effectsButtonRef = useRef(null);
  const infoButtonRef = useRef(null);

  useEffect(() => {
    if (!compact) setOpenPanel(null);
  }, [compact]);

  useEffect(() => {
    if (!openPanel) return undefined;
    const closeOnEscape = (event) => {
      if (event.key !== "Escape") return;
      const trigger = openPanel === "effects" ? effectsButtonRef.current : infoButtonRef.current;
      setOpenPanel(null);
      trigger?.focus();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [openPanel]);

  const closePanel = () => {
    const trigger = openPanel === "effects" ? effectsButtonRef.current : infoButtonRef.current;
    setOpenPanel(null);
    window.setTimeout(() => trigger?.focus(), 0);
  };

  return (
    <main className={`play-layout play-layout-three-column ${className}`.trim()}>
      {compact && openPanel ? (
        <button
          type="button"
          className="play-panel-backdrop"
          aria-label="Close game panel"
          onClick={closePanel}
        />
      ) : null}

      <Drawer
        id="effects"
        label="Effects And Actions"
        openPanel={openPanel}
        compact={compact}
        onClose={closePanel}
      >
        {effects}
      </Drawer>

      {board}

      <Drawer
        id="info"
        label="Game And Moves"
        openPanel={openPanel}
        compact={compact}
        onClose={closePanel}
      >
        {info}
      </Drawer>

      <nav className="play-panel-dock" aria-label="Game side panels">
        <button
          ref={effectsButtonRef}
          type="button"
          className={openPanel === "effects" ? "active" : ""}
          aria-expanded={openPanel === "effects"}
          onClick={() => setOpenPanel((current) => current === "effects" ? null : "effects")}
        >
          <i aria-hidden="true">✦</i>
          <span>Effects</span>
          {effectCount ? <b>{effectCount}</b> : null}
        </button>
        <button
          ref={infoButtonRef}
          type="button"
          className={openPanel === "info" ? "active" : ""}
          aria-expanded={openPanel === "info"}
          onClick={() => setOpenPanel((current) => current === "info" ? null : "info")}
        >
          <i aria-hidden="true">≡</i>
          <span>Game &amp; Moves</span>
          {moveCount ? <b>{moveCount}</b> : null}
        </button>
      </nav>
    </main>
  );
}

export default ResponsivePlayLayout;
