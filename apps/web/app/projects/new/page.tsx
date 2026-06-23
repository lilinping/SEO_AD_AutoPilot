import { ProjectIntakeForm } from "@/components/ProjectIntakeForm";
import { StatusPill } from "@/components/StatusPill";
import { StatCard } from "@/components/StatCard";

export default function NewProjectPage() {
  return (
    <div className="page">
      <section className="hero">
        <div className="eyebrow">New project</div>
        <h1>Register a site and start the analysis loop.</h1>
        <p className="hero-copy">
          Create the project record, feed in the source signals, and immediately run the preview-first workflow.
          The platform classifies the site, scores risk, and prepares an approval-gated release bundle.
        </p>
        <div className="hero-meta">
          <StatusPill tone="accent">URL required</StatusPill>
          <StatusPill tone="good">Preview first</StatusPill>
          <StatusPill tone="warn">Approval gated</StatusPill>
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Workflow preview</div>
            <h2>What happens after intake</h2>
          </div>
          <p>The intake is intentionally short: create the project, classify the site, generate a preview, then stop at approval.</p>
        </div>
        <div className="stat-grid">
          <StatCard label="1. Create" value="project" caption="register the site and source signals" accent />
          <StatCard label="2. Analyze" value="workflow" caption="classify, score risk, and build a plan" />
          <StatCard label="3. Preview" value="artifact" caption="generate diff and evidence before release" />
          <StatCard label="4. Approve" value="gate" caption="human approval controls deployment" />
        </div>
      </section>

      <ProjectIntakeForm />
    </div>
  );
}
