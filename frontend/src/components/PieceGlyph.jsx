const CUSTOM_VISUALS = new Set([
  "maharani",
  "catapult",
  "barricade",
  "hypnotizer",
  "diplomat",
  "cannibal",
  "elephant",
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
  if (type === "diplomat") {
    return (
      <svg viewBox="0 0 64 64" aria-hidden="true">
        <circle cx="32" cy="24" r="16" />
        <path d="M16 24h32M19 15c8 4 18 4 26 0M19 33c8-4 18-4 26 0" />
        <path d="M32 8c6 5 9 10 9 16s-3 12-9 16c-6-4-9-10-9-16s3-11 9-16Z" />
        <path d="M27 40v7h-8l-4 9h34l-4-9h-8v-7" />
      </svg>
    );
  }
  if (type === "cannibal") {
    return (
      <svg viewBox="0 0 64 64" aria-hidden="true">
        <path d="M13 19c5-11 33-11 38 0v21c0 11-8 18-19 18S13 51 13 40V19Z" />
        <path d="m20 25 7 3M44 25l-7 3" />
        <path d="M17 37c4-8 26-8 30 0-2 11-8 17-15 17s-13-6-15-17Z" />
        <path d="m19 37 5 8 4-10 4 10 4-10 4 10 5-8" />
      </svg>
    );
  }
  if (type === "elephant") {
    return (
      <svg viewBox="0 0 64 64" aria-hidden="true">
        <path d="M24 20c-5-9-15-9-19 0-5 11 2 23 18 23M40 20c5-9 15-9 19 0 5 11-2 23-18 23" />
        <path d="M23 18c2-7 16-7 18 0l2 16c0 6-5 11-11 11s-11-5-11-11l2-16Z" />
        <path d="M32 34v18c0 5 3 8 7 8s7-3 7-7" />
        <path d="M24 35c-4 4-4 9-1 13M40 35c4 4 4 9 1 13" />
        <circle cx="27" cy="27" r="2" /><circle cx="37" cy="27" r="2" />
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
