import Button from "../ui/Button";
import StatusBadge from "../ui/StatusBadge";

const COPY = {
  checking: {
    tone: "neutral",
    label: "Checking Connection",
    text: "You can prepare your photo while we check recognition availability.",
  },
  ready: {
    tone: "success",
    label: "Recognition Connected",
    text: "Your cropped photo is sent to the scanner service only when you choose Recognize Pieces.",
  },
  offline: {
    tone: "warning",
    label: "Recognition Offline",
    text: "Photo preparation still works. Start or reconnect the scanner service, then try again.",
  },
  unconfigured: {
    tone: "neutral",
    label: "Photo Preparation Only",
    text: "Recognition is not enabled on this deployment yet. You can still upload, rotate, crop, and save a prepared photo.",
  },
};

function ScannerServiceStatus({ status, onRetry }) {
  const copy = COPY[status] || COPY.offline;
  return (
    <section
      className="scanner-service-status"
      aria-label="Recognition availability"
    >
      <div role="status">
        <StatusBadge tone={copy.tone}>{copy.label}</StatusBadge>
        <p>{copy.text}</p>
      </div>
      {status === "offline" ? (
        <Button variant="secondary" size="small" onClick={onRetry}>
          Retry Connection
        </Button>
      ) : null}
    </section>
  );
}

export default ScannerServiceStatus;
