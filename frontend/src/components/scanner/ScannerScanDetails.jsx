import Disclosure from "../ui/Disclosure";
import { formatDuration, scanCorrections, scanSummary } from "../../scannerInsights";

export default function ScannerScanDetails({ scan, board, reviewSquares, confirmed,
  showDetections, onShowDetections, reviewMs }) {
  const summary = scanSummary(scan, board);
  const corrections = scanCorrections(scan, board);
  const browser = scan.runtime === "browser-onnx";
  const timing = scan.clientTimings || {};
  const pieceName = (label) => label ? label.replace("-", " ") : "empty";
  return (
    <section className="scanner-scan-summary" aria-label="Scan result">
      <div className="scanner-summary-line" aria-live="polite">
        <strong>{summary.detected} pieces detected</strong>
        <span>{reviewSquares.length} squares to review</span>
        <span>{summary.corrected} {summary.corrected === 1 ? "square" : "squares"} corrected</span>
        {confirmed ? <span className="scanner-reviewed-label">Review complete</span> : null}
      </div>
      <Disclosure className="scanner-label-export scanner-scan-details" summary="Scan Details">
        <dl className="scanner-detail-grid">
          <div><dt>Processed</dt><dd>{browser ? "On your device" : "On the server"}</dd></div>
          <div><dt>Total wait</dt><dd>{formatDuration(timing.totalMs)}</dd></div>
          <div><dt>Recognition</dt><dd>{formatDuration(scan.inferenceMs)}</dd></div>
          {browser ? <>
            <div><dt>Model fetch / cache</dt><dd>{formatDuration(scan.timings?.modelFetchMs)}</dd></div>
            <div><dt>Runtime setup</dt><dd>{formatDuration(scan.timings?.runtimeSetupMs)}</dd></div>
          </> : <>
            <div><dt>Connection / startup wait</dt><dd>{formatDuration(timing.connectionMs)}</dd></div>
            <div><dt>Scan request (includes recognition)</dt><dd>{formatDuration(timing.requestMs)}</dd></div>
          </>}
          {timing.fallbackMs != null ? <div><dt>On-device attempt before fallback</dt><dd>{formatDuration(timing.fallbackMs)}</dd></div> : null}
          {confirmed ? <div><dt>Active review time</dt><dd>{formatDuration(reviewMs)}</dd></div> : null}
          <div><dt>Model version</dt><dd>SSDLite + ResNet18
            {Object.entries(scan.modelSha256 || {}).map(([name, hash]) => (
              <small key={name} title={hash}>{name}: {String(hash).slice(0, 12)}</small>
            ))}
          </dd></div>
        </dl>
        <label className="scanner-runtime-toggle">
          <input type="checkbox" checked={showDetections} onChange={(event) => onShowDetections(event.target.checked)} />
          Show detected piece outlines on photo
        </label>
        <p>Outlines show detections, not verified piece bases. Scores rank suggestions; they are not measured probabilities of correctness.</p>
        {corrections.length ? <ul className="scanner-correction-list" aria-label="Changes from recognition">
          {corrections.map((change) => <li key={change.square}>
            <strong>{change.square}</strong>: {pieceName(change.before)} &rarr; {pieceName(change.after)}
          </li>)}
        </ul> : <p>No changes from the original recognition result.</p>}
      </Disclosure>
    </section>
  );
}
