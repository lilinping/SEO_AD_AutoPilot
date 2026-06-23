"use client";

import Link from "next/link";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="page">
      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Error</div>
            <h2>Page unavailable</h2>
          </div>
        </div>
        <div className="alert-box">
          <p>This page requires the backend API to be running.</p>
          <p style={{ marginTop: 8 }}>
            Run <code>make api-dev</code> to start the backend.
          </p>
          <div style={{ marginTop: 12, display: "flex", gap: 10 }}>
            <button className="button button-primary" onClick={() => reset()}>
              Try again
            </button>
            <Link className="button button-secondary" href="/">
              Go to overview
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
