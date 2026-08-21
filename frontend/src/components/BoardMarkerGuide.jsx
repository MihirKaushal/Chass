import { useEffect, useId, useRef, useState } from "react";

import IconCloseButton from "./IconCloseButton";

const MARKERS = [
  {
    color: "Blue dot",
    description: "Make a normal move or standard capture on this square.",
    kind: "move-dot",
  },
  {
    color: "Red target",
    description: "Use a special attack or complete a sacrifice.",
    icon: "x",
    marker: "attack",
  },
  {
    color: "Teal target",
    description: "Use special movement, such as moving a Barricade.",
    icon: "↔",
    marker: "move",
  },
  {
    color: "Gold target",
    description: "Use an ability, swap, or command action.",
    icon: "✦",
    marker: "ability",
  },
  {
    color: "Green target",
    description: "Summon or return a piece to the board.",
    icon: "+",
    marker: "summon",
  },
  {
    color: "Ember target",
    description: "Scorch the square without moving a piece.",
    icon: "♨",
    marker: "scorch",
  },
];

function MarkerSample({ marker }) {
  if (marker.kind === "move-dot") {
    return (
      <span className="board-marker-guide-sample" aria-hidden="true">
        <span className="move-dot" />
      </span>
    );
  }

  return (
    <span className="board-marker-guide-sample" aria-hidden="true">
      <span className={`board-action-marker marker-${marker.marker}`}>
        <i>{marker.icon}</i>
      </span>
    </span>
  );
}

function BoardMarkerGuide() {
  const [isOpen, setIsOpen] = useState(false);
  const panelId = useId();
  const triggerRef = useRef(null);
  const closeRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return undefined;

    closeRef.current?.focus();
    const closeOnEscape = (event) => {
      if (event.key !== "Escape") return;
      setIsOpen(false);
      triggerRef.current?.focus();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [isOpen]);

  const closeGuide = () => {
    setIsOpen(false);
    triggerRef.current?.focus();
  };

  return (
    <div className="board-marker-guide">
      <button
        ref={triggerRef}
        type="button"
        className="board-marker-guide-trigger"
        aria-label={`${isOpen ? "Close" : "Open"} board marker guide`}
        aria-haspopup="dialog"
        aria-expanded={isOpen}
        aria-controls={panelId}
        title="Board marker guide"
        onClick={() => setIsOpen((current) => !current)}
      >
        i
      </button>

      {isOpen ? (
        <section
          id={panelId}
          className="board-marker-guide-panel"
          role="dialog"
          aria-labelledby={`${panelId}-title`}
        >
          <header className="board-marker-guide-header">
            <div>
              <span>Board Guide</span>
              <h2 id={`${panelId}-title`}>Target Markers</h2>
            </div>
            <IconCloseButton
              ref={closeRef}
              className="board-marker-guide-close"
              label="Close board marker guide"
              onClick={closeGuide}
            />
          </header>

          <ul className="board-marker-guide-list">
            {MARKERS.map((marker) => (
              <li key={marker.color}>
                <MarkerSample marker={marker} />
                <span>
                  <strong>{marker.color}</strong>
                  <small>{marker.description}</small>
                </span>
              </li>
            ))}
          </ul>

          <p className="board-marker-guide-tip">
            <span aria-hidden="true">i</span>
            <span>
              <strong>Piece details</strong> Double-tap a piece to open its information card.
            </span>
          </p>
        </section>
      ) : null}
    </div>
  );
}

export default BoardMarkerGuide;
