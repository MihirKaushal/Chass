import Disclosure from "../ui/Disclosure";
import { SCANNER_PERFORMANCE as data } from "../../scannerPerformance";

export default function ScannerPerformance() {
  return (
    <Disclosure className="scanner-performance" summary="Performance & Limitations">
      <ol className="scanner-pipeline-diagram" aria-label="Recognition pipeline">
        {["Prepare photo", "Locate pieces", "Classify crops", "Assign squares", "Review & play"].map((step) => <li key={step}>{step}</li>)}
      </ol>
      <h3>Piece recognition progress</h3>
      <p>Correct type and color among located pieces. Recorded {data.recordedOn} on {data.photos} photos
        with {data.pieces.toLocaleString("en-US")} annotated pieces.</p>
      <ul className="scanner-benchmark-chart">
        {data.history.map((entry) => {
          const percent = entry.correct / entry.located * 100;
          return <li key={entry.name}>
            <div><span>{entry.name}</span><strong>{percent.toFixed(2)}%</strong></div>
            <span className="scanner-benchmark-track" aria-hidden="true"><span style={{ width: `${percent}%` }} /></span>
          </li>;
        })}
      </ul>
      <p><strong>This is not whole-board accuracy.</strong> Including missed pieces, the current pipeline
        correctly locates and labels {(data.correctAll / data.pieces * 100).toFixed(2)}% of annotated pieces.
        It misses {data.missed} pieces and produces {data.extra} unmatched extra detections on this benchmark.</p>
      <p>Square accuracy and completely correct boards are not yet measured. The same test collection
        has been reused during development; it does not establish performance on unfamiliar chess sets.</p>
      <h3>What to check</h3>
      <ul>
        <li>Empty squares may hide missed pieces, especially in crowded positions.</li>
        <li>Tall or tilted pieces can be assigned to a neighboring square.</li>
        <li>Unfamiliar Kings, Queens, and Bishops may be confused. Review suggestions against the photo.</li>
      </ul>
      <p>Scan Details separates recognition from connection and model-loading time. Device and server
        timings are not directly comparable. Cold starts can still add a wait.</p>
      <a href="https://github.com/MihirKaushal/Chass/blob/main/scanner/ml/ACCURACY_TRACKER.md">Benchmark definitions and experiment history</a>
    </Disclosure>
  );
}
