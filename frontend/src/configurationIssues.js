import { barricadeSquares, significantCenterSquares } from "./boardGeometry.js";

const ISSUE_RULES = [
  {
    pattern: /point target cannot exceed/i,
    sectionId: "studio-victory",
    settingKey: "target-points",
  },
  {
    pattern: /king cannot begin in check or checkmate/i,
    sectionId: "studio-pieces",
    settingKey: "board-editor",
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

function issueSquareKey(square) {
  return `${square.row}-${square.col}`;
}

function uniqueVisibleSquares(squares, rows, cols) {
  const unique = new Map();
  squares.forEach((square) => {
    if (
      Number.isInteger(square?.row)
      && Number.isInteger(square?.col)
      && square.row >= 0
      && square.row < rows
      && square.col >= 0
      && square.col < cols
    ) {
      unique.set(issueSquareKey(square), { row: square.row, col: square.col });
    }
  });
  return [...unique.values()];
}

export function configurationIssueSquares(message = "", draft = {}) {
  const rows = Number(draft.boardRows);
  const cols = Number(draft.boardCols);
  const placements = Array.isArray(draft.placements) ? draft.placements : [];
  if (!Number.isInteger(rows) || !Number.isInteger(cols)) return [];

  let matches = [];
  if (/pawns cannot begin on a promotion rank/i.test(message)) {
    matches = placements.filter((piece) => (
      piece.type === "pawn"
      && (
        (piece.color === "white" && piece.row === 0)
        || (piece.color === "black" && piece.row === rows - 1)
      )
    ));
  } else if (/king cannot begin in check or checkmate/i.test(message)) {
    const color = message.match(/^(white|black)/i)?.[1]?.toLowerCase();
    matches = placements.filter((piece) => (
      piece.type === "king" && piece.color === color
    ));
  } else if (/two kings cannot begin on touching squares/i.test(message)) {
    const whiteKings = placements.filter((piece) => piece.type === "king" && piece.color === "white");
    const blackKings = placements.filter((piece) => piece.type === "king" && piece.color === "black");
    whiteKings.forEach((whiteKing) => {
      blackKings.forEach((blackKing) => {
        if (
          Math.max(
            Math.abs(whiteKing.row - blackKing.row),
            Math.abs(whiteKing.col - blackKing.col)
          ) <= 1
        ) {
          matches.push(whiteKing, blackKing);
        }
      });
    });
  } else if (
    /marked center squares|only barricades may start there|kings? must begin outside.*royal center/i.test(message)
  ) {
    const centerKeys = new Set(
      significantCenterSquares(rows, cols, {
        victoryMode: draft.victory?.mode,
        affinityEnabled: Boolean(draft.customRules?.affinityEnabled),
      }).map(issueSquareKey)
    );
    matches = placements.filter((piece) => (
      piece.type !== "barricade" && centerKeys.has(issueSquareKey(piece))
    ));
  } else if (/starting barricade positions must remain empty/i.test(message)) {
    const reservedKeys = new Set(
      barricadeSquares(rows, cols, draft.barricadeCount || 0).map(issueSquareKey)
    );
    matches = placements.filter((piece) => (
      piece.type !== "barricade" && reservedKeys.has(issueSquareKey(piece))
    ));
  } else if (/starting barricades must use the reserved central squares/i.test(message)) {
    const reservedKeys = new Set(
      barricadeSquares(rows, cols, draft.barricadeCount || 0).map(issueSquareKey)
    );
    matches = placements.filter((piece) => (
      piece.type === "barricade" && !reservedKeys.has(issueSquareKey(piece))
    ));
  } else if (/only one piece may occupy each starting square/i.test(message)) {
    const counts = new Map();
    placements.forEach((piece) => {
      const key = issueSquareKey(piece);
      counts.set(key, (counts.get(key) || 0) + 1);
    });
    matches = placements.filter((piece) => counts.get(issueSquareKey(piece)) > 1);
  } else if (/must begin with exactly one king/i.test(message)) {
    const color = message.match(/^(white|black)/i)?.[1]?.toLowerCase();
    const kings = placements.filter((piece) => piece.type === "king" && piece.color === color);
    matches = kings.length > 1 ? kings : [];
  } else if (/^starting .+ is not enabled/i.test(message)) {
    const pieceType = message.match(/^starting (.+) is not enabled/i)?.[1]
      ?.trim()
      .toLowerCase()
      .replaceAll(" ", "_");
    matches = placements.filter((piece) => piece.type === pieceType);
  } else if (/barricades must be neutral/i.test(message)) {
    matches = placements.filter((piece) => piece.type === "barricade" && piece.color !== "neutral");
  } else if (/only barricades may be neutral/i.test(message)) {
    matches = placements.filter((piece) => piece.type !== "barricade" && piece.color === "neutral");
  }

  return uniqueVisibleSquares(matches, rows, cols);
}
