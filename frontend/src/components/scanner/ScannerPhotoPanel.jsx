import { useEffect, useRef, useState } from "react";

import IconCloseButton from "../IconCloseButton";
import Button from "../ui/Button";
import ScannerIcon from "./ScannerIcon";

const PHOTO_TIPS = [
  {
    icon: "top",
    title: "Shoot from above",
    text: "Keep the camera parallel to the board, with all four corners visible.",
  },
  {
    icon: "light",
    title: "Use even lighting",
    text: "Avoid glare, strong shadows, and blurred photos.",
  },
  {
    icon: "align",
    title: "Center the pieces",
    text: "Place each piece inside its square. Keep hands and captured pieces off the board.",
  },
];

function ScannerPhotoPanel() {
  const uploadRef = useRef(null);
  const cameraRef = useRef(null);
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [rotation, setRotation] = useState(0);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!file) {
      setPreviewUrl("");
      return undefined;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const choosePhoto = (candidate) => {
    setDragging(false);
    if (!candidate) return;
    const supported =
      ["image/jpeg", "image/png", "image/webp"].includes(candidate.type) ||
      (!candidate.type && /\.(jpe?g|png|webp)$/i.test(candidate.name));
    if (!supported) {
      setError("Choose a JPG, PNG, or WebP image.");
      return;
    }
    if (candidate.size > 10 * 1024 * 1024) {
      setError("Choose an image smaller than 10 MB.");
      return;
    }
    setFile(candidate);
    setRotation(0);
    setError("");
  };

  const handleFileChange = (event) => {
    choosePhoto(event.target.files?.[0]);
    event.target.value = "";
  };

  return (
    <section
      className="scanner-panel scanner-photo-panel"
      aria-labelledby="scanner-photo-title"
    >
      <header className="scanner-panel-header">
        <div>
          <span className="scanner-overline">Your photograph</span>
          <h2 id="scanner-photo-title">Add a board photo</h2>
        </div>
        <span className="scanner-step-label">01</span>
      </header>
      <div
        className={`scanner-photo-dropzone${dragging ? " is-dragging" : ""}${previewUrl ? " has-photo" : ""}`}
        onDragOver={(event) => {
          event.preventDefault();
          if (event.dataTransfer.types.includes("Files")) setDragging(true);
        }}
        onDragLeave={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget))
            setDragging(false);
        }}
        onDrop={(event) => {
          event.preventDefault();
          choosePhoto(event.dataTransfer.files?.[0]);
        }}
      >
        {previewUrl ? (
          <>
            <img
              className={`scanner-photo-preview${rotation % 180 ? " is-rotated" : ""}`}
              src={previewUrl}
              alt="Uploaded physical chessboard for review"
              style={{ transform: `rotate(${rotation}deg)` }}
              onError={() => {
                setFile(null);
                setError(
                  "This image could not be opened. Try another JPG, PNG, or WebP photo.",
                );
              }}
            />
            <IconCloseButton
              className="scanner-remove-photo"
              label="Remove photo"
              onClick={() => {
                setFile(null);
                setError("");
              }}
            />
          </>
        ) : (
          <div className="scanner-upload-placeholder">
            <span className="scanner-capture-mark">
              <ScannerIcon name="camera" />
            </span>
            <strong>Your physical board, on Chass.</strong>
            <p>
              Drop a top-down photo here
              <br />
              or choose an image below.
            </p>
            <span className="scanner-file-types">
              JPG, PNG, WebP · Up to 10 MB
            </span>
          </div>
        )}
        <span className="scanner-photo-corner top-left" aria-hidden="true" />
        <span className="scanner-photo-corner top-right" aria-hidden="true" />
        <span className="scanner-photo-corner bottom-left" aria-hidden="true" />
        <span
          className="scanner-photo-corner bottom-right"
          aria-hidden="true"
        />
      </div>
      <input
        ref={uploadRef}
        className="scanner-hidden-input"
        type="file"
        accept="image/jpeg,image/png,image/webp"
        aria-label="Upload a board photo"
        onChange={handleFileChange}
      />
      <input
        ref={cameraRef}
        className="scanner-hidden-input"
        type="file"
        accept="image/jpeg,image/png,image/webp"
        capture="environment"
        aria-label="Take a board photo"
        onChange={handleFileChange}
      />
      <div className="scanner-photo-actions">
        <Button onClick={() => uploadRef.current?.click()}>
          <ScannerIcon name="upload" />
          {file ? "Replace Photo" : "Upload Photo"}
        </Button>
        <Button variant="secondary" onClick={() => cameraRef.current?.click()}>
          <ScannerIcon name="camera" />
          Take A Photo
        </Button>
      </div>
      {file ? (
        <div className="scanner-photo-file">
          <span title={file.name}>{file.name}</span>
          <Button
            variant="text"
            size="small"
            onClick={() => setRotation((current) => (current + 90) % 360)}
          >
            <ScannerIcon name="rotate" />
            Rotate
          </Button>
        </div>
      ) : null}
      {error ? (
        <p className="scanner-field-error" role="alert">
          {error}
        </p>
      ) : null}
      <div className="scanner-photo-tools">
        <Button
          variant="secondary"
          size="small"
          disabled
          title="Corner detection and adjustment will be connected with recognition."
        >
          Adjust Corners
        </Button>
        <Button
          size="small"
          disabled
          title="Image recognition is not connected in this preview."
        >
          Recognize Pieces
          <ScannerIcon name="arrow" />
        </Button>
      </div>
      <p className="scanner-preview-note">
        <ScannerIcon name="info" />
        <span>
          {file
            ? "Photo preview only. The example board is not generated from this image."
            : "Recognition is not connected yet. Use the example board to try the review controls."}
        </span>
      </p>
      <div className="scanner-photo-tips">
        <h3>For a clearer scan</h3>
        {PHOTO_TIPS.map((tip) => (
          <div className="scanner-photo-tip" key={tip.title}>
            <span className="scanner-tip-icon">
              <ScannerIcon name={tip.icon} />
            </span>
            <div>
              <strong>{tip.title}</strong>
              <p>{tip.text}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

export default ScannerPhotoPanel;
