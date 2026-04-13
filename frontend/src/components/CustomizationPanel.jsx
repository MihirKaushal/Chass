import { useEffect, useMemo, useState } from "react";

function CustomizationPanel({
  game,
  onApplyBasic,
  onApplyPieceCustomization,
  onApplyRuleBuilder,
  onApplyRaw,
  onCreateNewGame,
}) {
  const [boardSize, setBoardSize] = useState(game.boardSize);
  const [ruleToggles, setRuleToggles] = useState({});
  const [alignedEnemyCount, setAlignedEnemyCount] = useState(2);
  const [rawRules, setRawRules] = useState("[]");

  const [selectedPieceType, setSelectedPieceType] = useState("");
  const [piecePoints, setPiecePoints] = useState("");
  const [piecePatternsJson, setPiecePatternsJson] = useState("[]");
  const [pieceAttributesJson, setPieceAttributesJson] = useState("{}");

  const [localError, setLocalError] = useState("");

  const basicRuleSet = useMemo(
    () => game.rules.filter((rule) => rule.canDisable),
    [game.rules]
  );

  const selectedPieceDefinition = useMemo(
    () =>
      game.pieceDefinitions.find((definition) => definition.type === selectedPieceType) || null,
    [game.pieceDefinitions, selectedPieceType]
  );

  useEffect(() => {
    setBoardSize(game.boardSize);
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

    const defaultPiece = game.pieceDefinitions[0];
    if (defaultPiece) {
      setSelectedPieceType(defaultPiece.type);
      setPiecePoints(defaultPiece.points ?? "");
      setPiecePatternsJson(JSON.stringify(defaultPiece.patterns, null, 2));
      setPieceAttributesJson(JSON.stringify(defaultPiece.customAttributes || {}, null, 2));
    }
  }, [game]);

  useEffect(() => {
    if (!selectedPieceDefinition) {
      return;
    }
    setPiecePoints(selectedPieceDefinition.points ?? "");
    setPiecePatternsJson(JSON.stringify(selectedPieceDefinition.patterns, null, 2));
    setPieceAttributesJson(
      JSON.stringify(selectedPieceDefinition.customAttributes || {}, null, 2)
    );
  }, [selectedPieceDefinition]);

  const applyBasicChanges = () => {
    setLocalError("");
    const patches = basicRuleSet.map((rule) => ({
      id: rule.id,
      enabled: Boolean(ruleToggles[rule.id]),
      params: rule.params,
    }));

    onApplyBasic({ boardSize, patches });
  };

  const applyPieceChanges = () => {
    setLocalError("");

    if (!selectedPieceType) {
      setLocalError("Choose a piece to edit.");
      return;
    }

    let parsedPatterns;
    let parsedAttributes;

    try {
      parsedPatterns = JSON.parse(piecePatternsJson);
      if (!Array.isArray(parsedPatterns)) {
        setLocalError("Movement patterns must be a JSON array.");
        return;
      }
    } catch {
      setLocalError("Movement patterns must be valid JSON.");
      return;
    }

    try {
      parsedAttributes = JSON.parse(pieceAttributesJson);
      if (typeof parsedAttributes !== "object" || Array.isArray(parsedAttributes)) {
        setLocalError("Custom attributes must be a JSON object.");
        return;
      }
    } catch {
      setLocalError("Custom attributes must be valid JSON.");
      return;
    }

    const normalizedPoints = piecePoints === "" ? null : Number(piecePoints);
    if (normalizedPoints !== null && Number.isNaN(normalizedPoints)) {
      setLocalError("Points must be a number or blank.");
      return;
    }

    onApplyPieceCustomization({
      pieces: [
        {
          type: selectedPieceType,
          points: normalizedPoints,
          patterns: parsedPatterns,
          customAttributes: parsedAttributes,
          isCustom: true,
        },
      ],
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
      <p>Start simple, then expand into piece behavior and advanced rules.</p>

      <div className="customization-card">
        <h3>Layer 1: Basic Setup</h3>
        <label className="field-label">
          Board Size
          <input
            type="number"
            min="4"
            max="16"
            value={boardSize}
            onChange={(event) => setBoardSize(Number(event.target.value))}
          />
        </label>

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
          <button type="button" className="secondary" onClick={() => onCreateNewGame(boardSize)}>
            Create New Game
          </button>
        </div>
      </div>

      <details className="customization-card" open>
        <summary>Layer 2: Piece Attributes</summary>
        <div className="layer-grid two-col">
          <label className="field-label">
            Piece Type
            <select
              value={selectedPieceType}
              onChange={(event) => setSelectedPieceType(event.target.value)}
            >
              {game.pieceDefinitions.map((definition) => (
                <option key={definition.type} value={definition.type}>
                  {definition.displayName} ({definition.type})
                </option>
              ))}
            </select>
          </label>

          <label className="field-label">
            Points
            <input
              type="number"
              value={piecePoints}
              onChange={(event) => setPiecePoints(event.target.value)}
              placeholder="Leave blank for no points"
            />
          </label>
        </div>

        <label className="field-label full-width">
          Movement Patterns (JSON Array)
          <textarea
            className="raw-editor"
            value={piecePatternsJson}
            onChange={(event) => setPiecePatternsJson(event.target.value)}
            rows={9}
          />
        </label>

        <label className="field-label full-width">
          Custom Attributes (JSON Object)
          <textarea
            className="raw-editor"
            value={pieceAttributesJson}
            onChange={(event) => setPieceAttributesJson(event.target.value)}
            rows={5}
          />
        </label>

        <button type="button" onClick={applyPieceChanges}>
          Apply Piece Changes
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
