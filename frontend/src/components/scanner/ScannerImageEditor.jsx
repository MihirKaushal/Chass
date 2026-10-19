import { useEffect, useId, useMemo, useRef, useState } from "react";

import {
  defaultScannerCrop,
  prepareScannerPhoto,
  projectScannerPoint,
  rotateScannerEdits,
  scannerCropIssue,
  scannerCropResolution,
  scannerPerspectiveMatrix,
  scannerPointerPosition,
  scannerRotationGeometry,
  translateScannerCrop,
} from "../../scannerImage";
import Button from "../ui/Button";
import Dialog from "../ui/Dialog";
import ScannerIcon from "./ScannerIcon";

const CORNER_NAMES = ["Top left", "Top right", "Bottom right", "Bottom left"];
const bounded = (value) => Math.max(0, Math.min(1, value));

function ScannerImageEditor({ sourceFile, initialEdits, onApply, onClose }) {
  const angleId = useId();
  const svgRef = useRef(null);
  const draggingRef = useRef(null);
  const activeRef = useRef(false);
  const savingRef = useRef(false);
  const [photo, setPhoto] = useState(null);
  const [{ rotation, corners }, setImageEdits] = useState(() => ({
    rotation: initialEdits?.rotation ?? 0,
    corners: initialEdits?.corners?.map((point) => ({ ...point })) ?? null,
  }));
  const [selectedCorner, setSelectedCorner] = useState(0);
  const [showGrid, setShowGrid] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const setCorners = (update) => {
    setImageEdits((current) => ({
      ...current,
      corners: typeof update === "function" ? update(current.corners) : update,
    }));
  };

  useEffect(() => {
    activeRef.current = true;
    const url = URL.createObjectURL(sourceFile);
    const image = new Image();
    image.onload = () => {
      if (!activeRef.current) return;
      if (!image.naturalWidth || !image.naturalHeight) {
        setError(
          "This image has no readable dimensions. Choose another photo.",
        );
        return;
      }
      const geometry = scannerRotationGeometry(
        image.naturalWidth,
        image.naturalHeight,
        initialEdits?.rotation ?? 0,
      );
      setPhoto({ image, url });
      setCorners((current) => current ?? defaultScannerCrop(geometry));
    };
    image.onerror = () => {
      if (activeRef.current)
        setError(
          "This photo could not be opened. Choose another JPG, PNG, or WebP image.",
        );
    };
    image.src = url;
    return () => {
      activeRef.current = false;
      image.onload = null;
      image.onerror = null;
      URL.revokeObjectURL(url);
    };
  }, [sourceFile, initialEdits]);

  const geometry = useMemo(
    () =>
      photo
        ? scannerRotationGeometry(
            photo.image.naturalWidth,
            photo.image.naturalHeight,
            rotation,
          )
        : null,
    [photo, rotation],
  );
  const cropIssue =
    geometry && corners ? scannerCropIssue(corners, geometry) : null;
  const resolution =
    geometry && corners && !cropIssue
      ? scannerCropResolution(corners, geometry)
      : 0;
  const gridLines = useMemo(() => {
    if (!corners || cropIssue || !showGrid) return [];
    const matrix = scannerPerspectiveMatrix(corners);
    return Array.from({ length: 7 }, (_, index) => {
      const step = (index + 1) / 8;
      return [
        [
          projectScannerPoint(matrix, step, 0),
          projectScannerPoint(matrix, step, 1),
        ],
        [
          projectScannerPoint(matrix, 0, step),
          projectScannerPoint(matrix, 1, step),
        ],
      ];
    }).flat();
  }, [corners, cropIssue, showGrid]);

  const updateCorner = (index, point) => {
    setCorners((current) =>
      current.map((corner, position) =>
        position === index
          ? { x: bounded(point.x), y: bounded(point.y) }
          : corner,
      ),
    );
    setSelectedCorner(index);
    setError("");
  };

  const pointerPoint = (event) =>
    scannerPointerPosition(
      event.clientX,
      event.clientY,
      svgRef.current.getBoundingClientRect(),
      geometry,
    );
  const startDrag = (event, index) => {
    if (saving) return;
    const point = pointerPoint(event);
    if (!point) return;
    event.preventDefault();
    event.currentTarget.focus();
    event.currentTarget.setPointerCapture(event.pointerId);
    draggingRef.current = {
      pointerId: event.pointerId,
      index,
      start: point,
      corners,
    };
    if (index !== null) setSelectedCorner(index);
  };
  const drag = (event) => {
    const dragging = draggingRef.current;
    if (!dragging || dragging.pointerId !== event.pointerId) return;
    const point = pointerPoint(event);
    if (!point) return;
    if (dragging.index === null) {
      setCorners(
        translateScannerCrop(
          dragging.corners,
          point.x - dragging.start.x,
          point.y - dragging.start.y,
        ),
      );
      setError("");
    } else updateCorner(dragging.index, point);
  };
  const nudge = (event, index) => {
    const directions = {
      ArrowLeft: [-1, 0],
      ArrowRight: [1, 0],
      ArrowUp: [0, -1],
      ArrowDown: [0, 1],
    };
    if (!directions[event.key] || saving) return;
    event.preventDefault();
    const [dx, dy] = directions[event.key];
    const amount = event.shiftKey ? 0.01 : 0.001;
    if (index === null)
      setCorners((current) =>
        translateScannerCrop(current, dx * amount, dy * amount),
      );
    else
      updateCorner(index, {
        x: corners[index].x + dx * amount,
        y: corners[index].y + dy * amount,
      });
  };
  const changeRotation = (value) => {
    if (!photo || saving) return;
    setImageEdits((current) =>
      rotateScannerEdits(
        current,
        photo.image.naturalWidth,
        photo.image.naturalHeight,
        typeof value === "function" ? value(current.rotation) : value,
      ),
    );
    setError("");
  };
  const quarterTurn = (amount) =>
    changeRotation(
      (current) => ((((current + amount + 180) % 360) + 360) % 360) - 180,
    );
  const reset = () => {
    if (photo)
      setImageEdits({
        rotation: 0,
        corners: defaultScannerCrop(
          scannerRotationGeometry(
            photo.image.naturalWidth,
            photo.image.naturalHeight,
            0,
          ),
        ),
      });
    setSelectedCorner(0);
    setError("");
  };
  const close = () => {
    activeRef.current = false;
    onClose();
  };
  const apply = async () => {
    if (!photo || cropIssue || savingRef.current) return;
    savingRef.current = true;
    setSaving(true);
    setError("");
    const edits = { rotation, corners: corners.map((point) => ({ ...point })) };
    try {
      await new Promise((resolve) => window.setTimeout(resolve, 0));
      if (!activeRef.current) return;
      const prepared = await prepareScannerPhoto(
        photo.image,
        sourceFile,
        edits,
      );
      if (activeRef.current) onApply(prepared, edits);
    } catch (applyError) {
      if (activeRef.current)
        setError(
          applyError.message ||
            "The image could not be prepared. Please try again.",
        );
    } finally {
      savingRef.current = false;
      if (activeRef.current) setSaving(false);
    }
  };

  const pointList =
    geometry && corners
      ? corners
          .map(
            (point) =>
              `${point.x * geometry.width},${point.y * geometry.height}`,
          )
          .join(" ")
      : "";
  const handleRadius = geometry
    ? Math.max(geometry.width, geometry.height) * 0.021
    : 0;
  const feedbackError = (photo && error) || cropIssue;

  return (
    <Dialog
      open
      className="scanner-image-editor"
      title="Prepare your board photo"
      eyebrow="Rotate & crop"
      description="Rotate the board upright, then place each corner on the outer edge of the playing grid. Keep every square and piece visible."
      onClose={close}
      closeLabel="Close photo editor"
      actions={
        <>
          <Button variant="secondary" onClick={close}>
            Cancel
          </Button>
          <Button
            disabled={!photo || Boolean(cropIssue)}
            loading={saving}
            loadingLabel="Applying Edits..."
            onClick={apply}
          >
            <ScannerIcon name="check" />
            Apply Photo Edits
          </Button>
        </>
      }
    >
      <div className="scanner-editor-layout">
        <div className="scanner-editor-visual">
          <div className="scanner-editor-stage">
            {photo && geometry && corners ? (
              <svg
                ref={svgRef}
                viewBox={`0 0 ${geometry.width} ${geometry.height}`}
                preserveAspectRatio="xMidYMid meet"
                className="scanner-crop-surface"
                aria-label="Board crop area"
                onPointerMove={drag}
                onPointerUp={() => {
                  draggingRef.current = null;
                }}
                onPointerCancel={() => {
                  draggingRef.current = null;
                }}
                onLostPointerCapture={() => {
                  draggingRef.current = null;
                }}
              >
                <image
                  href={photo.url}
                  width={geometry.sourceWidth}
                  height={geometry.sourceHeight}
                  transform={`translate(${geometry.width / 2} ${geometry.height / 2}) rotate(${rotation}) translate(${-geometry.sourceWidth / 2} ${-geometry.sourceHeight / 2})`}
                />
                <path
                  className="scanner-crop-mask"
                  fillRule="evenodd"
                  d={`M0 0H${geometry.width}V${geometry.height}H0Z M${pointList.replaceAll(" ", " L")}Z`}
                />
                <polygon
                  className={`scanner-crop-outline${cropIssue ? " is-invalid" : ""}`}
                  points={pointList}
                  role="button"
                  tabIndex={saving ? -1 : 0}
                  aria-label="Move entire crop. Use arrow keys to adjust."
                  onPointerDown={(event) => startDrag(event, null)}
                  onKeyDown={(event) => nudge(event, null)}
                />
                {gridLines.map(([a, b], index) => (
                  <line
                    className="scanner-crop-grid-line"
                    key={index}
                    x1={a.x * geometry.width}
                    y1={a.y * geometry.height}
                    x2={b.x * geometry.width}
                    y2={b.y * geometry.height}
                  />
                ))}
                {corners.map((point, index) => (
                  <g
                    key={index}
                    className={`scanner-crop-handle${selectedCorner === index ? " is-selected" : ""}`}
                    transform={`translate(${point.x * geometry.width} ${point.y * geometry.height})`}
                    role="button"
                    tabIndex={saving ? -1 : 0}
                    aria-label={`${CORNER_NAMES[index]} board corner. Use arrow keys to adjust.`}
                    onFocus={() => setSelectedCorner(index)}
                    onPointerDown={(event) => startDrag(event, index)}
                    onKeyDown={(event) => nudge(event, index)}
                  >
                    <circle
                      className="scanner-crop-handle-hit"
                      r={handleRadius * 1.5}
                    />
                    <circle
                      className="scanner-crop-handle-face"
                      r={handleRadius}
                    />
                    <text
                      textAnchor="middle"
                      dominantBaseline="central"
                      fontSize={handleRadius * 1.1}
                    >
                      {index + 1}
                    </text>
                  </g>
                ))}
              </svg>
            ) : (
              <p
                className="scanner-editor-loading"
                role={error ? "alert" : "status"}
              >
                {error || "Opening your photo..."}
              </p>
            )}
          </div>
          <p className="scanner-editor-caption">
            <ScannerIcon name="info" />
            <span>
              Drag a corner to fit the board, or drag inside the frame to move
              it. Arrow keys fine-tune; Shift moves farther.
            </span>
          </p>
        </div>
        <aside
          className="scanner-editor-controls"
          aria-label="Photo adjustments"
        >
          <div className="scanner-rotation-tools">
            <h3>Rotate &amp; straighten</h3>
            <p>
              Put White's home rank at the bottom, with a1 in the bottom-left
              corner.
            </p>
            <div className="scanner-angle-control">
              <div className="scanner-angle-heading">
                <label htmlFor={angleId}>Angle (degrees)</label>
                <Button
                  variant="text"
                  size="small"
                  disabled={!photo || saving}
                  onClick={() => changeRotation(0)}
                >
                  Reset to 0°
                </Button>
              </div>
              <div className="scanner-angle-slider">
                <input
                  id={angleId}
                  type="range"
                  min="-180"
                  max="180"
                  step="0.1"
                  value={rotation}
                  aria-valuetext={`${rotation} degrees`}
                  disabled={!photo || saving}
                  onChange={(event) => changeRotation(event.target.value)}
                />
                <output htmlFor={angleId} aria-live="off">
                  {rotation}°
                </output>
              </div>
            </div>
            <div className="scanner-quarter-turns">
              <Button
                variant="secondary"
                size="small"
                disabled={!photo || saving}
                onClick={() => quarterTurn(-90)}
              >
                Turn Left 90°
              </Button>
              <Button
                variant="secondary"
                size="small"
                disabled={!photo || saving}
                onClick={() => quarterTurn(90)}
              >
                Turn Right 90°
              </Button>
            </div>
          </div>
          <div className="scanner-corner-tools">
            <h3>Crop to the board</h3>
            <p>
              Exclude the table and captured pieces. The selected board will be
              straightened into a square.
            </p>
            <label className="scanner-check-option">
              <input
                type="checkbox"
                checked={showGrid}
                onChange={(event) => setShowGrid(event.target.checked)}
              />
              Show 8 × 8 grid
            </label>
            <Button
              variant="text"
              size="small"
              disabled={!photo || saving}
              onClick={reset}
            >
              <ScannerIcon name="undo" />
              Reset Edits
            </Button>
          </div>
        </aside>
      </div>
      <div className="scanner-editor-feedback">
        {feedbackError ? (
          <p className="scanner-field-error" role="alert">
            {feedbackError}
          </p>
        ) : resolution > 0 && resolution < 256 ? (
          <p className="scanner-image-quality-note">
            This crop is small. A closer, sharper photo will preserve more piece
            detail.
          </p>
        ) : null}
      </div>
    </Dialog>
  );
}

export default ScannerImageEditor;
