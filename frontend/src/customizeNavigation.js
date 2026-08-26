export const CUSTOMIZE_SECTION_LINKS = [
  {
    id: "studio-popular-modes",
    label: "Starting Systems",
    keywords: "overall setup preset formation",
  },
  {
    id: "studio-board-size",
    label: "Board Size",
    keywords: "dimensions rows columns board size custom",
  },
  {
    id: "studio-pieces",
    label: "Pieces",
    keywords: "piece catalog values movement placement board editor",
  },
  {
    id: "studio-victory",
    label: "Win Condition",
    keywords: "victory win ending condition end game logic",
  },
  {
    id: "studio-custom-rules",
    label: "Custom Rules",
    keywords: "custom board-wide rules system",
  },
  {
    id: "studio-abilities",
    label: "Special Abilities",
    keywords: "abilities powers player selection",
  },
  {
    id: "studio-gambit",
    label: "Chass Gambit Settings",
    keywords: "private army construction draft setup",
  },
  {
    id: "rulebook",
    label: "Rulebook",
    keywords: "help guide reference explanation descriptions encyclopedia codex",
  },
];

const STATIC_SETTING_LINKS = [
  {
    id: "setting-match-analysis",
    label: "Match Analysis",
    sectionId: "studio-custom-rules",
    category: "Custom Rules",
    targetId: "customize-match-analysis",
    keywords: "stockfish fairy analysis automatic engine outcome estimate parity",
  },
  {
    id: "setting-popular-formations",
    label: "Starting Layout Presets",
    sectionId: "studio-popular-modes",
    category: "Starting Systems",
    targetId: "customize-popular-formations",
    keywords: "starting arrangement layout formation popular board formations",
  },
  {
    id: "setting-board-dimensions",
    label: "Board Dimensions",
    sectionId: "studio-board-size",
    category: "Board Size",
    targetId: "customize-board-dimensions",
    keywords: "rows columns 8x8 10x10 16x16 width height",
  },
  {
    id: "setting-board-editor",
    label: "Board Editor",
    sectionId: "studio-pieces",
    category: "Pieces",
    targetId: "customize-board-editor",
    keywords: "placement clear erase undo mirror restore white black",
  },
  {
    id: "setting-piece-values",
    label: "Piece Point Values",
    sectionId: "studio-pieces",
    category: "Pieces",
    targetId: "studio-pieces",
    keywords: "points score cost values",
  },
  {
    id: "setting-affinity-squares",
    label: "Affinity Squares",
    sectionId: "studio-custom-rules",
    category: "Custom Rules",
    targetId: "customize-affinity-squares",
    keywords: "center control command points cap",
  },
  {
    id: "setting-abilities-per-player",
    label: "Abilities Per Player",
    sectionId: "studio-abilities",
    category: "Special Abilities",
    targetId: "customize-ability-count",
    keywords: "maximum count allowed selection",
  },
  {
    id: "setting-gambit-points",
    label: "Maximum Gambit Points",
    sectionId: "studio-gambit",
    category: "Chass Gambit Settings",
    targetId: "customize-gambit-settings",
    keywords: "budget cost army points",
  },
  {
    id: "setting-gambit-pieces",
    label: "Maximum Gambit Pieces",
    sectionId: "studio-gambit",
    category: "Chass Gambit Settings",
    targetId: "customize-gambit-settings",
    keywords: "army cap piece limit",
  },
  {
    id: "setting-gambit-rows",
    label: "Private Setup Rows",
    sectionId: "studio-gambit",
    category: "Chass Gambit Settings",
    targetId: "customize-gambit-settings",
    keywords: "deployment home rows private setup",
  },
  {
    id: "setting-gambit-queens",
    label: "Maximum Queens",
    sectionId: "studio-gambit",
    category: "Chass Gambit Settings",
    targetId: "customize-gambit-settings",
    keywords: "queen army limit cap",
  },
  {
    id: "setting-shared-draft",
    label: "Shared Draft",
    sectionId: "studio-gambit",
    category: "Chass Gambit Settings",
    targetId: "customize-gambit-settings",
    keywords: "draft gambit pool alternating picks",
  },
];

