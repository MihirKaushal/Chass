import { useEffect, useRef, useState } from "react";

import IconCloseButton from "../IconCloseButton";
import Button from "../ui/Button";
import ScannerCameraDialog from "./ScannerCameraDialog";
import ScannerIcon from "./ScannerIcon";
import ScannerImageEditor from "./ScannerImageEditor";
import { downloadScannerFile } from "../../scannerApi";

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
  {
    icon: "rotate",
    title: "Rotate and crop before scanning",
    text: "Put White's home rank at the bottom. Crop to the playing grid, keeping all 64 squares and pieces visible, without the surrounding table.",
  },
];

function ScannerPhotoPanel({
  onRecognize,
  onPhotoChange,
  busy = false,
  serviceAvailable = false,
}) {
  const uploadRef = useRef(null);
  const [cameraOpen, setCameraOpen] = useState(false);
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [originalFile, setOriginalFile] = useState(null);
  const [edits, setEdits] = useState(null);
  const [editorOpen, setEditorOpen] = useState(false);
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
    onPhotoChange?.(true);
    setOriginalFile(candidate);
    setEdits(null);
    setEditorOpen(true);
    setError("");
  };

  const removePhoto = () => {
    onPhotoChange?.(false);
    setFile(null);
    setOriginalFile(null);
    setEdits(null);
    setEditorOpen(false);
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
      <input
        ref={uploadRef}
        className="scanner-hidden-input"
        type="file"
        accept="image/jpeg,image/png,image/webp"
        aria-label="Upload a board photo"
        onChange={handleFileChange}
      />
      <div className="scanner-photo-actions">
        <Button onClick={() => uploadRef.current?.click()}>
          <ScannerIcon name="upload" />
          {file ? "Replace Photo" : "Upload Photo"}
        </Button>
        <Button variant="secondary" onClick={() => setCameraOpen(true)}>
          <ScannerIcon name="camera" />
          Take A Photo
        </Button>
      </div>
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
              className="scanner-photo-preview"
              src={previewUrl}
              alt="Uploaded physical chessboard for review"
              onError={() => {
                removePhoto();
                setError(
                  "This image could not be opened. Try another JPG, PNG, or WebP photo.",
                );
              }}
            />
            <IconCloseButton
              className="scanner-remove-photo"
              label="Remove photo"
              onClick={removePhoto}
            />
          </>
        ) : (
          <div className="scanner-upload-placeholder">
            <span className="scanner-capture-mark">
              <ScannerIcon name="camera" />
            </span>
            <strong>Drop a top-down board photo here</strong>
            <p>Include all 64 squares and keep the pieces centered.</p>
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
      {file ? (
        <div className="scanner-photo-file">
          <span title={file.name}>{file.name}</span>
          {edits ? (
            <span className="scanner-edited-label">Edited photo</span>
          ) : null}
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
          disabled={!originalFile}
          onClick={() => setEditorOpen(true)}
        >
          <ScannerIcon name="rotate" />
          Crop &amp; Rotate
        </Button>
        <Button
          size="small"
          disabled={!file || !edits || busy || !serviceAvailable}
          onClick={() => onRecognize?.(file)}
          title={
            !serviceAvailable
              ? "Recognition is unavailable. Check the connection status above."
              : !edits
                ? "Apply Crop & Rotate first, with White at the bottom."
                : undefined
          }
        >
          {busy ? "Recognizing..." : "Recognize Pieces"}
          <ScannerIcon name="arrow" />
        </Button>
      </div>
      {edits && file ? (
        <Button
          variant="text"
          size="small"
          onClick={() => downloadScannerFile(file, file.name)}
        >
          Save Prepared Photo
        </Button>
      ) : null}
      <p className="scanner-preview-note">
        <ScannerIcon name="info" />
        <span>
          Apply the crop to the 8 x 8 playing grid, with White's home rank at
          the bottom, before recognizing pieces.
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
      {cameraOpen ? (
        <ScannerCameraDialog
          onClose={() => setCameraOpen(false)}
          onCapture={(photo) => {
            choosePhoto(photo);
            setCameraOpen(false);
          }}
        />
      ) : null}
      {editorOpen && originalFile ? (
        <ScannerImageEditor
          sourceFile={originalFile}
          initialEdits={edits}
          onClose={() => setEditorOpen(false)}
          onApply={(prepared, settings) => {
            onPhotoChange?.(true);
            setFile(prepared);
            setEdits(settings);
            setEditorOpen(false);
          }}
        />
      ) : null}
    </section>
  );
}

export default ScannerPhotoPanel;
