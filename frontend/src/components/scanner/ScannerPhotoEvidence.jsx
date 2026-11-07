import { detectionRects, squareName } from "../../scannerInsights";

export function ScannerPhotoEvidence({ src, scan, selectedSquare, showDetections = false }) {
  return (
    <svg className="scanner-photo-evidence" viewBox="0 0 8 8" role="img"
      aria-label={selectedSquare ? `Prepared photo with ${squareName(selectedSquare)} highlighted` : "Prepared board photo"}>
      <image href={src} width="8" height="8" preserveAspectRatio="none" />
      {showDetections ? detectionRects(scan).map((rect) => (
        <rect key={rect.index} x={rect.x} y={rect.y} width={rect.width} height={rect.height}
          className="scanner-detection-outline" />
      )) : null}
      {selectedSquare ? <rect x={selectedSquare.col} y={selectedSquare.row} width="1" height="1"
        className="scanner-photo-selection" /> : null}
    </svg>
  );
}

export function ScannerSquareCrop({ src, square }) {
  if (!src || !square) return null;
  return (
    <figure className="scanner-square-crop">
      <svg viewBox={`${square.col} ${square.row} 1 1`} role="img" aria-label={`Photo crop of ${squareName(square)}`}>
        <image href={src} width="8" height="8" preserveAspectRatio="none" />
      </svg>
      <figcaption>{squareName(square)} in your photo</figcaption>
    </figure>
  );
}
