import { useEffect, useMemo, useState } from "react";

import { getCatalog } from "../api/gameApi";

const MIN_DIMENSION = 4;
const MAX_DIMENSION = 16;
const STANDARD_TYPES = ["pawn", "knight", "bishop", "rook", "queen", "king"];
const BACK_RANK = ["rook", "knight", "bishop", "queen", "king", "bishop", "knight", "rook"];

function title(value) {
  return value ? value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase()) : "";
}

function clamp(value, minimum, maximum) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return minimum;
  }
  return Math.max(minimum, Math.min(maximum, Math.trunc(number)));
}

function coordinate(row, col, rows) {
  return `${String.fromCharCode(65 + col)}${rows - row}`;
}

function classicLayout(rows, cols) {
  if (rows < 4 || cols < 8) {
    const kingCol = Math.floor(cols / 2);
    return [
      { row: 0, col: kingCol, type: "king", color: "black" },
      { row: rows - 1, col: kingCol, type: "king", color: "white" },
    ];
  }
  const startCol = Math.floor((cols - 8) / 2);
  const placements = [];
  BACK_RANK.forEach((type, index) => {
    placements.push({ row: 0, col: startCol + index, type, color: "black" });
    placements.push({ row: rows - 1, col: startCol + index, type, color: "white" });
    placements.push({ row: 1, col: startCol + index, type: "pawn", color: "black" });
    placements.push({ row: rows - 2, col: startCol + index, type: "pawn", color: "white" });
  });
  return placements;
}

function centeredResize(placements, oldRows, oldCols, rows, cols) {
  const rowOffset = Math.floor((rows - oldRows) / 2);
  const colOffset = Math.floor((cols - oldCols) / 2);
  return placements
    .map((piece) => ({ ...piece, row: piece.row + rowOffset, col: piece.col + colOffset }))
    .filter((piece) => piece.row >= 0 && piece.row < rows && piece.col >= 0 && piece.col < cols);
}

function formationLayout(id, rows, cols) {
  const base = classicLayout(rows, cols);
  if (id === "no_pawns") {
    return base.filter((piece) => piece.type !== "pawn");
  }
  if (id === "pawn_race") {
    return base.filter((piece) => ["pawn", "king"].includes(piece.type));
  }
  if (id === "knight_skirmish") {
    return [
      { row: 0, col: 2, type: "king", color: "black" },
      { row: 1, col: 1, type: "knight", color: "black" },
      { row: 1, col: 4, type: "knight", color: "black" },
      { row: 5, col: 3, type: "king", color: "white" },
      { row: 4, col: 1, type: "knight", color: "white" },
      { row: 4, col: 4, type: "knight", color: "white" },
    ];
  }
  if (id === "horde") {
    const pieces = base.filter((piece) => piece.color === "black");
    for (let row = rows - 4; row < rows; row += 1) {
      for (let col = 0; col < cols; col += 1) {
        pieces.push({ row, col, type: "pawn", color: "white" });
      }
    }
    pieces[Math.floor(pieces.length / 2)] = {
      row: rows - 1,
      col: Math.floor(cols / 2),
      type: "king",
      color: "white",
    };
    return pieces;
  }
  if (id === "castle_siege") {
    return classicLayout(rows, cols).filter((piece) => piece.type !== "knight");
  }
  return base;
}

const FORMATIONS = [
  {
    id: "no_pawns",
    name: "No Pawns",
    icon: "♜",
    summary: "Open lines immediately by removing every Pawn.",
    rows: 8,
    cols: 8,
  },
  {
    id: "pawn_race",
    name: "Pawn Race",
    icon: "♟",
    summary: "Kings and Pawns only, with promotion deciding the attack.",
    rows: 8,
    cols: 8,
  },
  {
    id: "knight_skirmish",
    name: "Knight Skirmish",
    icon: "♞",
    summary: "A compact 6x6 tactical duel built around Knight forks.",
    rows: 6,
    cols: 6,
  },
  {
    id: "horde",
    name: "Horde",
    icon: "⚑",
    summary: "A dense Pawn army challenges a conventional force.",
    rows: 8,
    cols: 8,
  },
  {
    id: "castle_siege",
    name: "Castle Siege",
    icon: "🏰",
    summary: "A wider 8x10 battlefield with long defensive lanes.",
    rows: 8,
    cols: 10,
  },
];