function sectionResult(section) {
  return {
    ...section,
    sectionId: section.id,
    targetId: section.id,
    kind: "section",
  };
}

function tunableSearchText(entry) {
  return (entry.tunableParameters || [])
    .flatMap((parameter) => [parameter.label, parameter.description])
    .join(" ");
}

export function buildCustomizeSearchIndex(catalog = {}) {
  const modes = (catalog.popularModes || []).map((mode) => ({
    id: `mode-${mode.id}`,
    label: mode.name,
    sectionId: "studio-popular-modes",
    category: "Starting Systems",
    targetId: `customize-mode-${mode.id}`,
    keywords: `${mode.id} ${mode.summary || ""}`,
    kind: "starting-system",
  }));
  const formations = (catalog.formations || []).map((formation) => ({
    id: `formation-${formation.id}`,
    label: formation.name,
    sectionId: "studio-popular-modes",
    category: "Starting Layout Presets",
    targetId: `customize-formation-${formation.id}`,
    keywords: `${formation.id} ${formation.summary || ""}`,
    kind: "formation",
  }));
  const pieces = (catalog.pieces || []).map((piece) => ({
    id: `piece-${piece.type}`,
    label: piece.name,
    sectionId: "studio-pieces",
    category: "Pieces",
    targetId: `customize-piece-${piece.type}`,
    keywords: [
      piece.type,
      piece.isCustom ? "custom piece" : "classic piece",
      piece.description,
      piece.movement,
      ...(piece.rules || []),
      tunableSearchText(piece),
    ].filter(Boolean).join(" "),
    kind: "piece",
    pieceFilter: piece.isCustom ? "custom" : "classic",
  }));
  const victoryModes = (catalog.victoryModes || []).map((mode) => ({
    id: `victory-${mode.id}`,
    label: mode.name,
    sectionId: "studio-victory",
    category: "Win Condition",
    targetId: `customize-victory-${mode.id}`,
    keywords: `${mode.id} ${mode.id === "timed" ? "timer clock" : ""} ${mode.summary || ""}`,
    kind: "victory",
  }));
  const abilities = (catalog.specialAbilities || []).map((ability) => ({
    id: `ability-${ability.id}`,
    label: ability.name,
    sectionId: "studio-abilities",
    category: "Special Abilities",
    targetId: `customize-ability-${ability.id}`,
    keywords: [
      ability.id,
      ability.summary,
      ability.description,
      ...(ability.rules || []),
      tunableSearchText(ability),
    ].filter(Boolean).join(" "),
    kind: "ability",
  }));

  return [
    ...CUSTOMIZE_SECTION_LINKS.map(sectionResult),
    ...STATIC_SETTING_LINKS,
    ...modes,
    ...formations,
    ...pieces,
    ...victoryModes,
    ...abilities,
  ];
}

function normalizedText(value) {
  return String(value || "").trim().toLowerCase();
}

function resultRank(result, query) {
  const label = normalizedText(result.label);
  if (label === query) return 0;
  if (label.startsWith(query)) return 1;
  if (label.includes(query)) return 2;
  return 3;
}

export function matchingCustomizeResults(query, catalog = {}) {
  const normalized = normalizedText(query);
  if (!normalized) return CUSTOMIZE_SECTION_LINKS.map(sectionResult);

  const terms = normalized.split(/\s+/);
  return buildCustomizeSearchIndex(catalog)
    .filter((result) => {
      const searchableText = normalizedText(`${result.label} ${result.keywords || ""}`);
      return terms.every((term) => searchableText.includes(term));
    })
    .sort((left, right) => (
      resultRank(left, normalized) - resultRank(right, normalized)
      || left.label.localeCompare(right.label)
    ));
}

export function nextCustomizeResultIndex(currentIndex, resultCount, direction) {
  if (resultCount <= 0) return -1;
  if (currentIndex < 0 || currentIndex >= resultCount) {
    return direction < 0 ? resultCount - 1 : 0;
  }
  return (currentIndex + direction + resultCount) % resultCount;
}
