export const SCANNER_CAMERA_CONSTRAINTS = {
  audio: false,
  video: {
    facingMode: { ideal: "environment" },
    width: { ideal: 1920 },
    height: { ideal: 1080 },
  },
};

function stopStream(stream) {
  stream?.getTracks().forEach((track) => track.stop());
}

export function createScannerCameraSession(mediaDevices) {
  let activeStream = null;
  let requestVersion = 0;

  const stop = () => {
    requestVersion += 1;
    stopStream(activeStream);
    activeStream = null;
  };

  return {
    stop,
    async start() {
      stop();
      const version = requestVersion;
      let stream;
      try {
        stream = await mediaDevices.getUserMedia(SCANNER_CAMERA_CONSTRAINTS);
      } catch (error) {
        if (version !== requestVersion) return null;
        throw error;
      }
      // Permission may be granted after the dialog has already closed.
      if (version !== requestVersion) {
        stopStream(stream);
        return null;
      }
      activeStream = stream;
      return stream;
    },
  };
}

export function scannerCameraErrorMessage(error) {
  switch (error?.name) {
    case "NotAllowedError":
    case "SecurityError":
      return "Camera access is blocked. Allow camera access for this site in your browser settings, then try again, or upload a photo.";
    case "NotFoundError":
    case "OverconstrainedError":
      return "No available camera was found. Connect a camera and try again, or upload a photo.";
    case "NotReadableError":
    case "AbortError":
      return "The camera could not start. Close other apps using it and try again, or upload a photo.";
    default:
      return "The camera could not be opened. Try again, or use Upload Photo instead.";
  }
}

export async function captureScannerPhoto(video) {
  if (
    !video ||
    video.readyState < 2 ||
    !video.videoWidth ||
    !video.videoHeight
  ) {
    throw new Error(
      "The camera is still starting. Wait for the live picture and try again.",
    );
  }
  const canvas = document.createElement("canvas");
  const scale = Math.min(
    1,
    2048 / Math.max(video.videoWidth, video.videoHeight),
  );
  canvas.width = Math.max(1, Math.round(video.videoWidth * scale));
  canvas.height = Math.max(1, Math.round(video.videoHeight * scale));
  const context = canvas.getContext("2d");
  if (!context)
    throw new Error(
      "This browser could not capture the picture. Upload a photo instead.",
    );
  context.drawImage(video, 0, 0, canvas.width, canvas.height);
  const blob = await new Promise((resolve, reject) => {
    canvas.toBlob(
      (image) =>
        image
          ? resolve(image)
          : reject(
              new Error("The picture could not be saved. Please try again."),
            ),
      "image/jpeg",
      0.94,
    );
  });
  return new File([blob], `chass-board-${Date.now()}.jpg`, {
    type: "image/jpeg",
  });
}
