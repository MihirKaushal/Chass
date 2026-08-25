import { evaluationLabel, outcomePercentages } from "../matchPredictor";
import Button from "./ui/Button";

function factorValue(value) {
  const numeric = Number(value);
  return Number.isInteger(numeric) ? numeric : numeric.toFixed(1);
}

function MatchPredictor({ analysis, moveCount = 0, refreshing = false, onRetry }) {
  const unavailable = analysis?.status === "unavailable";
  const ready = analysis?.status === "ready";
  const percentages = outcomePercentages(analysis?.outcome, moveCount);
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
        <b className={`predictor-evaluation${unavailable ? " is-unavailable" : ""}`}>
          {loading ? <i aria-hidden="true" /> : null}
          {unavailable ? "Unavailable" : loading ? "Updating" : evaluationLabel(analysis, moveCount)}
        </b>
      </header>

      {unavailable ? (
        <div className="match-predictor-unavailable">
          <p className="match-predictor-message">{analysis.reason}</p>
          <Button
            onClick={onRetry}
            loading={refreshing}
            loadingLabel="Retrying Analysis..."
          >
            Retry Analysis
          </Button>
        </div>
      ) : percentages ? (
        <>
          <div
            className="outcome-track"
            role="img"
            aria-label={`White ${percentages.white} percent, Black ${percentages.black} percent`}
          >
            <span className="outcome-white" style={{ width: `${percentages.white}%` }} />
            <span className="outcome-black" style={{ width: `${percentages.black}%` }} />
          </div>
          <div className="outcome-labels">
            <span><i className="white" />White<strong>{percentages.white}%</strong></span>
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
          <p className="predictor-engine-version">
            Engine version: <strong>{analysis.engineVersion || "Stockfish"}</strong>
          </p>
        </details>
      ) : null}
    </section>
  );
}

export default MatchPredictor;
