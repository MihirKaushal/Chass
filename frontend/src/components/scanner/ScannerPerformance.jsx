import Disclosure from "../ui/Disclosure";
import ExternalLink from "../ExternalLink";
import { SCANNER_PERFORMANCE as data } from "../../scannerPerformance";
import { SCANNER_REFERENCE } from "../../scannerReference";

const percent = (count, total) => (count / total * 100).toFixed(2);
const count = (value) => value.toLocaleString("en-US");

export default function ScannerPerformance() {
  const outcomes = [
    { label: "Correct type and color", count: data.correctAll, tone: "correct" },
    { label: "Located, wrong label", count: data.located - data.correctAll, tone: "wrong" },
    { label: "Missed", count: data.missed, tone: "missed" },
  ];
  const copy = SCANNER_REFERENCE.performance;
  return (
    <Disclosure className="scanner-performance" summary="Performance & Limitations">
      <ol className="scanner-pipeline-diagram" aria-label="Recognition pipeline">
        {["Prepare photo", "Locate pieces", "Classify crops", "Assign squares", "Review & play"].map((step) => <li key={step}>{step}</li>)}
      </ol>
      <p>{copy.method}</p>
      <h3>Training data</h3>
      <p>{copy.trainingData.description}</p>
      <p>Sources: {copy.trainingData.sources.map((source, index) => <span key={source.url}>
        {index > 0 && " and "}<ExternalLink href={source.url}>{source.label}</ExternalLink>
      </span>)}
        {" "}on Roboflow Universe, both licensed under <ExternalLink href={copy.trainingData.licenseUrl}>{copy.trainingData.license}</ExternalLink>.
        {" "}{copy.trainingData.preparation}</p>
      <h3>Piece recognition progress</h3>
      <p>Correct type and color <strong>among located pieces</strong>, on the same {data.historyPhotos} Chess V2 photos
        with {count(data.historyPieces)} annotated pieces. Updated {data.recordedOn}.</p>
      <ul className="scanner-benchmark-chart">
        {data.history.map((entry) => {
          const accuracy = percent(entry.correct, entry.located);
          return <li key={entry.name}>
            <div><span>{entry.name}</span><strong>{accuracy}%</strong></div>
            <span className="scanner-benchmark-track" aria-hidden="true"><span style={{ width: `${accuracy}%` }} /></span>
            <small>{count(entry.correct)} correct / {count(entry.located)} located</small>
          </li>;
        })}
      </ul>
      <h3>Recognition across both datasets</h3>
      <p>Correctly located, typed, and colored pieces <strong>out of all real pieces</strong>, including misses.</p>
      <div className="scanner-source-table-wrap">
        <table className="scanner-source-table">
          <thead><tr><th scope="col">Test source</th><th scope="col">Previous model</th><th scope="col">Combined-data model</th></tr></thead>
          <tbody>{data.sources.map((source) => <tr key={source.key}>
            <th scope="row">{source.name}<small>{source.photos} photos / {count(source.pieces)} pieces</small></th>
            <td>{percent(source.previous, source.pieces)}%</td>
            <td><strong>{percent(source.correct, source.pieces)}%</strong></td>
          </tr>)}</tbody>
        </table>
      </div>
      <p>Equal-source F1: <strong>{percent(data.sourceBalancedF1, 1)}%</strong>. F1 balances misses, wrong labels, and extra predictions;
        weighting each source equally prevents the larger collection from hiding failures on the smaller one.
        An equal-budget single-source control had nearly identical pooled recall; the gain is broader source coverage.</p>
      <h3>What happens to all real pieces?</h3>
      <p>Current model on both test collections: {data.photos} photos and {count(data.pieces)} annotated pieces.</p>
      <figure className="scanner-outcome-chart">
        <div className="scanner-outcome-track" aria-hidden="true">
          {outcomes.map((outcome) => <span key={outcome.tone} className={`scanner-outcome-${outcome.tone}`}
            style={{ width: `${outcome.count / data.pieces * 100}%` }} />)}
        </div>
        <figcaption>
          <ul className="scanner-outcome-legend">
            {outcomes.map((outcome) => <li key={outcome.tone}>
              <span className={`scanner-outcome-swatch scanner-outcome-${outcome.tone}`} aria-hidden="true" />
              <span>{outcome.label}</span>
              <strong>{percent(outcome.count, data.pieces)}% <small>({count(outcome.count)})</small></strong>
            </li>)}
          </ul>
        </figcaption>
      </figure>
      <p>The detector locates <strong>{percent(data.located, data.pieces)}%</strong> of real pieces.
        Once located, <strong>{percent(data.correctAll, data.located)}%</strong> have the right type and color.
        Including misses, <strong>{percent(data.correctAll, data.pieces)}%</strong> of all real pieces are correctly located and labelled.
        There are also <strong>{data.extra} extra detections</strong> with no matching real piece; these sit outside the chart's {count(data.pieces)} real-piece total.</p>
      <h3>How we measure it</h3>
      <p>{copy.evaluation}</p>
      <p><strong>This is not whole-board accuracy.</strong> Square accuracy and completely correct boards are not yet measured.
        That requires independently checked labels for all 64 squares, including empty ones.
        Strong piece recognition can still produce a board that needs corrections.</p>
      <h3>What to check</h3>
      <ul>
        <li>Empty squares may hide missed pieces, especially in crowded positions.</li>
        <li>Tall or tilted pieces can be assigned to a neighboring square.</li>
        <li>Unfamiliar Kings, Queens, and Bishops may be confused. Review suggestions against the photo.</li>
      </ul>
      <p>{copy.uncertainty}</p>
      <h3>Speed and privacy</h3>
      <p>{copy.timing}</p>
      <p>{copy.privacy}</p>
      <ExternalLink href="https://github.com/MihirKaushal/Chass/blob/main/scanner/ml/ACCURACY_TRACKER.md">Benchmark definitions and experiment history</ExternalLink>
    </Disclosure>
  );
}
