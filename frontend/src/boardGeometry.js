function squareKey(row, col) {
  return `${row}-${col}`;
}

export function boardFileLabel(column) {
  let value = Number(column) + 1;
  let result = "";
  while (value > 0) {
    value -= 1;
    result = String.fromCharCode(97 + (value % 26)) + result;
    value = Math.floor(value / 26);
  }
  return result;
}

export function boardSquareLabel(position, rows = 8) {
  if (!position) return "";
  return `${boardFileLabel(position.col)}${rows - position.row}`;
}

export function centeredBoardSquares(rows, cols, count) {
  if (rows <= 0 || cols <= 0 || count <= 0) return [];

  const centerRows = rows % 2 ? [Math.floor(rows / 2)] : [rows / 2 - 1, rows / 2];
  const candidates = centerRows.flatMap((row) =>
    Array.from({ length: cols }, (_, col) => ({ row, col }))
  );
  const candidateKeys = new Set(candidates.map(({ row, col }) => squareKey(row, col)));
  const limit = Math.min(count, candidates.length);
  const rotate = ({ row, col }) => ({ row: rows - 1 - row, col: cols - 1 - col });
  const distance = ({ row, col }) =>
    (2 * row - (rows - 1)) ** 2 + (2 * col - (cols - 1)) ** 2;
  const fixed = candidates.filter((square) => {
    const partner = rotate(square);
    return partner.row === square.row && partner.col === square.col;
  });
  const pairs = new Map();

  candidates.forEach((square) => {
    const partner = rotate(square);
    if (!candidateKeys.has(squareKey(partner.row, partner.col))) return;
    if (partner.row === square.row && partner.col === square.col) return;
    const ordered = [square, partner].sort((left, right) =>
      left.row - right.row || left.col - right.col
    );
    pairs.set(`${squareKey(ordered[0].row, ordered[0].col)}|${squareKey(ordered[1].row, ordered[1].col)}`, ordered);
  });

  const orderedPairs = [...pairs.values()].sort((left, right) =>
    distance(left[0]) - distance(right[0]) ||
    left[0].row - right[0].row ||
    left[0].col - right[0].col
  );
  const selected = [];
  if (limit % 2 && fixed.length) selected.push(fixed[0]);
  orderedPairs.some((pair) => {
    const remaining = limit - selected.length;
    if (remaining <= 0) return true;
    if (remaining >= 2) selected.push(...pair);
    else selected.push(pair[Math.floor(selected.length / 2) % 2]);
    return selected.length >= limit;
  });
  return selected;
}

export function barricadeSquares(rows, cols, count) {
  return centeredBoardSquares(rows, cols, count);
}

export function objectiveCenterSquares(rows, cols) {
  return centeredBoardSquares(rows, cols, 4);
}

function balanceAffinityBoardColors(rows, cols, selected) {
  const half = selected.length / 2;
  const parityCounts = [0, 0];
  selected.forEach(({ row, col }) => {
    parityCounts[(row + col) % 2] += 1;
  });
  if (parityCounts[0] === half) return selected;

  const underrepresented = parityCounts[0] < half ? 0 : 1;
  const overrepresented = 1 - underrepresented;
  const swapCount = half - parityCounts[underrepresented];
  const candidateRows = rows % 2
    ? Array.from({ length: rows }, (_, row) => row)
    : [rows / 2 - 1, rows / 2];
  const candidates = candidateRows.flatMap((row) =>
    Array.from({ length: cols }, (_, col) => ({ row, col }))
  );
  const selectedKeys = new Set(
    selected.map(({ row, col }) => squareKey(row, col))
  );
  const distance = ({ row, col }) =>
    (2 * row - (rows - 1)) ** 2 + (2 * col - (cols - 1)) ** 2;
  const additions = candidates
    .filter(({ row, col }) => (
      !selectedKeys.has(squareKey(row, col))
      && (row + col) % 2 === underrepresented
    ))
    .sort((left, right) =>
      distance(left) - distance(right)
      || left.col - right.col
      || left.row - right.row
    )
    .slice(0, swapCount);
  const removals = selected
    .filter(({ row, col }) => (row + col) % 2 === overrepresented)
    .sort((left, right) =>
      distance(right) - distance(left)
      || right.col - left.col
      || right.row - left.row
    )
    .slice(0, swapCount);
  const removalKeys = new Set(
    removals.map(({ row, col }) => squareKey(row, col))
  );
  return [
    ...selected.filter(({ row, col }) => !removalKeys.has(squareKey(row, col))),
    ...additions,
  ];
}

