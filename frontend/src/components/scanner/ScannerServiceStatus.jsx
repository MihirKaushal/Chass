import Button from "../ui/Button";
import StatusBadge from "../ui/StatusBadge";

const COPY = {
  checking: {
    tone: "neutral",
    label: "Connecting",
    text: "You can prepare your photo now.",
  },
  warming: {
    tone: "neutral",
    label: "Starting scanner",
    text: "Waking the service. This may take a minute or two.",
  },
  ready: {
    tone: "success",
    label: "Scanner ready",
    text: "",
  },
  offline: {
    tone: "warning",
    label: "Recognition offline",
    text: "Could not connect. Your photo is still here; try again.",
  },
  unconfigured: {
    tone: "neutral",
    label: "Photo Preparation Only",
    text: "Recognition is not configured for this site.",
  },
};

function ScannerServiceStatus({ status, onRetry }) {
  const copy = COPY[status] || COPY.offline;
  return (
    <section
      className="scanner-service-status"
      aria-label="Recognition availability"
    >
      <div role="status" className="scanner-service-message">
        <StatusBadge tone={copy.tone} busy={status === "checking" || status === "warming"}>{copy.label}</StatusBadge>
        {copy.text ? <p>{copy.text}</p> : null}
      </div>
      {status === "offline" ? (
        <Button variant="secondary" size="small" onClick={onRetry}>
          Retry connection
        </Button>
      ) : null}
    </section>
  );
}

export default ScannerServiceStatus;
