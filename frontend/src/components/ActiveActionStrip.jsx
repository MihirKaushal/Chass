import { buildActionGuidance } from "../actionGuidance";

function Marker({ guidance }) {
  if (guidance.marker === "standard") {
    return <span className="active-action-marker"><i className="move-dot" /></span>;
  }
  return (
    <span className={`active-action-marker marker-${guidance.marker}`}>
      <i>{guidance.icon}</i>
    </span>
  );
}

function ActiveActionStrip(props) {
  const guidance = buildActionGuidance(props);
  return (
    <section
      className={`active-action-strip state-${guidance.state}`}
      aria-live="polite"
      aria-atomic="true"
    >
      <Marker guidance={guidance} />
      <div>
        <strong>{guidance.title}</strong>
        <p>{guidance.description}</p>
      </div>
      <small>{guidance.instruction}</small>
    </section>
  );
}

export default ActiveActionStrip;
