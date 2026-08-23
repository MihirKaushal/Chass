import { outcomePercentages } from "../matchPredictor";

function evaluationLabel(analysis) {
  const evaluation = analysis?.evaluation;
  if (!evaluation) return analysis?.status === "ready" && analysis?.outcome
    ? "Final result"
    : "Position pending";
  if (evaluation.mateIn != null) {
    const winner = evaluation.mateIn > 0 ? "White" : "Black";
    return `${winner} mates in ${Math.abs(evaluation.mateIn)}`;
  }
  if (evaluation.centipawns == null) return "Balanced position";
  const pawns = evaluation.centipawns / 100;
  if (Math.abs(pawns) < 0.005) return "Even";
  return `${pawns > 0 ? "+" : ""}${pawns.toFixed(2)} ${pawns > 0 ? "White" : "Black"}`;
}

function factorValue(value) {
  const numeric = Number(value);
  return Number.isInteger(numeric) ? numeric : numeric.toFixed(1);
}

function readableMove(move) {
  const match = /^([a-h][1-8])([a-h][1-8])([qrbn])?$/.exec(move);
  if (!match) return move;
  return `${match[1]}-${match[2]}${match[3] ? `=${match[3].toUpperCase()}` : ""}`;
}

function MatchPredictor({ analysis, refreshing = false }) {
  const unavailable = analysis?.status === "unavailable";
  const ready = analysis?.status === "ready";
  const percentages = outcomePercentages(analysis?.outcome);
  const loading = refreshing || !analysis || analysis.status === "analyzing";

  return (
    <section
      className={`panel-section match-predictor ${loading ? "is-analyzing" : ""}`}
      aria-live="polite"
    >
      <header className="match-predictor-heading">
        <span>
          <small>Classic Analysis</small>
          <h3>Match Predictor</h3>
        </span>
        <b className={unavailable ? "is-unavailable" : ""}>
          {loading ? <i aria-hidden="true" /> : null}
          {unavailable ? "Unavailable" : loading ? "Updating" : evaluationLabel(analysis)}
        </b>
      </header>

      {unavailable ? (
        <p className="match-predictor-message">{analysis.reason}</p>
      ) : percentages ? (
        <>
          <div
            className="outcome-track"
            role="img"
            aria-label={`White win ${percentages.white} percent, draw ${percentages.draw} percent, Black win ${percentages.black} percent`}
          >
            <span className="outcome-white" style={{ width: `${percentages.white}%` }} />
            <span className="outcome-draw" style={{ width: `${percentages.draw}%` }} />
            <span className="outcome-black" style={{ width: `${percentages.black}%` }} />
          </div>
          <div className="outcome-labels">
            <span><i className="white" />White<strong>{percentages.white}%</strong></span>
            <span><i className="draw" />Draw<strong>{percentages.draw}%</strong></span>
            <span><i className="black" />Black<strong>{percentages.black}%</strong></span>
          </div>
        </>
      ) : (
        <div className="predictor-loading-frame" aria-live="polite">
          <span /><span /><span />
          <p>{analysis?.reason || "Preparing the first position estimate..."}</p>
        </div>
      )}

      {ready && analysis.factors?.length ? (
        <details className="predictor-factors">
          <summary><span>Position Factors</span><small>How the board compares</small></summary>
          <div className="predictor-factor-list">
            {analysis.factors.map((factor) => (
              <article key={factor.id} className={`factor-${factor.advantage}`}>
                <header><strong>{factor.label}</strong><span>{factor.advantage === "balanced" ? "Even" : `${factor.advantage === "white" ? "White" : "Black"} edge`}</span></header>
                <p>{factor.summary}</p>
                <small>W {factorValue(factor.whiteValue)} <i /> B {factorValue(factor.blackValue)}</small>
              </article>
            ))}
          </div>
          {analysis.principalVariation?.length ? (
            <p className="predictor-line"><b>Engine line</b>{analysis.principalVariation.map(readableMove).join("  ")}</p>
          ) : null}
        </details>
      ) : null}

      <footer>
        <span>{analysis?.engineVersion || "Stockfish NNUE"}</span>
        {analysis?.depth ? <span>Depth {analysis.depth}</span> : null}
        {analysis?.elapsedMs != null ? <span>{analysis.elapsedMs} ms</span> : null}
      </footer>
      <p className="predictor-disclaimer">Position-based engine estimate, not a guaranteed result.</p>
    </section>
  );
}

export default MatchPredictor;