export function affinitySquares(rows, cols, count = 4) {
  if (rows <= 0 || cols <= 0) return { white: [], black: [] };

  const requested = Math.trunc(Number(count));
  const safeRequested = Number.isFinite(requested) ? requested : 4;
  const limit = Math.min(
    Math.max(2, safeRequested - (safeRequested % 2)),
    rows * cols,
    cols * 2
  );
  let selected;
  if (rows % 2 === 0) {
    selected = centeredBoardSquares(rows, cols, limit);
  } else {
    const centerRow = Math.floor(rows / 2);
    const rotate = ({ row, col }) => ({ row: rows - 1 - row, col: cols - 1 - col });
    const distance = ({ row, col }) =>
      (2 * row - (rows - 1)) ** 2 + (2 * col - (cols - 1)) ** 2;
    const collectPairs = (candidates) => {
      const pairs = new Map();
      candidates.forEach((square) => {
        const partner = rotate(square);
        if (partner.row === square.row && partner.col === square.col) return;
        const ordered = [square, partner].sort((left, right) =>
          left.row - right.row || left.col - right.col
        );
        pairs.set(
          `${squareKey(ordered[0].row, ordered[0].col)}|${squareKey(ordered[1].row, ordered[1].col)}`,
          ordered
        );
      });
      return [...pairs.values()].sort((left, right) =>
        distance(left[0]) - distance(right[0]) ||
        left[0].row - right[0].row ||
        left[0].col - right[0].col
      );
    };
    const centralPairs = collectPairs(
      Array.from({ length: cols }, (_, col) => ({ row: centerRow, col }))
    );
    const outerPairs = collectPairs(
      Array.from({ length: rows }, (_, row) => row)
        .filter((row) => row !== centerRow)
        .flatMap((row) => Array.from({ length: cols }, (_, col) => ({ row, col })))
    );
    selected = [];
    [...centralPairs, ...outerPairs].some((pair) => {
      selected.push(...pair);
      return selected.length >= limit;
    });
  }

  const ordered = balanceAffinityBoardColors(rows, cols, selected.slice(0, limit))
    .sort(
      (left, right) => left.row - right.row || left.col - right.col
    );
  const half = ordered.length / 2;
  let white;
  if (rows % 2) {
    white = ordered.filter((_, index) => index % 2 === 0);
  } else {
    const checkerWhite = ordered.filter(({ row, col }) => (row + col) % 2 === 0);
    white = checkerWhite.length === half
      ? checkerWhite
      : [...ordered]
        .sort((left, right) =>
          ((left.row + left.col) % 2) - ((right.row + right.col) % 2) ||
          left.row - right.row ||
          left.col - right.col
        )
        .slice(0, half);
  }
  const whiteKeys = new Set(white.map(({ row, col }) => squareKey(row, col)));
  return {
    white: [...white].sort((left, right) => left.row - right.row || left.col - right.col),
    black: ordered.filter(({ row, col }) => !whiteKeys.has(squareKey(row, col))),
  };
}

export function significantCenterSquares(
  rows,
  cols,
  { victoryMode = "", affinityEnabled = false, affinitySquareCount = 4 } = {}
) {
  const squares = new Map();
  const add = ({ row, col }) => squares.set(squareKey(row, col), { row, col });

  if (victoryMode === "center_dominion") {
    Object.values(affinitySquares(rows, cols, 4)).flat().forEach(add);
  }
  if (affinityEnabled) {
    Object.values(affinitySquares(rows, cols, affinitySquareCount)).flat().forEach(add);
  }
  if (victoryMode === "royal_center") {
    objectiveCenterSquares(rows, cols).forEach(add);
  }
  return [...squares.values()].sort((left, right) => (
    left.row - right.row || left.col - right.col
  ));
}
