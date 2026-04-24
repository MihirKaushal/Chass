import { useEffect, useMemo, useState } from "react";

const MIN_DIMENSION = 4;
const MAX_DIMENSION = 16;

function clampDimension(value) {
  if (!Number.isFinite(value)) {
    return MIN_DIMENSION;
  }
  return Math.max(MIN_DIMENSION, Math.min(MAX_DIMENSION, value));
}

function cloneBoard(board) {
  return board.map((row) => row.map((piece) => (piece ? { ...piece } : null)));
}

function createEmptyBoard(rows, cols) {
  return Array.from({ length: rows }, () => Array.from({ length: cols }, () => null));
}

function resizeBoardCentered(currentBoard, nextRows, nextCols) {
  const currentRows = currentBoard.length;
  const currentCols = currentBoard[0] ? currentBoard[0].length : 0;
  const resized = createEmptyBoard(nextRows, nextCols);

  const rowOffset = Math.floor((nextRows - currentRows) / 2);
  const colOffset = Math.floor((nextCols - currentCols) / 2);

  for (let row = 0; row < currentRows; row += 1) {
    for (let col = 0; col < currentCols; col += 1) {
      const nextRow = row + rowOffset;
      const nextCol = col + colOffset;
      if (nextRow < 0 || nextRow >= nextRows || nextCol < 0 || nextCol >= nextCols) {
        continue;
      }
      resized[nextRow][nextCol] = currentBoard[row][col];
    }
  }

  return resized;
}

function toPlacements(board) {
  const placements = [];
  for (let row = 0; row < board.length; row += 1) {
    for (let col = 0; col < board[row].length; col += 1) {
      const piece = board[row][col];
      if (!piece) {
        continue;
      }
      placements.push({ row, col, type: piece.type, color: piece.color });
    }
  }
  return placements;
}

function fileLabelFromCol(col) {
  return String.fromCharCode(65 + col);
}

function rankLabelFromRow(row, totalRows) {
  return String(totalRows - row);
}

function createClassicSetupBoard(rows, cols, definitionsByType) {
  const board = createEmptyBoard(rows, cols);
  const classicBackRank = ["rook", "knight", "bishop", "queen", "king", "bishop", "knight", "rook"];

  if (rows < 2 || cols < 8) {
    return board;
  }

  const colStart = Math.floor((cols - 8) / 2);

  for (let index = 0; index < 8; index += 1) {
    const col = colStart + index;
    const backType = classicBackRank[index];
    const backDefinition = definitionsByType[backType];
    const pawnDefinition = definitionsByType.pawn;

    if (backDefinition) {
      board[0][col] = {
        type: backDefinition.type,
        name: backDefinition.displayName,
        color: "black",
        points: backDefinition.points,
        symbol: backDefinition.symbols.black,
        hasMoved: false,
        isCustom: backDefinition.isCustom,
        customAttributes: backDefinition.customAttributes || {},
      };

      board[rows - 1][col] = {
        type: backDefinition.type,
        name: backDefinition.displayName,
        color: "white",
        points: backDefinition.points,
        symbol: backDefinition.symbols.white,
        hasMoved: false,
        isCustom: backDefinition.isCustom,
        customAttributes: backDefinition.customAttributes || {},
      };
    }

    if (pawnDefinition) {
      board[1][col] = {
        type: pawnDefinition.type,
        name: pawnDefinition.displayName,
        color: "black",
        points: pawnDefinition.points,
        symbol: pawnDefinition.symbols.black,
        hasMoved: false,
        isCustom: pawnDefinition.isCustom,
        customAttributes: pawnDefinition.customAttributes || {},
      };

      board[rows - 2][col] = {
        type: pawnDefinition.type,
        name: pawnDefinition.displayName,
        color: "white",
        points: pawnDefinition.points,
        symbol: pawnDefinition.symbols.white,
        hasMoved: false,
        isCustom: pawnDefinition.isCustom,
        customAttributes: pawnDefinition.customAttributes || {},
      };
    }
  }

  return board;
}

