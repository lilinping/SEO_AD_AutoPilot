"use client";

import React, { ReactNode } from "react";

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends React.Component<
  { children: ReactNode; fallback?: ReactNode },
  ErrorBoundaryState
> {
  constructor(props: { children: ReactNode; fallback?: ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
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
              This page requires the backend API to be running.
              <br />
              Run <code>make api-dev</code> to start the backend.
            </div>
          </section>
        </div>
      );
    }
    return this.props.children;
  }
}
