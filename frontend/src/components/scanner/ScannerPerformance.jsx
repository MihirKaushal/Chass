import { useState } from "react";

import Disclosure from "../ui/Disclosure";
import ExternalLink from "../ExternalLink";
import { SCANNER_PERFORMANCE as data } from "../../scannerPerformance";
import { SCANNER_REFERENCE } from "../../scannerReference";

const percent = (count, total) => (count / total * 100).toFixed(2);
const count = (value) => value.toLocaleString("en-US");
const versionDescriptions = {
  "Detector only": "One model finds pieces and predicts their type and color.",
  "Crop classifier": "A second model examines a close-up of each detected piece to identify it.",
  "King-focused update": "Refinements target missed pieces and identification errors, especially Kings.",
  "Combined-data update": "Both models are trained further using two photo collections instead of one.",
};

export default function ScannerPerformance() {
  const [open, setOpen] = useState(true);
  const outcomes = [
    { label: "Correct type and color", count: data.correctAll, tone: "correct" },
    { label: "Located, wrong label", count: data.located - data.correctAll, tone: "wrong" },
    { label: "Missed", count: data.missed, tone: "missed" },
  ];
  const copy = SCANNER_REFERENCE.performance;
  return (
    <Disclosure className="scanner-performance" summary="Performance & Limitations"
      open={open} onToggle={(event) => setOpen(event.currentTarget.open)}>
      <ol className="scanner-pipeline-diagram" aria-label="Recognition pipeline">
        {["Prepare photo", "Locate pieces", "Classify crops", "Assign squares", "Review & play"].map((step) => <li key={step}>{step}</li>)}
      </ol>
      <p>{copy.method}</p>
      <p><strong>Finding is not the same as identifying.</strong> A piece is located when the scanner finds it in the photo;
        it is correctly identified when both its type and color match, such as a white Knight.
        Annotated pieces are the labeled real pieces used to check the model, before user corrections.</p>
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
      <p>These are successive model versions, not separate scores for the current model.
        Missed pieces and extra detections are excluded from these percentages.</p>
      <ul className="scanner-benchmark-chart">
        {data.history.map((entry) => {
          const accuracy = percent(entry.correct, entry.located);
          return <li key={entry.name}>
            <div><span>{entry.name}</span><strong>{accuracy}%</strong></div>
            <small>{versionDescriptions[entry.name]}</small>
            <span className="scanner-benchmark-track" aria-hidden="true"><span style={{ width: `${accuracy}%` }} /></span>
            <small>{count(entry.correct)} correct / {count(entry.located)} located</small>
          </li>;
        })}
      </ul>
      <h3>Recognition across both datasets</h3>
      <p>Correctly located, typed, and colored pieces <strong>out of all real pieces</strong>, including misses.
        Unlike the chart above, missing a piece counts as a failure. Each dataset is measured separately.</p>
      <p>For example, finding 8 of 10 pieces and identifying 7 correctly scores 87.5% among located pieces,
        but only 70% across all real pieces. This is why the percentages below are lower.</p>
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
      <p>Previous model means the King-focused version above; combined-data model means the latest version.
        The main improvement is recognizing pieces in the second photo collection, while keeping similar results on the first.</p>
      <p>Equal-source F1: <strong>{percent(data.sourceBalancedF1, 1)}%</strong>. F1 balances misses, wrong labels, and extra predictions;
        weighting each source equally prevents the larger collection from hiding failures on the smaller one.
        A separate comparison trained on just one collection for the same amount of training had almost the same overall
        correct-piece rate; using both collections mainly improved performance on the smaller source.</p>
      <h3>What happens to all real pieces?</h3>
      <p>Current model on both test collections: {data.photos} photos and {count(data.pieces)} annotated pieces.
        This combines both datasets and splits every real piece into correct, mislabeled, or missed; the three groups total 100%.</p>
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