function pieceFromDefinition(definitionsByType, type, color) {
  const definition = definitionsByType[type];
  if (!definition) {
    return null;
  }

  return {
    type: definition.type,
    name: definition.displayName,
    color,
    points: definition.points,
    symbol: definition.symbols[color],
    hasMoved: false,
    isCustom: definition.isCustom,
    customAttributes: definition.customAttributes || {},
  };
}

function createPawnRaceBoard(definitionsByType) {
  const rows = 8;
  const cols = 8;
  const board = createEmptyBoard(rows, cols);

  for (let col = 0; col < cols; col += 1) {
    board[1][col] = pieceFromDefinition(definitionsByType, "pawn", "black");
    board[6][col] = pieceFromDefinition(definitionsByType, "pawn", "white");
  }

  board[0][4] = pieceFromDefinition(definitionsByType, "king", "black");
  board[7][4] = pieceFromDefinition(definitionsByType, "king", "white");

  return { rows, cols, board };
}

function createNoPawnsBoard(definitionsByType) {
  const rows = 8;
  const cols = 8;
  const board = createClassicSetupBoard(rows, cols, definitionsByType);

  for (let col = 0; col < cols; col += 1) {
    board[1][col] = null;
    board[6][col] = null;
  }

  return { rows, cols, board };
}

function createKnightSkirmishBoard(definitionsByType) {
  const rows = 6;
  const cols = 6;
  const board = createEmptyBoard(rows, cols);

  board[0][2] = pieceFromDefinition(definitionsByType, "king", "black");
  board[5][3] = pieceFromDefinition(definitionsByType, "king", "white");

  board[1][1] = pieceFromDefinition(definitionsByType, "knight", "black");
  board[1][4] = pieceFromDefinition(definitionsByType, "knight", "black");
  board[4][1] = pieceFromDefinition(definitionsByType, "knight", "white");
  board[4][4] = pieceFromDefinition(definitionsByType, "knight", "white");

  board[2][2] = pieceFromDefinition(definitionsByType, "pawn", "black");
  board[3][3] = pieceFromDefinition(definitionsByType, "pawn", "white");

  return { rows, cols, board };
}

function createHordeBoard(definitionsByType) {
  const rows = 8;
  const cols = 8;
  const board = createClassicSetupBoard(rows, cols, definitionsByType);

  for (let row = 4; row < 8; row += 1) {
    for (let col = 0; col < cols; col += 1) {
      board[row][col] = pieceFromDefinition(definitionsByType, "pawn", "white");
    }
  }

  board[7][4] = pieceFromDefinition(definitionsByType, "king", "white");

  return { rows, cols, board };
}

function createMiniCastleBoard(definitionsByType) {
  const rows = 8;
  const cols = 10;
  const board = createClassicSetupBoard(rows, cols, definitionsByType);

  board[0][0] = pieceFromDefinition(definitionsByType, "rook", "black");
  board[0][9] = pieceFromDefinition(definitionsByType, "rook", "black");
  board[7][0] = pieceFromDefinition(definitionsByType, "rook", "white");
  board[7][9] = pieceFromDefinition(definitionsByType, "rook", "white");

  return { rows, cols, board };
}

