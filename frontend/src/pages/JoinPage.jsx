import { useEffect, useRef, useState } from "react";

import PageSkeleton from "../components/PageSkeleton";
import SiteFooter from "../components/SiteFooter";
import Button from "../components/ui/Button";
import { pageTitle } from "../documentTitle";
import useDocumentTitle from "../hooks/useDocumentTitle";

// Network failures, rate limits, and server errors can succeed later. An invite
// that was used, replaced, or expired (409) or is malformed (4xx) cannot.
export function joinErrorIsRetryable(status) {
  return status === 0 || status === 429 || status >= 500 || status == null;
}

function JoinPage({ inviteToken, onJoin, onHome }) {
  const startedTokenRef = useRef(null);
  const [failure, setFailure] = useState(null);
  useDocumentTitle(pageTitle("Join game"));

  const join = async () => {
    setFailure(null);
    try {
      await onJoin(inviteToken);
    } catch (requestError) {
      setFailure({
        message: requestError.message,
        retryable: joinErrorIsRetryable(requestError.status),
      });
    }
  };

  useEffect(() => {
    // Guard against StrictMode's double effect so an invite is claimed once.
    if (startedTokenRef.current === inviteToken) return;
    startedTokenRef.current = inviteToken;
    join();
  }, [inviteToken]);

  if (!failure) return <PageSkeleton variant="play" />;

  return (
    <div className="page-frame">
      <main className="landing-shell">
        <section className="join-card">
          <span className="eyebrow">Private game invitation</span>
          <h1>Unable to join</h1>
          <p className="landing-error" role="alert">{failure.message}</p>
          {failure.retryable ? null : (
            <p className="join-status">
              Ask the host for a new invite link or code.
            </p>
          )}
          <div className="button-row">
            {failure.retryable ? <Button onClick={join}>Try again</Button> : null}
            <Button variant={failure.retryable ? "secondary" : "primary"} onClick={onHome}>
              Back home
            </Button>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}

export default JoinPage;
