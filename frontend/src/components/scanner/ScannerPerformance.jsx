import Disclosure from "../ui/Disclosure";
import ExternalLink from "../ExternalLink";
import { SCANNER_PERFORMANCE as data } from "../../scannerPerformance";
import { SCANNER_REFERENCE } from "../../scannerReference";

const percent = (count, total) => (count / total * 100).toFixed(2);
const count = (value) => value.toLocaleString("en-US");

export default function ScannerPerformance() {
  const latest = data.history.at(-1);
  const outcomes = [
    { label: "Correct type and color", count: data.correctAll, tone: "correct" },
    { label: "Located, wrong label", count: latest.located - data.correctAll, tone: "wrong" },
    { label: "Missed", count: data.missed, tone: "missed" },
  ];
  const copy = SCANNER_REFERENCE.performance;
  return (
    <Disclosure className="scanner-performance" summary="Performance & Limitations">
      <ol className="scanner-pipeline-diagram" aria-label="Recognition pipeline">
        {["Prepare photo", "Locate pieces", "Classify crops", "Assign squares", "Review & play"].map((step) => <li key={step}>{step}</li>)}
      </ol>
      <p>{copy.method}</p>
      <h3>Piece recognition progress</h3>
      <p>Correct type and color <strong>among located pieces</strong>. Recorded {data.recordedOn} on {data.photos} photos
        with {count(data.pieces)} annotated pieces.</p>
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
      <h3>What happens to all real pieces?</h3>
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
      <p>The detector locates <strong>{percent(latest.located, data.pieces)}%</strong> of real pieces.
        Once located, <strong>{percent(latest.correct, latest.located)}%</strong> have the right type and color.
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