function CustomizationPanel({
  game,
  onApplyBasic,
  onApplyBoardLayout,
  onApplyPieceCustomization,
  onApplyRuleBuilder,
  onApplyRaw,
  onCreateNewGame,
}) {
  const initialRows = game.boardRows ?? game.boardSize;
  const initialCols = game.boardCols ?? game.boardSize;

  const [boardRows, setBoardRows] = useState(initialRows);
  const [boardCols, setBoardCols] = useState(initialCols);
  const [previewBoard, setPreviewBoard] = useState(() => cloneBoard(game.board));

  const [ruleToggles, setRuleToggles] = useState({});
  const [alignedEnemyCount, setAlignedEnemyCount] = useState(2);
  const [rawRules, setRawRules] = useState("[]");
  const [piecePointsByType, setPiecePointsByType] = useState({});
  const [selectedTool, setSelectedTool] = useState(null);
  const [scoreRaceTarget, setScoreRaceTarget] = useState(21);
  const [scoreRaceKingPoints, setScoreRaceKingPoints] = useState(1);

  const [localError, setLocalError] = useState("");

  const basicRuleSet = useMemo(
    () => game.rules.filter((rule) => rule.canDisable),
    [game.rules]
  );

  const definitionsByType = useMemo(
    () =>
      game.pieceDefinitions.reduce((accumulator, definition) => {
        accumulator[definition.type] = definition;
        return accumulator;
      }, {}),
    [game.pieceDefinitions]
  );

  const palettePieces = useMemo(
    () =>
      game.pieceDefinitions.flatMap((definition) => [
        {
          kind: "piece",
          key: `${definition.type}-white`,
          type: definition.type,
          color: "white",
          symbol: definition.symbols.white,
          label: `${definition.displayName} (White)`,
        },
        {
          kind: "piece",
          key: `${definition.type}-black`,
          type: definition.type,
          color: "black",
          symbol: definition.symbols.black,
          label: `${definition.displayName} (Black)`,
        },
      ]),
    [game.pieceDefinitions]
  );

  useEffect(() => {
    const rows = game.boardRows ?? game.boardSize;
    const cols = game.boardCols ?? game.boardSize;

    setBoardRows(rows);
    setBoardCols(cols);
    setPreviewBoard(cloneBoard(game.board));
    setLocalError("");
    setRuleToggles(
      game.rules.reduce((accumulator, rule) => {
        accumulator[rule.id] = rule.enabled;
        return accumulator;
      }, {})
    );
    setRawRules(
      JSON.stringify(
        game.rules.map((rule) => ({
          id: rule.id,
          enabled: rule.enabled,
          params: rule.params,
        })),
        null,
        2
      )
    );

    setPiecePointsByType(
      game.pieceDefinitions.reduce((accumulator, definition) => {
        accumulator[definition.type] = definition.points ?? "";
        return accumulator;
      }, {})
    );

    const firstDefinition = game.pieceDefinitions[0];
    if (firstDefinition) {
      setSelectedTool({
        kind: "piece",
        type: firstDefinition.type,
        color: "white",
      });
    }
  }, [game]);

  const placeToolAt = (row, col, tool) => {
    if (!tool) {
      return;
    }

    setPreviewBoard((current) => {
      const next = cloneBoard(current);

      if (tool.kind === "erase") {
        next[row][col] = null;
        return next;
      }

      const definition = definitionsByType[tool.type];
      if (!definition) {
        return current;
      }

      next[row][col] = {
        type: definition.type,
        name: definition.displayName,
        color: tool.color,
        points: definition.points,
        symbol: definition.symbols[tool.color],
        hasMoved: false,
        isCustom: definition.isCustom,
        customAttributes: definition.customAttributes || {},
      };

      return next;
    });
  };

  const setDimensions = (nextRows, nextCols) => {
    const normalizedRows = clampDimension(nextRows);
    const normalizedCols = clampDimension(nextCols);

    setBoardRows(normalizedRows);
    setBoardCols(normalizedCols);
    setPreviewBoard((current) => resizeBoardCentered(current, normalizedRows, normalizedCols));
  };

  const applyPresetClassic8x8 = () => {
    setBoardRows(8);
    setBoardCols(8);
    setPreviewBoard(createClassicSetupBoard(8, 8, definitionsByType));
  };

  const applyPresetEmpty10x10 = () => {
    setBoardRows(10);
    setBoardCols(10);
    setPreviewBoard(createEmptyBoard(10, 10));
  };

  const applyPresetCenteredClassicRectangular = () => {
    setBoardRows(8);
    setBoardCols(10);
    setPreviewBoard(createClassicSetupBoard(8, 10, definitionsByType));
  };

  const applyVariantMode = (variantBuilder) => {
    const variant = variantBuilder(definitionsByType);
    setBoardRows(variant.rows);
    setBoardCols(variant.cols);
    setPreviewBoard(variant.board);
  };

  const applyScoreRaceMode = async () => {
    setLocalError("");

    const targetScore = Number(scoreRaceTarget);
    const kingPoints = Number(scoreRaceKingPoints);

    if (!Number.isFinite(targetScore) || targetScore <= 0) {
      setLocalError("Score race target must be a positive number.");
      return;
    }

    if (!Number.isFinite(kingPoints) || kingPoints < 0) {
      setLocalError("King points must be zero or greater.");
      return;
    }

    const raceBoard = createClassicSetupBoard(8, 8, definitionsByType);
    const placements = toPlacements(raceBoard);
    const patches = game.rules
      .filter((rule) => rule.canDisable)
      .map((rule) => {
        if (rule.id === "score_target_win") {
          return {
            id: rule.id,
            enabled: true,
            params: {
              ...rule.params,
              targetScore,
            },
          };
        }

        if (["check", "checkmate", "stalemate"].includes(rule.id)) {
          return {
            id: rule.id,
            enabled: false,
            params: rule.params,
          };
        }

        return {
          id: rule.id,
          enabled: rule.enabled,
          params: rule.params,
        };
      });

    try {
      await onApplyPieceCustomization({
        pieces: [
          {
            type: "king",
            points: kingPoints,
            isCustom: true,
            customAttributes: {
              modeTag: "score_race",
            },
          },
        ],
      });

      await onApplyBasic({
        boardRows: 8,
        boardCols: 8,
        patches,
      });

      await onApplyBoardLayout({
        boardRows: 8,
        boardCols: 8,
        placements,
      });

      setBoardRows(8);
      setBoardCols(8);
      setPreviewBoard(raceBoard);
    } catch (modeError) {
      setLocalError(modeError?.message || "Unable to activate Score Race mode.");
    }
  };

  const applyBasicChanges = () => {
    setLocalError("");
    const patches = basicRuleSet.map((rule) => ({
      id: rule.id,
      enabled: Boolean(ruleToggles[rule.id]),
      params: rule.params,
    }));

    onApplyBasic({ boardRows, boardCols, patches });
  };

  const applyBoardLayout = () => {
    setLocalError("");
    onApplyBoardLayout({
      boardRows,
      boardCols,
      placements: toPlacements(previewBoard),
    });
  };

  const applyPointChanges = () => {
    setLocalError("");

    const pieces = [];
    for (const definition of game.pieceDefinitions) {
      const rawValue = piecePointsByType[definition.type];
      const normalizedPoints = rawValue === "" ? null : Number(rawValue);

      if (normalizedPoints !== null && Number.isNaN(normalizedPoints)) {
        setLocalError(`Point value for ${definition.displayName} must be numeric or blank.`);
        return;
      }

      pieces.push({
        type: definition.type,
        points: normalizedPoints,
        isCustom: true,
      });
    }

    onApplyPieceCustomization({
      pieces,
    });
  };

  const applyBuilderRule = () => {
    setLocalError("");
    onApplyRuleBuilder({
      rules: [
        {
          id: "double_capture_rook",
          enabled: true,
          params: {
            alignedEnemies: alignedEnemyCount,
            captureCount: 2,
          },
        },
      ],
    });
  };

  const applyRawRules = () => {
    setLocalError("");
    let parsed;
    try {
      parsed = JSON.parse(rawRules);
    } catch {
      setLocalError("Raw rule payload must be valid JSON");
      return;
    }

    if (!Array.isArray(parsed)) {
      setLocalError("Raw rule payload must be an array of rule patches");
      return;
    }

    onApplyRaw({ rules: parsed });
  };

  return (
    <section className="customization-panel">
      <h2>Customization Layers</h2>
      <p>Live preview your board, place pieces, and tune values before applying.</p>

      <div className="customize-workbench">
        <div className="customize-preview-column">
          <div className="customize-board-frame">
            <div
              className="customize-board-grid"
              style={{
                aspectRatio: `${boardCols} / ${boardRows}`,
                gridTemplateColumns: `repeat(${boardCols}, minmax(34px, 1fr))`,
                gridTemplateRows: `repeat(${boardRows}, minmax(34px, 1fr))`,
              }}
            >
              {Array.from({ length: boardRows }).map((_, row) =>
                Array.from({ length: boardCols }).map((__, col) => {
                  const piece = previewBoard[row]?.[col] || null;
                  const isLight = (row + col) % 2 === 0;

                  return (
                    <button
                      type="button"
                      key={`${row}-${col}`}
                      className={`customize-square ${isLight ? "light" : "dark"}`}
                      onClick={() => placeToolAt(row, col, selectedTool)}
                      onDragOver={(event) => event.preventDefault()}
                      onDrop={(event) => {
                        event.preventDefault();
                        const payload = event.dataTransfer.getData("application/chass-piece");
                        if (!payload) {
                          return;
                        }

                        try {
                          const tool = JSON.parse(payload);
                          setSelectedTool(tool);
                          placeToolAt(row, col, tool);
                        } catch {
                          setLocalError("Unable to drop piece onto board.");
                        }
                      }}
                    >
                      {col === 0 ? (
                        <span className="coord-label coord-rank">
                          {rankLabelFromRow(row, boardRows)}
                        </span>
                      ) : null}
                      {row === boardRows - 1 ? (
                        <span className="coord-label coord-file">
                          {fileLabelFromCol(col)}
                        </span>
                      ) : null}
                      <span className={`preview-piece ${piece ? "filled" : "empty"}`}>
                        {piece?.symbol || ""}
                      </span>
                    </button>
                  );
                })
              )}
            </div>
          </div>

          <div className="button-row">
            <button type="button" onClick={applyBoardLayout}>
              Apply Board Layout
            </button>
            <button
              type="button"
              className="secondary"
              onClick={() => setPreviewBoard(createEmptyBoard(boardRows, boardCols))}
            >
              Clear Board
            </button>
          </div>
        </div>

        <aside className="customize-sidebar">
          <div className="customization-card">
            <h3>Board Dimensions</h3>
            <div className="layer-grid two-col">
              <label className="field-label">
                Rows
                <input
                  type="number"
                  min={MIN_DIMENSION}
                  max={MAX_DIMENSION}
                  value={boardRows}
                  onChange={(event) => setDimensions(Number(event.target.value), boardCols)}
                />
              </label>

              <label className="field-label">
                Columns
                <input
                  type="number"
                  min={MIN_DIMENSION}
                  max={MAX_DIMENSION}
                  value={boardCols}
                  onChange={(event) => setDimensions(boardRows, Number(event.target.value))}
                />
              </label>
            </div>

            <div className="button-row">
              <button
                type="button"
                className="secondary"
                onClick={() => onCreateNewGame({ boardRows, boardCols })}
              >
                Create New Game
              </button>
            </div>
          </div>

          <div className="customization-card">
            <h3>Quick Presets</h3>
            <div className="preset-grid">
              <button type="button" className="secondary" onClick={applyPresetClassic8x8}>
                Classic 8x8
              </button>
              <button type="button" className="secondary" onClick={applyPresetEmpty10x10}>
                Empty 10x10
              </button>
              <button
                type="button"
                className="secondary"
                onClick={applyPresetCenteredClassicRectangular}
              >
                Centered Classic 8x10
              </button>
            </div>
          </div>

          <div className="customization-card">
            <h3>Game Modes</h3>
            <p className="palette-hint">One click loads a playable mini-game into preview.</p>
            <div className="preset-grid variant-grid">
              <button
                type="button"
                className="secondary"
                onClick={() => applyVariantMode(createNoPawnsBoard)}
              >
                No Pawns (8x8)
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => applyVariantMode(createPawnRaceBoard)}
              >
                Pawn Race (8x8)
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => applyVariantMode(createKnightSkirmishBoard)}
              >
                Knight Skirmish (6x6)
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => applyVariantMode(createHordeBoard)}
              >
                Horde (8x8)
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => applyVariantMode(createMiniCastleBoard)}
              >
                Castle Siege (8x10)
              </button>
            </div>
            <div className="mode-box">
              <h4>Score Race Mode</h4>
              <p className="palette-hint">
                First player to target points wins. Kings are treated like regular point pieces.
              </p>
              <div className="layer-grid two-col">
                <label className="field-label">
                  Target Score
                  <input
                    type="number"
                    min="1"
                    value={scoreRaceTarget}
                    onChange={(event) => setScoreRaceTarget(event.target.value)}
                  />
                </label>
                <label className="field-label">
                  King Points
                  <input
                    type="number"
                    min="0"
                    value={scoreRaceKingPoints}
                    onChange={(event) => setScoreRaceKingPoints(event.target.value)}
                  />
                </label>
              </div>
              <button type="button" onClick={applyScoreRaceMode}>
                Activate Score Race Mode
              </button>
            </div>
          </div>

          <div className="customization-card">
            <h3>Piece Palette</h3>
            <p className="palette-hint">Drag onto board, or select and click a square.</p>
            <div className="piece-palette-grid">
              <button
                type="button"
                className={`palette-tile ${selectedTool?.kind === "erase" ? "active" : ""}`}
                onClick={() => setSelectedTool({ kind: "erase" })}
                draggable
                onDragStart={(event) => {
                  event.dataTransfer.setData(
                    "application/chass-piece",
                    JSON.stringify({ kind: "erase" })
                  );
                }}
              >
                <span className="palette-symbol">⌫</span>
                <span className="palette-label">Eraser</span>
              </button>

              {palettePieces.map((palettePiece) => {
                const isActive =
                  selectedTool?.kind === "piece" &&
                  selectedTool?.type === palettePiece.type &&
                  selectedTool?.color === palettePiece.color;

                return (
                  <button
                    type="button"
                    key={palettePiece.key}
                    className={`palette-tile ${isActive ? "active" : ""}`}
                    onClick={() =>
                      setSelectedTool({
                        kind: "piece",
                        type: palettePiece.type,
                        color: palettePiece.color,
                      })
                    }
                    draggable
                    onDragStart={(event) => {
                      event.dataTransfer.setData(
                        "application/chass-piece",
                        JSON.stringify({
                          kind: "piece",
                          type: palettePiece.type,
                          color: palettePiece.color,
                        })
                      );
                    }}
                  >
                    <span className="palette-symbol">{palettePiece.symbol}</span>
                    <span className="palette-label">{palettePiece.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </aside>
      </div>

      <div className="customization-card">
        <h3>Layer 1: Basic Setup</h3>

        <div className="rule-toggle-grid">
          {basicRuleSet.map((rule) => (
            <label key={rule.id} className="rule-toggle">
              <input
                type="checkbox"
                checked={Boolean(ruleToggles[rule.id])}
                onChange={(event) =>
                  setRuleToggles((current) => ({
                    ...current,
                    [rule.id]: event.target.checked,
                  }))
                }
              />
              <span>
                <strong>{rule.name}</strong>
                <small>{rule.description}</small>
              </span>
            </label>
          ))}
        </div>

        <div className="button-row">
          <button type="button" onClick={applyBasicChanges}>
            Apply Basic Settings
          </button>
        </div>
      </div>

      <details className="customization-card" open>
        <summary>Layer 2: Piece Point Values</summary>
        <div className="piece-points-grid">
          {game.pieceDefinitions.map((definition) => (
            <label key={definition.type} className="field-label">
              {definition.displayName}
              <input
                type="number"
                value={piecePointsByType[definition.type] ?? ""}
                onChange={(event) =>
                  setPiecePointsByType((current) => ({
                    ...current,
                    [definition.type]: event.target.value,
                  }))
                }
                placeholder="Leave blank for no points"
              />
            </label>
          ))}
        </div>

        <button type="button" onClick={applyPointChanges}>
          Apply Point Values
        </button>
      </details>

      <details className="customization-card">
        <summary>Layer 3: Rule Builder</summary>
        <div className="builder-preview">
          <p>
            IF rook moves AND <strong>{alignedEnemyCount}</strong> enemies aligned
          </p>
          <p>THEN capture both (Double Capture Rule)</p>
        </div>

        <label className="field-label">
          Aligned Enemies
          <select
            value={alignedEnemyCount}
            onChange={(event) => setAlignedEnemyCount(Number(event.target.value))}
          >
            <option value="2">2</option>
            <option value="3">3</option>
          </select>
        </label>

        <button type="button" onClick={applyBuilderRule}>
          Activate Builder Rule
        </button>
      </details>

      <details className="customization-card">
        <summary>Advanced: Raw Rule JSON</summary>
        <textarea
          className="raw-editor"
          value={rawRules}
          onChange={(event) => setRawRules(event.target.value)}
          rows={12}
        />
        <button type="button" onClick={applyRawRules}>
          Apply Raw Rules
        </button>
      </details>

      {localError ? <p className="error">{localError}</p> : null}
    </section>
  );
}

export default CustomizationPanel;