function defaultDraft(catalog) {
  const pointValues = {};
  const pieceCaps = {};
  catalog.pieces.forEach((piece) => {
    pointValues[piece.type] = Math.max(0, piece.points ?? 0);
    pieceCaps[piece.type] = piece.type === "king" ? 1 : piece.type === "queen" ? 2 : 16;
  });
  return {
    presetId: "classic",
    boardRows: 8,
    boardCols: 8,
    enabledPieces: [...STANDARD_TYPES],
    pointValues,
    pieceCaps,
    placements: classicLayout(8, 8),
    victory: {
      mode: "checkmate",
      targetPoints: 21,
      timeSeconds: 600,
      kingPoints: 0,
    },
    specialAbilities: { enabled: false, allowed: [] },
    gambit: {
      enabled: false,
      budget: 39,
      maxPieces: 16,
      setupRows: 2,
      maxQueens: 2,
      affinityEnabled: true,
      commandPointCap: 3,
    },
  };
}

function ConfigurationBoard({ draft, catalog, selectedTool, onSelectTool, onPlace }) {
  const definitionMap = useMemo(
    () => new Map(catalog.pieces.map((piece) => [piece.type, piece])),
    [catalog]
  );
  const placementMap = useMemo(
    () => new Map(draft.placements.map((piece) => [`${piece.row}-${piece.col}`, piece])),
    [draft.placements]
  );
  const setupRows = new Set([
    ...Array.from({ length: Math.min(draft.gambit.setupRows, draft.boardRows) }, (_, index) => index),
    ...Array.from(
      { length: Math.min(draft.gambit.setupRows, draft.boardRows) },
      (_, index) => draft.boardRows - 1 - index
    ),
  ]);

  return (
    <div className="studio-preview-stack">
      <div className="studio-board-frame">
        <div
          className="studio-board"
          style={{
            aspectRatio: `${draft.boardCols} / ${draft.boardRows}`,
            gridTemplateColumns: `repeat(${draft.boardCols}, minmax(0, 1fr))`,
            gridTemplateRows: `repeat(${draft.boardRows}, minmax(0, 1fr))`,
            "--studio-piece-size": `${Math.max(0.7, Math.min(1.8, 14 / draft.boardCols))}rem`,
          }}
        >
          {Array.from({ length: draft.boardRows }).map((_, row) =>
            Array.from({ length: draft.boardCols }).map((__, col) => {
              const gambitBarricade =
                draft.gambit.enabled &&
                draft.enabledPieces.includes("barricade") &&
                row === Math.max(0, Math.floor(draft.boardRows / 2) - 1) &&
                col === Math.max(0, Math.floor(draft.boardCols / 2) - 1);
              const placement = gambitBarricade
                ? { row, col, type: "barricade", color: "neutral" }
                : placementMap.get(`${row}-${col}`);
              const definition = placement ? definitionMap.get(placement.type) : null;
              const symbol = placement
                ? definition?.symbols?.[placement.color] || definition?.icon || "?"
                : "";
              const affinityRows = [
                Math.max(0, Math.floor(draft.boardRows / 2) - 1),
                Math.min(draft.boardRows - 1, Math.floor(draft.boardRows / 2)),
              ];
              const affinityCols = [
                Math.max(0, Math.floor(draft.boardCols / 2) - 1),
                Math.min(draft.boardCols - 1, Math.floor(draft.boardCols / 2)),
              ];
              const affinity =
                draft.gambit.enabled && draft.gambit.affinityEnabled &&
                affinityRows.includes(row) && affinityCols.includes(col);
              return (
                <button
                  type="button"
                  key={`${row}-${col}`}
                  className={[
                    "studio-square",
                    (row + col) % 2 === 0 ? "light" : "dark",
                    draft.gambit.enabled && setupRows.has(row) ? "setup-zone" : "",
                    affinity ? "studio-affinity" : "",
                  ].filter(Boolean).join(" ")}
                  disabled={draft.gambit.enabled}
                  onClick={() => onPlace(row, col)}
                  title={
                    draft.gambit.enabled
                      ? "Players arrange their own private setup when the game begins."
                      : `${coordinate(row, col, draft.boardRows)}${placement ? `: ${placement.color} ${placement.type}` : ""}`
                  }
                >
                  {col === 0 ? <span className="studio-rank">{draft.boardRows - row}</span> : null}
                  {row === draft.boardRows - 1 ? (
                    <span className="studio-file">{String.fromCharCode(65 + col)}</span>
                  ) : null}
                  <span className={`studio-piece ${definition?.isCustom ? "custom" : ""}`}>
                    {symbol}
                  </span>
                </button>
              );
            })
          )}
        </div>
      </div>

      <div className="board-tool-readout">
        <span>{draft.gambit.enabled ? "Private Setup Preview" : "Board Editor"}</span>
        <strong>
          {draft.gambit.enabled
            ? `${draft.gambit.setupRows} home rows per player`
            : selectedTool?.kind === "erase"
              ? "Eraser selected"
              : selectedTool
                ? `${title(selectedTool.color)} ${title(selectedTool.type)} selected`
                : "Choose a piece below"}
        </strong>
        {!draft.gambit.enabled ? (
          <button type="button" className="text-button" onClick={() => onSelectTool({ kind: "erase" })}>
            Use Eraser
          </button>
        ) : null}
      </div>
    </div>
  );
}

