import { useEffect, useRef, useState } from "react";

import {
  captureScannerPhoto,
  createScannerCameraSession,
  scannerCameraErrorMessage,
} from "../../scannerCamera";
import Button from "../ui/Button";
import Dialog from "../ui/Dialog";
import ScannerIcon from "./ScannerIcon";

function ScannerCameraDialog({ onCapture, onClose }) {
  const videoRef = useRef(null);
  const sessionRef = useRef(null);
  const requestVersionRef = useRef(0);
  const capturingRef = useRef(false);
  const [retryKey, setRetryKey] = useState(0);
  const [ready, setReady] = useState(false);
  const [capturing, setCapturing] = useState(false);
  const [error, setError] = useState("");
  const [captureError, setCaptureError] = useState("");

  useEffect(() => {
    const version = ++requestVersionRef.current;
    const video = videoRef.current;
    const session = createScannerCameraSession(navigator.mediaDevices);
    sessionRef.current = session;
    setReady(false);
    setError("");
    setCaptureError("");

    const fail = (message) => {
      if (version !== requestVersionRef.current) return;
      session.stop();
      video.pause();
      video.srcObject = null;
      setReady(false);
      setError(message);
    };
    const disconnected = () =>
      fail(
        "The camera disconnected. Reconnect it and try again, or upload a photo.",
      );
    let tracks = [];

    const openCamera = async () => {
      if (!navigator.mediaDevices?.getUserMedia) {
        fail(
          "Camera access is unavailable here. Open Chass over HTTPS or localhost in a browser with camera support, or upload a photo.",
        );
        return;
      }
      try {
        const stream = await session.start();
        if (!stream || version !== requestVersionRef.current) return;
        tracks = stream.getVideoTracks();
        tracks.forEach((track) =>
          track.addEventListener("ended", disconnected),
        );
        video.srcObject = stream;
        await video.play();
        if (version === requestVersionRef.current && video.readyState >= 2) {
          setReady(true);
        }
      } catch (cameraError) {
        fail(scannerCameraErrorMessage(cameraError));
      }
    };
    openCamera();

    return () => {
      requestVersionRef.current += 1;
      tracks.forEach((track) =>
        track.removeEventListener("ended", disconnected),
      );
      session.stop();
      if (video) {
        video.pause();
        video.srcObject = null;
      }
    };
  }, [retryKey]);

  const close = () => {
    requestVersionRef.current += 1;
    sessionRef.current?.stop();
    onClose();
  };

  const capture = async () => {
    if (!ready || capturingRef.current) return;
    const version = requestVersionRef.current;
    capturingRef.current = true;
    setCapturing(true);
    setCaptureError("");
    try {
      const photo = await captureScannerPhoto(videoRef.current);
      if (version !== requestVersionRef.current) return;
      sessionRef.current?.stop();
      onCapture(photo);
    } catch (photoError) {
      if (version === requestVersionRef.current) {
        setCaptureError(
          photoError.message ||
            "The photo could not be captured. Please try again.",
        );
      }
    } finally {
      capturingRef.current = false;
      if (version === requestVersionRef.current) setCapturing(false);
    }
  };

  return (
    <Dialog
      open
      className="scanner-camera-dialog"
      eyebrow="Your camera"
      title="Take a board photo"
      description="Hold the camera above the board. Keep all four corners visible and the pieces inside their squares."
      onClose={close}
      closeLabel="Close camera"
      actions={
        <>
          <Button variant="secondary" onClick={close}>
            Cancel
          </Button>
          {error ? (
            <Button onClick={() => setRetryKey((current) => current + 1)}>
              Try Again
            </Button>
          ) : (
            <Button
              disabled={!ready}
              loading={capturing}
              loadingLabel="Capturing..."
              onClick={capture}
            >
              <ScannerIcon name="camera" />
              Capture Photo
            </Button>
          )}
        </>
      }
    >
      <div className={`scanner-camera-viewport${error ? " has-error" : ""}`}>
        <video
          ref={videoRef}
          autoPlay
          muted
          playsInline
          aria-label="Live camera preview"
          onCanPlay={(event) => {
            if (
              !error &&
              event.currentTarget.srcObject &&
              event.currentTarget.videoWidth
            )
              setReady(true);
          }}
        />
        {!ready ? (
          <div
            className="scanner-camera-placeholder"
            role={error ? "alert" : "status"}
          >
            <ScannerIcon name="camera" />
            <strong>
              {error ? "Camera unavailable" : "Starting your camera..."}
            </strong>
            <p>
              {error ||
                "Allow camera access when your browser asks. Only the camera is used; audio stays off."}
            </p>
          </div>
        ) : (
          <div className="scanner-camera-guide" aria-hidden="true">
            <span className="scanner-photo-corner top-left" />
            <span className="scanner-photo-corner top-right" />
            <span className="scanner-photo-corner bottom-left" />
            <span className="scanner-photo-corner bottom-right" />
          </div>
        )}
      </div>
      {captureError ? (
        <p className="scanner-field-error" role="alert">
          {captureError}
        </p>
      ) : null}
      <p className="scanner-camera-note">
        <ScannerIcon name="info" />
        <span>
          The camera turns off when you capture a photo or close this window.
          Your photo stays on this device.
        </span>
      </p>
    </Dialog>
  );
}

export default ScannerCameraDialog;
