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

export function affinitySquares(rows, cols) {
  if (rows % 2) {
    const line = centeredBoardSquares(rows, cols, 4).sort((left, right) => left.col - right.col);
    return {
      white: [line[0], line[2]],
      black: [line[1], line[3]],
    };
  }

  const [leftCol, rightCol] = centeredBoardSquares(1, cols, 2)
    .map((square) => square.col)
    .sort((left, right) => left - right);
  const upperRow = rows / 2 - 1;
  const lowerRow = rows / 2;
  return {
    white: [{ row: upperRow, col: leftCol }, { row: lowerRow, col: rightCol }],
    black: [{ row: upperRow, col: rightCol }, { row: lowerRow, col: leftCol }],
  };
}

export function significantCenterSquares(
  rows,
  cols,
  { victoryMode = "", affinityEnabled = false } = {}
) {
  const squares = new Map();
  const add = ({ row, col }) => squares.set(squareKey(row, col), { row, col });

  if (victoryMode === "center_dominion" || affinityEnabled) {
    Object.values(affinitySquares(rows, cols)).flat().forEach(add);
  }
  if (victoryMode === "royal_center") {
    objectiveCenterSquares(rows, cols).forEach(add);
  }
  return [...squares.values()].sort((left, right) => (
    left.row - right.row || left.col - right.col
  ));
}
