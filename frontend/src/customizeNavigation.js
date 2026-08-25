export const CUSTOMIZE_SECTION_LINKS = [
  {
    id: "studio-popular-modes",
    label: "Starting Systems",
    keywords: "classic chass gambit draft preset formation horde castle siege no pawns",
  },
  {
    id: "studio-board-size",
    label: "Board Size",
    keywords: "dimensions rows columns 8x8 10x10 16x16 custom",
  },
  {
    id: "studio-pieces",
    label: "Pieces",
    keywords: "point values movement army limits placements king queen rook pawn custom catapult maharani barricade hypnotizer diplomat cannibal elephant clear board",
  },
  {
    id: "studio-victory",
    label: "End Game Logic",
    keywords: "victory checkmate king capture timed point race elimination royal score center dominion royal center check race timer score",
  },
  {
    id: "studio-custom-rules",
    label: "Custom Rules",
    keywords: "affinity squares command points center",
  },
  {
    id: "studio-abilities",
    label: "Special Abilities",
    keywords: "necromancy getaway eye for an eye kamikaze episcopal power of love scorch cooldown",
  },
  {
    id: "studio-gambit",
    label: "Chass Gambit Settings",
    keywords: "private army shared draft maximum points pieces queens setup rows",
  },
  {
    id: "rulebook",
    label: "Rulebook",
    keywords: "help guide reference explanation descriptions encyclopedia codex",
  },
];

export function matchingCustomizeSections(query) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) return CUSTOMIZE_SECTION_LINKS;
  const terms = normalized.split(/\s+/);
  return CUSTOMIZE_SECTION_LINKS.filter(({ label, keywords }) => {
    const searchableText = `${label} ${keywords}`.toLowerCase();
    return terms.every((term) => searchableText.includes(term));
  });
}
