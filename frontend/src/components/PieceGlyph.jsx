const CUSTOM_VISUALS = new Set([
  "maharani",
  "catapult",
  "barricade",
  "hypnotizer",
  "diplomat",
  "cannibal",
]);

function CustomPieceMark({ type }) {
  if (type === "maharani") {
    return (
      <svg viewBox="0 0 64 64" aria-hidden="true">
        <path d="M10 48h44l-4 8H14l-4-8Zm3-28 11 10 8-18 8 18 11-10-4 24H17l-4-24Z" />
        <circle cx="13" cy="18" r="4" /><circle cx="32" cy="9" r="4" /><circle cx="51" cy="18" r="4" />
      </svg>
    );
  }
  if (type === "catapult") {
    return (
      <svg viewBox="0 0 64 64" aria-hidden="true">
        <circle cx="19" cy="48" r="8" /><circle cx="45" cy="48" r="8" />
        <path d="M14 43h37M23 41l18-25 5 4-18 25M40 14l10 3-4 9-10-4Z" />
      </svg>
    );
  }
  if (type === "barricade") {
    return (
      <svg viewBox="0 0 64 64" aria-hidden="true">
        <path d="M8 14h48v40H8zM8 27h48M8 40h48M20 14v13M43 14v13M31 27v13M19 40v14M44 40v14" />
      </svg>
    );
  }
  if (type === "hypnotizer") {
    return (
      <svg viewBox="0 0 64 64" aria-hidden="true">
        <path d="M32 7c15 0 25 10 25 24S47 56 32 56 7 47 7 33 16 11 29 11s20 8 20 19-8 18-18 18-16-7-16-15 6-14 14-14 12 5 12 11-5 10-10 10-8-3-8-7 3-7 7-7" />
      </svg>
    );
  }
  if (type === "cannibal") {
    return (
      <svg viewBox="0 0 64 64" aria-hidden="true">
        <path d="M9 17c8-8 38-8 46 0v30c-8 9-38 9-46 0V17Zm8 8 8 8 7-10 7 10 8-8v17H17V25Z" />
        <path d="M18 47h28M24 47v7M32 47v8M40 47v7" />
        <circle cx="21" cy="18" r="3" /><circle cx="43" cy="18" r="3" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 64 64" aria-hidden="true">
      <path d="M32 8v48M19 15c0 10 5 16 13 17-8 1-13 7-13 17M45 15c0 10-5 16-13 17 8 1 13 7 13 17M12 20c7 0 12-3 15-9M52 20c-7 0-12-3-15-9M14 50h36" />
      <circle cx="32" cy="32" r="6" />
    </svg>
  );
}

function PieceGlyph({ piece, type, color, symbol, className = "" }) {
  const pieceType = type || piece?.type;
  const pieceColor = color || piece?.color || "neutral";
  const fallback = symbol || piece?.symbol || piece?.icon || "?";
  const classes = [
    "piece-glyph",
    CUSTOM_VISUALS.has(pieceType) ? "piece-glyph-custom" : "piece-glyph-classic",
    `piece-glyph-${pieceColor}`,
    className,
  ].filter(Boolean).join(" ");

  return (
    <span className={classes} aria-hidden="true">
      {CUSTOM_VISUALS.has(pieceType) ? <CustomPieceMark type={pieceType} /> : fallback}
    </span>
  );
}

export default PieceGlyph;
