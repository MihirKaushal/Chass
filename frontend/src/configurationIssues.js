const ISSUE_RULES = [
  {
    pattern: /point target cannot exceed/i,
    sectionId: "studio-victory",
    settingKey: "target-points",
  },
  {
    pattern: /kings? must begin outside|starting piece must be inside|starting square|starting barricade|marked center squares|only barricades may start|promotion rank|touching squares/i,
    sectionId: "studio-pieces",
    settingKey: "board-editor",
  },
  {
    pattern: /royal center|victory|check race|checkmate|point race|end.game/i,
    sectionId: "studio-victory",
    settingKey: "victory-mode",
  },
  {
    pattern: /abilit|necromancy|getaway|kamikaze|episcopal|power of love|eye for an eye|scorch/i,
    sectionId: "studio-abilities",
    settingKey: "ability-options",
  },
  {
    pattern: /gambit|army cap|army slot|piece limit|point limit|required king|shared draft|draft pool|army draft|private setup|maximum queens|board midpoint|deployment rows/i,
    sectionId: "studio-gambit",
    settingKey: "gambit-settings",
  },
  {
    pattern: /affinity|command point/i,
    sectionId: "studio-custom-rules",
    settingKey: "affinity-rules",
  },
  {
    pattern: /formation|no longer matches/i,
    sectionId: "studio-popular-modes",
    settingKey: "popular-modes",
  },
  {
    pattern: /uses a \d+x\d+ board/i,
    sectionId: "studio-board-size",
    settingKey: "board-dimensions",
  },
  {
    pattern: /insufficient material|starting|king|queen|pawn|bishop|rook|knight|barricade|piece|promotion rank|touching squares/i,
    sectionId: "studio-pieces",
    settingKey: "board-editor",
  },
];

export function locateConfigurationIssue(message = "") {
  const match = ISSUE_RULES.find((rule) => rule.pattern.test(message));
  if (match) {
    return { sectionId: match.sectionId, settingKey: match.settingKey };
  }
  return {
    sectionId: "studio-pieces",
    settingKey: "board-editor",
  };
}
