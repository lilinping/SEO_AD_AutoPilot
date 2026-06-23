"use client";

import Link from "next/link";

export default function NotFound() {
  return (
    <div className="page">
      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">404</div>
            <h2>Page not found</h2>
          </div>
        </div>
        <div className="alert-box">
          <p>The page you are looking for does not exist.</p>
          <Link className="button button-primary" href="/" style={{ marginTop: 12, display: "inline-block" }}>
            Go to overview
          </Link>
        </div>
      </section>
    </div>
  );
}