function Toggle({ checked, onChange, label, description }) {
  return (
    <label className="studio-toggle">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span className="toggle-track" aria-hidden="true"><i /></span>
      <span className="toggle-copy">
        <strong>{label}</strong>
        <small>{description}</small>
      </span>
    </label>
  );
}

function Rulebook({ catalog }) {
  return (
    <section className="rulebook" id="rulebook">
      <header className="rulebook-hero">
        <div>
          <span className="eyebrow">Complete Reference</span>
          <h2>The Chass Rulebook</h2>
          <p>
            This is the detailed source of truth for every built-in piece, victory rule,
            special ability, countdown, and Chass Gambit system.
          </p>
        </div>
        <nav aria-label="Rulebook sections">
          <a href="#rulebook-pieces">Pieces</a>
          <a href="#rulebook-victory">Victory</a>
          <a href="#rulebook-abilities">Abilities</a>
          <a href="#rulebook-gambit">Gambit</a>
        </nav>
      </header>

      <article className="rulebook-section" id="rulebook-pieces">
        <div className="rulebook-section-heading">
          <span>01</span>
          <div><h3>Piece Encyclopedia</h3><p>Movement, value, and special behavior.</p></div>
        </div>
        <div className="rulebook-entry-grid">
          {catalog.pieces.map((piece) => (
            <details className="rulebook-entry" key={piece.type} open={piece.isCustom}>
              <summary>
                <span className="entry-icon">{piece.icon || piece.symbols.black}</span>
                <span><strong>{piece.name}</strong><small>{piece.isCustom ? "Chass original" : "Classic piece"}</small></span>
                <b>{piece.points ?? 0} pts</b>
              </summary>
              <p>{piece.description}</p>
              <h4>Movement</h4>
              <p>{piece.movement}</p>
              {piece.rules.length ? <ul>{piece.rules.map((rule) => <li key={rule}>{rule}</li>)}</ul> : null}
            </details>
          ))}
        </div>
      </article>

      <article className="rulebook-section" id="rulebook-victory">
        <div className="rulebook-section-heading">
          <span>02</span>
          <div><h3>Victory Rules</h3><p>Exactly what must happen before the match ends.</p></div>
        </div>
        <div className="rulebook-strip">
          {catalog.victoryModes.map((mode) => (
            <div key={mode.id}><i>{mode.icon}</i><strong>{mode.name}</strong><p>{mode.summary}</p></div>
          ))}
        </div>
      </article>

      <article className="rulebook-section" id="rulebook-abilities">
        <div className="rulebook-section-heading">
          <span>03</span>
          <div><h3>Special Ability Codex</h3><p>Each player privately locks one enabled ability.</p></div>
        </div>
        <div className="rulebook-entry-grid">
          {catalog.specialAbilities.map((ability) => (
            <details className="rulebook-entry ability-entry" key={ability.id} open>
              <summary><span className="entry-icon">{ability.icon}</span><span><strong>{ability.name}</strong><small>Player ability</small></span></summary>
              <p>{ability.summary}</p>
              <ul>{ability.details.map((detail) => <li key={detail}>{detail}</li>)}</ul>
            </details>
          ))}
        </div>
      </article>

      <article className="rulebook-section" id="rulebook-gambit">
        <div className="rulebook-section-heading">
          <span>04</span>
          <div><h3>{catalog.gambit.icon} {catalog.gambit.name}</h3><p>{catalog.gambit.summary}</p></div>
        </div>
        <div className="rulebook-gambit-copy">
          <ol>{catalog.gambit.details.map((detail) => <li key={detail}>{detail}</li>)}</ol>
          <div>
            <h4>Affinity And Command</h4>
            <p>
              The four geometric center squares are divided between White and Black. Hold both
              squares assigned to your color through the opponent&apos;s turn to earn one command
              point, up to the configured cap.
            </p>
            <p>
              One command point reinforces a Pawn, two evolves a Pawn into a Knight or Bishop,
              and three establishes a Rook in an available home square. Every command consumes
              the player&apos;s normal turn and is simulated for King safety.
            </p>
          </div>
        </div>
      </article>

      <article className="rulebook-section countdown-reference">
        <div className="rulebook-section-heading">
          <span>05</span>
          <div><h3>Turns And Countdowns</h3><p>How timed effects are counted and displayed.</p></div>
        </div>
        <p>
          A countdown decreases only when the affected player completes one of their own turns.
          Both players can see every active countdown in the game sidebar. Hovering the affected
          piece shows the same remaining time beside its movement and point information.
        </p>
      </article>
    </section>
  );
}

