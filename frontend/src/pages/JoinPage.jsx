import { useEffect, useRef, useState } from "react";

import PageSkeleton from "../components/PageSkeleton";
import Button from "../components/ui/Button";

function JoinPage({ inviteToken, onJoin, onHome }) {
  const startedRef = useRef(false);
  const [status, setStatus] = useState("Joining your game...");
  const [error, setError] = useState("");

  const join = async () => {
    setError("");
    setStatus("Joining your game...");
    try {
      await onJoin(inviteToken);
    } catch (requestError) {
      setStatus("");
      setError(requestError.message);
    }
  };

  useEffect(() => {
    if (startedRef.current) {
      return;
    }
    startedRef.current = true;
    join();
  }, [inviteToken]);

  if (!error) return <PageSkeleton variant="play" />;

  return (
    <main className="landing-shell">
      <section className="join-card">
        <span className="eyebrow">Private Game Invitation</span>
        <h1>Unable To Join</h1>
        {status ? <p className="join-status">{status}</p> : null}
        {error ? <p className="landing-error">{error}</p> : null}
        {error ? (
          <div className="button-row">
            <Button onClick={join}>
              Try Again
            </Button>
            <Button variant="secondary" onClick={onHome}>
              Back Home
            </Button>
          </div>
        ) : null}
      </section>
    </main>
  );
}

export default JoinPage;