function CustomizationPanel({ onCreate, initialPreset = "" }) {
  const [catalog, setCatalog] = useState(null);
  const [draft, setDraft] = useState(null);
  const [selectedTool, setSelectedTool] = useState(null);
  const [creatingMode, setCreatingMode] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    getCatalog()
      .then((payload) => {
        if (cancelled) return;
        setCatalog(payload);
        setDraft(defaultDraft(payload));
      })
      .catch((requestError) => setError(requestError.message));
    return () => { cancelled = true; };
  }, []);

  const definitionMap = useMemo(
    () => new Map((catalog?.pieces || []).map((piece) => [piece.type, piece])),
    [catalog]
  );

  const applyPopularMode = (mode) => {
    const rows = mode.boardRows;
    const cols = mode.boardCols;
    setDraft((current) => ({
      ...current,
      presetId: mode.id,
      boardRows: rows,
      boardCols: cols,
      placements: classicLayout(rows, cols),
      victory: { ...current.victory, ...mode.victory },
      gambit: { ...current.gambit, ...mode.gambit },
    }));
  };

  useEffect(() => {
    if (!draft || !catalog || !initialPreset) return;
    const preset = catalog.popularModes.find((mode) => mode.id === initialPreset);
    if (preset) applyPopularMode(preset);
    // The URL preset is an initial hint, not a persistent synchronization source.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [catalog, initialPreset]);

  if (!catalog || !draft) {
    return (
      <section className="customization-panel studio-loading">
        <span className="loading-mark" />
        <h2>Opening The Chass Workshop</h2>
        <p>{error || "Loading pieces, abilities, and rule definitions..."}</p>
      </section>
    );
  }

  const changeDimensions = (nextRows, nextCols) => {
    const rows = clamp(nextRows, MIN_DIMENSION, MAX_DIMENSION);
    const cols = clamp(nextCols, MIN_DIMENSION, MAX_DIMENSION);
    setDraft((current) => ({
      ...current,
      presetId: "custom",
      boardRows: rows,
      boardCols: cols,
      placements: centeredResize(
        current.placements,
        current.boardRows,
        current.boardCols,
        rows,
        cols
      ),
    }));
  };

  const applyFormation = (formation) => {
    setDraft((current) => ({
      ...current,
      presetId: formation.id,
      boardRows: formation.rows,
      boardCols: formation.cols,
      gambit: { ...current.gambit, enabled: false },
      placements: formationLayout(formation.id, formation.rows, formation.cols),
    }));
  };

  const togglePiece = (pieceType, enabled) => {
    if (pieceType === "king" && !enabled) return;
    setDraft((current) => {
      let placements = enabled
        ? current.placements
        : current.placements.filter((piece) => piece.type !== pieceType);
      if (enabled && pieceType === "barricade" && !current.gambit.enabled) {
        const centerCandidates = [
          [Math.max(0, Math.floor(current.boardRows / 2) - 1), Math.max(0, Math.floor(current.boardCols / 2) - 1)],
          [Math.max(0, Math.floor(current.boardRows / 2) - 1), Math.floor(current.boardCols / 2)],
          [Math.floor(current.boardRows / 2), Math.max(0, Math.floor(current.boardCols / 2) - 1)],
          [Math.floor(current.boardRows / 2), Math.floor(current.boardCols / 2)],
        ];
        const center = centerCandidates.find(([row, col]) =>
          !placements.some((piece) => piece.row === row && piece.col === col)
        );
        if (center) {
          placements = [...placements, { row: center[0], col: center[1], type: "barricade", color: "neutral" }];
        }
      }
      return {
        ...current,
        enabledPieces: enabled
          ? [...new Set([...current.enabledPieces, pieceType])]
          : current.enabledPieces.filter((type) => type !== pieceType),
        placements,
      };
    });
    if (!enabled && selectedTool?.type === pieceType) setSelectedTool(null);
  };

  const placeTool = (row, col) => {
    if (draft.gambit.enabled || !selectedTool) return;
    setDraft((current) => {
      const currentPiece = current.placements.find(
        (piece) => piece.row === row && piece.col === col
      );
      if (currentPiece?.type === "barricade") {
        return current;
      }
      const withoutSquare = current.placements.filter(
        (piece) => piece.row !== row || piece.col !== col
      );
      if (selectedTool.kind === "erase") return { ...current, placements: withoutSquare };
      return {
        ...current,
        placements: [
          ...withoutSquare,
          { row, col, type: selectedTool.type, color: selectedTool.color },
        ],
      };
    });
  };

  const validationIssues = [];
  const isWholeNumberAtLeast = (value, minimum) =>
    Number.isInteger(Number(value)) && Number(value) >= minimum;
  if (!draft.enabledPieces.includes("king")) validationIssues.push("The King must remain enabled.");
  if (Object.values(draft.pointValues).some((value) => !isWholeNumberAtLeast(value, 0))) {
    validationIssues.push("Every piece value must be a whole number of zero or more.");
  }
  if (draft.victory.mode === "point_race" && !isWholeNumberAtLeast(draft.victory.targetPoints, 1)) {
    validationIssues.push("The target score must be a whole number of at least one.");
  }
  if (draft.victory.mode === "timed" && !isWholeNumberAtLeast(draft.victory.timeSeconds, 60)) {
    validationIssues.push("Each player needs at least one whole minute on the clock.");
  }
  if (
    ["point_race", "king_capture", "royal_score"].includes(draft.victory.mode) &&
    !isWholeNumberAtLeast(draft.victory.kingPoints, 0)
  ) {
    validationIssues.push("The King point value must be a whole number of zero or more.");
  }
  if (draft.specialAbilities.enabled && draft.specialAbilities.allowed.length === 0) {
    validationIssues.push("Enable at least one ability for players to choose.");
  }
  if (draft.gambit.enabled) {
    if (!isWholeNumberAtLeast(draft.gambit.budget, 0)) {
      validationIssues.push("Gambit points must be a whole number of zero or more.");
    }
    if (!isWholeNumberAtLeast(draft.gambit.maxPieces, 1)) {
      validationIssues.push("A Gambit army must allow at least one piece for its King.");
    }
    if (
      !isWholeNumberAtLeast(draft.gambit.setupRows, 1) ||
      draft.gambit.setupRows > Math.floor(draft.boardRows / 2)
    ) {
      validationIssues.push("Private setup rows must fit entirely within each player's half.");
    }
    if (!isWholeNumberAtLeast(draft.gambit.maxQueens, 0)) {
      validationIssues.push("The Queen limit must be a whole number of zero or more.");
    } else if (draft.gambit.maxQueens > draft.gambit.maxPieces) {
      validationIssues.push("The Queen limit cannot exceed the maximum army size.");
    }
    if (!isWholeNumberAtLeast(draft.gambit.commandPointCap, 0)) {
      validationIssues.push("The command point cap must be a whole number of zero or more.");
    }
    if (
      draft.enabledPieces.some(
        (type) => type !== "barricade" && !isWholeNumberAtLeast(draft.pieceCaps[type], type === "king" ? 1 : 0)
      )
    ) {
      validationIssues.push("Every Gambit piece limit must be a valid whole number.");
    }
    if (draft.gambit.setupRows * draft.boardCols < draft.gambit.maxPieces) {
      validationIssues.push("The deployment rows do not contain enough squares for the maximum army size.");
    }
  }
  if (!draft.gambit.enabled) {
    for (const color of ["white", "black"]) {
      if (draft.placements.filter((piece) => piece.type === "king" && piece.color === color).length !== 1) {
        validationIssues.push(`${title(color)} needs exactly one King for this victory rule.`);
      }
    }
  }

  const create = async (mode) => {
    if (validationIssues.length) {
      setError(validationIssues[0]);
      return;
    }
    setCreatingMode(mode);
    setError("");
    try {
      await onCreate({
        mode,
        boardRows: draft.boardRows,
        boardCols: draft.boardCols,
        configuration: {
          schemaVersion: 1,
          presetId: draft.presetId,
          enabledPieces: draft.enabledPieces,
          piecePoints: Object.fromEntries(
            draft.enabledPieces.map((type) => [type, Number(draft.pointValues[type] ?? 0)])
          ),
          initialLayout: draft.gambit.enabled ? [] : draft.placements,
          victory: draft.victory,
          specialAbilities: draft.specialAbilities,
          gambit: {
            ...draft.gambit,
            pieceCaps: Object.fromEntries(
              draft.enabledPieces.map((type) => [type, Number(draft.pieceCaps[type] ?? draft.gambit.maxPieces)])
            ),
          },
        },
      });
    } catch (requestError) {
      setError(requestError.message);
      setCreatingMode("");
    }
  };

  return (
    <section className="customization-panel configuration-studio">
      <header className="studio-hero">
        <div>
          <span className="eyebrow">Configuration Studio</span>
          <h1>Build Your Version Of Chass</h1>
          <p>
            Start simple, or combine custom pieces, a new victory condition, player abilities,
            and hidden Gambit deployment. Every setting below includes an explanation.
          </p>
        </div>
        <a className="rulebook-jump" href="#rulebook"><span>📖</span> Read The Rulebook</a>
      </header>

      <div className="studio-shell">
        <aside className="studio-preview-column">
          <ConfigurationBoard
            draft={draft}
            catalog={catalog}
            selectedTool={selectedTool}
            onSelectTool={setSelectedTool}
            onPlace={placeTool}
          />
          <div className="studio-summary-card">
            <span>Current Blueprint</span>
            <strong>{draft.boardRows}x{draft.boardCols} {draft.gambit.enabled ? "Gambit" : "Board"}</strong>
            <p>{draft.enabledPieces.length} piece types, {title(draft.victory.mode)} victory</p>
            {draft.specialAbilities.enabled ? <p>{draft.specialAbilities.allowed.length} abilities enabled</p> : null}
          </div>
        </aside>

        <div className="studio-controls">
          <section className="studio-section">
            <div className="section-heading"><span>01</span><div><h2>Popular Modes</h2><p>Load a proven starting point, then change anything.</p></div></div>
            <div className="mode-preset-grid">
              {catalog.popularModes.map((mode) => (
                <button type="button" key={mode.id} className={draft.presetId === mode.id ? "selected" : ""} onClick={() => applyPopularMode(mode)}>
                  <i>{mode.icon}</i><strong>{mode.name}</strong><small>{mode.summary}</small>
                </button>
              ))}
              {FORMATIONS.map((formation) => (
                <button type="button" key={formation.id} className={draft.presetId === formation.id ? "selected" : ""} onClick={() => applyFormation(formation)}>
                  <i>{formation.icon}</i><strong>{formation.name}</strong><small>{formation.summary}</small>
                </button>
              ))}
            </div>
          </section>

          <section className="studio-section">
            <div className="section-heading"><span>02</span><div><h2>Board Size</h2><p>Use a familiar board or choose any dimensions from 4 to 16.</p></div></div>
            <div className="dimension-presets">
              {[8, 10].map((size) => <button type="button" key={size} className={draft.boardRows === size && draft.boardCols === size ? "active" : "secondary"} onClick={() => changeDimensions(size, size)}>{size}x{size}</button>)}
              <span>Custom</span>
              <label>Rows<input type="number" min={MIN_DIMENSION} max={MAX_DIMENSION} value={draft.boardRows} onChange={(event) => changeDimensions(event.target.value, draft.boardCols)} /></label>
              <label>Columns<input type="number" min={MIN_DIMENSION} max={MAX_DIMENSION} value={draft.boardCols} onChange={(event) => changeDimensions(draft.boardRows, event.target.value)} /></label>
            </div>
          </section>

          <section className="studio-section">
            <div className="section-heading"><span>03</span><div><h2>Pieces</h2><p>Enable a piece, set a value of zero or more, then place it on the preview board.</p></div></div>
            <div className="piece-catalog-grid">
              {catalog.pieces.map((piece) => {
                const enabled = draft.enabledPieces.includes(piece.type);
                return (
                  <article key={piece.type} className={`piece-config-card ${enabled ? "enabled" : ""} ${piece.isCustom ? "custom" : ""}`}>
                    <header><span>{piece.icon || piece.symbols.black}</span><div><h3>{piece.name}</h3><small>{piece.isCustom ? "Custom Piece" : "Classic Piece"}</small></div><input aria-label={`Enable ${piece.name}`} type="checkbox" checked={enabled} disabled={piece.type === "king"} onChange={(event) => togglePiece(piece.type, event.target.checked)} /></header>
                    <p>{piece.description}</p>
                    <small className="movement-copy">{piece.movement}</small>
                    <div className="piece-config-fields">
                      <label>Point Value<input type="number" min="0" step="1" disabled={!enabled} value={draft.pointValues[piece.type]} onChange={(event) => setDraft((current) => ({ ...current, pointValues: { ...current.pointValues, [piece.type]: Math.max(0, Number(event.target.value)) } }))} /></label>
                      {draft.gambit.enabled && piece.type !== "barricade" ? <label>Army Limit<input type="number" min={piece.type === "king" ? 1 : 0} max={draft.gambit.maxPieces} disabled={!enabled || piece.type === "king"} value={draft.pieceCaps[piece.type]} onChange={(event) => setDraft((current) => ({ ...current, pieceCaps: { ...current.pieceCaps, [piece.type]: Math.max(0, Number(event.target.value)) } }))} /></label> : null}
                    </div>
                    {enabled && !draft.gambit.enabled ? (
                      <div className="piece-color-tools">
                        {piece.type === "barricade" ? <p className="fixed-piece-note">{piece.symbols.neutral || piece.icon} Spawns automatically in the board's center.</p> : ["white", "black"].map((color) => <button type="button" key={color} className={selectedTool?.type === piece.type && selectedTool?.color === color ? "active" : "secondary"} onClick={() => setSelectedTool({ kind: "piece", type: piece.type, color })}><span>{piece.symbols[color] || piece.icon}</span> {title(color)}</button>)}
                      </div>
                    ) : null}
                  </article>
                );
              })}
            </div>
          </section>

          <section className="studio-section">
            <div className="section-heading"><span>04</span><div><h2>End Game Logic</h2><p>Choose the single condition that decides when this match is over.</p></div></div>
            <div className="victory-grid">
              {catalog.victoryModes.map((mode) => <button type="button" key={mode.id} className={draft.victory.mode === mode.id ? "selected" : ""} onClick={() => setDraft((current) => ({ ...current, victory: { ...current.victory, mode: mode.id } }))}><i>{mode.icon}</i><span><strong>{mode.name}</strong><small>{mode.summary}</small></span></button>)}
            </div>
            <div className="conditional-fields">
              {draft.victory.mode === "point_race" ? <label>Target Score<input type="number" min="1" value={draft.victory.targetPoints} onChange={(event) => setDraft((current) => ({ ...current, victory: { ...current.victory, targetPoints: Math.max(1, Number(event.target.value)) } }))} /><small>The first player to this many captured-piece points wins.</small></label> : null}
              {draft.victory.mode === "timed" ? <label>Minutes Per Player<input type="number" min="1" max="1440" value={Math.round(draft.victory.timeSeconds / 60)} onChange={(event) => setDraft((current) => ({ ...current, victory: { ...current.victory, timeSeconds: Math.max(60, Number(event.target.value) * 60) } }))} /><small>The server keeps both clocks authoritative.</small></label> : null}
              {["point_race", "king_capture", "royal_score"].includes(draft.victory.mode) ? <label>King Point Value<input type="number" min="0" value={draft.victory.kingPoints} onChange={(event) => setDraft((current) => ({ ...current, victory: { ...current.victory, kingPoints: Math.max(0, Number(event.target.value)) }, pointValues: { ...current.pointValues, king: Math.max(0, Number(event.target.value)) } }))} /><small>Zero is allowed; this mode does not assume the King is priceless.</small></label> : null}
            </div>
          </section>

          <section className="studio-section ability-config-section">
            <div className="section-heading"><span>05</span><div><h2>Special Abilities</h2><p>When enabled, each player privately chooses one allowed ability before play.</p></div></div>
            <Toggle checked={draft.specialAbilities.enabled} onChange={(enabled) => setDraft((current) => ({ ...current, specialAbilities: { ...current.specialAbilities, enabled } }))} label="Enable Special Abilities" description="Choices are hidden until both players lock in." />
            {draft.specialAbilities.enabled ? <div className="ability-option-grid">{catalog.specialAbilities.map((ability) => { const enabled = draft.specialAbilities.allowed.includes(ability.id); return <button type="button" key={ability.id} className={enabled ? "selected" : ""} onClick={() => setDraft((current) => ({ ...current, specialAbilities: { ...current.specialAbilities, allowed: enabled ? current.specialAbilities.allowed.filter((id) => id !== ability.id) : [...current.specialAbilities.allowed, ability.id] } }))}><i>{ability.icon}</i><span><strong>{ability.name}</strong><small>{ability.summary}</small></span><b>{enabled ? "Enabled" : "Off"}</b></button>; })}</div> : null}
          </section>

          <section className="studio-section gambit-config-section">
            <div className="section-heading"><span>06</span><div><h2>Chass Gambit</h2><p>Turn on private army construction without giving up any choices above.</p></div></div>
            <Toggle checked={draft.gambit.enabled} onChange={(enabled) => setDraft((current) => ({ ...current, presetId: enabled ? "gambit" : "custom", gambit: { ...current.gambit, enabled } }))} label="Enable Chass Gambit" description="Players spend their full budget and edit only their closest home rows." />
            {draft.gambit.enabled ? <div className="gambit-settings-grid">
              <label>Points Available<input type="number" min="0" value={draft.gambit.budget} onChange={(event) => setDraft((current) => ({ ...current, gambit: { ...current.gambit, budget: Math.max(0, Number(event.target.value)) } }))} /><small>Every player must spend all available points. Debt is impossible.</small></label>
              <label>Maximum Pieces<input type="number" min="1" max="128" value={draft.gambit.maxPieces} onChange={(event) => setDraft((current) => ({ ...current, gambit: { ...current.gambit, maxPieces: Math.max(1, Number(event.target.value)) } }))} /><small>Default is 16, including the required King.</small></label>
              <label>Private Setup Rows<input type="number" min="1" max={Math.floor(draft.boardRows / 2)} value={draft.gambit.setupRows} onChange={(event) => setDraft((current) => ({ ...current, gambit: { ...current.gambit, setupRows: clamp(event.target.value, 1, Math.max(1, Math.floor(current.boardRows / 2))) } }))} /><small>Each player can edit only this many rows nearest them.</small></label>
              <label>Maximum Queens<input type="number" min="0" max={draft.gambit.maxPieces} value={draft.gambit.maxQueens} onChange={(event) => { const value = Math.max(0, Number(event.target.value)); setDraft((current) => ({ ...current, gambit: { ...current.gambit, maxQueens: value }, pieceCaps: { ...current.pieceCaps, queen: value } })); }} /><small>Default is two. Exactly one King remains mandatory.</small></label>
              <label>Command Point Cap<input type="number" min="0" max="20" value={draft.gambit.commandPointCap} onChange={(event) => setDraft((current) => ({ ...current, gambit: { ...current.gambit, commandPointCap: Math.max(0, Number(event.target.value)) } }))} /><small>Limits saved command points from affinity control.</small></label>
              <Toggle checked={draft.gambit.affinityEnabled} onChange={(affinityEnabled) => setDraft((current) => ({ ...current, gambit: { ...current.gambit, affinityEnabled } }))} label="Enable Affinity Squares" description="Hold both center squares of your color to earn command points." />
            </div> : null}
          </section>
        </div>
      </div>

      <section className="studio-launch-bar">
        <div><span>Ready To Launch</span><strong>{validationIssues.length ? `${validationIssues.length} setting issue${validationIssues.length === 1 ? "" : "s"}` : "Configuration valid"}</strong><small>{validationIssues[0] || "Choose local hot seat or create a private online invite."}</small></div>
        <div className="launch-actions"><button type="button" disabled={Boolean(creatingMode) || validationIssues.length > 0} onClick={() => create("local")}>{creatingMode === "local" ? "Building..." : "Start Local Game"}</button><button type="button" className="secondary" disabled={Boolean(creatingMode) || validationIssues.length > 0} onClick={() => create("online")}>{creatingMode === "online" ? "Creating Invite..." : "Create Online Game"}</button></div>
      </section>
      {error ? <p className="studio-error">{error}</p> : null}

      <Rulebook catalog={catalog} />
    </section>
  );
}

export default CustomizationPanel;
