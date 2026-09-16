import Link from "next/link";

import {
  getAcceptanceReport,
  getProductBenchmarkReport,
  getRemainingTaskReport,
  getVisualFarmStatusReport,
  getWorkspaceConnectorsHealth,
} from "@/lib/api";
import {
  fallbackAcceptanceReport,
  fallbackProductBenchmarkReport,
  fallbackRemainingTaskReport,
  fallbackVisualFarmStatusReport,
  fallbackWorkspaceConnectorsHealthReport,
} from "@/lib/fallback";
import { formatDateTime } from "@/lib/format";
import { getServerI18n } from "@/lib/i18n/server";

const statusClass = (passed: boolean) => (passed ? "status-badge good" : "status-badge danger");
const maturityClass = (status: string) => {
  if (status === "production_ready" || status === "operational") return "status-badge good";
  if (status === "missing") return "status-badge danger";
  return "status-badge warn";
};

export default async function AcceptancePage() {
  const { locale, t } = getServerI18n();
  let acceptance = fallbackAcceptanceReport();
  let benchmark = fallbackProductBenchmarkReport();
  let remaining = fallbackRemainingTaskReport();
  let connectorsHealth = fallbackWorkspaceConnectorsHealthReport();
  let visualFarmStatus = fallbackVisualFarmStatusReport();
  let dataSource: "live" | "fallback" = "fallback";

  try {
    [acceptance, benchmark, remaining, connectorsHealth, visualFarmStatus] = await Promise.all([
      getAcceptanceReport(),
      getProductBenchmarkReport(),
      getRemainingTaskReport(),
      getWorkspaceConnectorsHealth(),
      getVisualFarmStatusReport(),
    ]);
    dataSource = "live";
  } catch (error) {
    console.error("Failed to fetch acceptance data:", error);
  }

  const failedGates = acceptance.gates.filter((gate) => !gate.passed);
  const blockingTasks = remaining.items.filter((item) => item.blocking).slice(0, 6);
  const gapRank = { missing_real: 0, fallback_only: 1, strict_gap: 2, blocking: 3, stale_or_unknown: 4, none: 5 };
  const providerEvidenceGaps = connectorsHealth.providerCoverage
    .filter((item) => item.evidenceGapType && item.evidenceGapType !== "none")
    .sort((a, b) => {
      const aRank = gapRank[a.evidenceGapType ?? "none"] ?? 9;
      const bRank = gapRank[b.evidenceGapType ?? "none"] ?? 9;
      return aRank - bRank || b.blockingProjectCount - a.blockingProjectCount || a.provider.localeCompare(b.provider);
    })
    .slice(0, 6);
  const visualFarmBlocked = Boolean(visualFarmStatus.readinessGapType && visualFarmStatus.readinessGapType !== "none");
  const recommendedIds = new Set(benchmark.recommendedNextCapabilityIds);
  const capabilities = [...benchmark.capabilities].sort((a, b) => {
    const aRecommended = recommendedIds.has(a.capabilityId) ? 0 : 1;
    const bRecommended = recommendedIds.has(b.capabilityId) ? 0 : 1;
    return aRecommended - bRecommended || a.maturityScore - b.maturityScore;
  });

  return (
    <div className="page">
      <section className="hero">
        <div className="eyebrow">{t("nav.acceptance")}</div>
        <h1>{t("acceptance.title")}</h1>
        <p className="hero-copy">{t("acceptance.hero_description")}</p>
        <div className="hero-meta">
          <span className={dataSource === "live" ? "status-badge good" : "status-badge warn"}>
            {dataSource === "live" ? t("acceptance.live_api") : t("acceptance.fallback_data")}
          </span>
          <span className="status-badge accent">{t("acceptance.generated")} {formatDateTime(acceptance.generatedAt, locale)}</span>
          <span className={statusClass(acceptance.passed)}>{acceptance.passed ? t("acceptance.passed") : t("acceptance.blocked")}</span>
        </div>
      </section>

      <section className="panel">
        <div className="stat-grid">
          <div className="stat-card">
            <div className="stat-label">{t("acceptance.gates")}</div>
            <div className="stat-value">{acceptance.gates.length}</div>
            <div className="stat-caption">{t("acceptance.gate_caption")}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">{t("acceptance.failed")}</div>
            <div className="stat-value">{failedGates.length}</div>
            <div className="stat-caption">{t("acceptance.failed_caption")}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">{t("acceptance.maturity")}</div>
            <div className="stat-value">{Math.round(benchmark.averageMaturityScore)}</div>
            <div className="stat-caption">{t("acceptance.maturity_caption")}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">{t("acceptance.blocking_tasks")}</div>
            <div className="stat-value">{remaining.blockingCount}</div>
            <div className="stat-caption">{t("acceptance.blocking_tasks_caption")}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">{t("acceptance.read_evidence")}</div>
            <div className="stat-value">{acceptance.readRealEvidenceCount}</div>
            <div className="stat-caption">{t("acceptance.read_evidence_caption")}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">{t("acceptance.write_evidence")}</div>
            <div className="stat-value">{acceptance.writeRealEvidenceCount}</div>
            <div className="stat-caption">{t("acceptance.write_evidence_caption")}</div>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">{t("acceptance.blocking_gates")}</div>
            <h2>{t("acceptance.current_blockers")}</h2>
          </div>
        </div>
        <div className="stack">
          {failedGates.slice(0, 8).map((gate) => (
            <article className="audit-card" key={gate.gateId}>
              <div className="audit-head">
                <strong>{gate.name}</strong>
                <span className="status-badge danger">{gate.gateId}</span>
              </div>
              <div className="metric-row">
                <span>{t("acceptance.expected")}</span>
                <strong>{gate.expected}</strong>
              </div>
              <div className="metric-row">
                <span>{t("acceptance.actual")}</span>
                <strong>{gate.actual}</strong>
              </div>
              {gate.quickActionPath ? (
                <div className="project-foot">
                  <span>{gate.notes[0] ?? t("acceptance.needs_remediation")}</span>
                  <Link href={gate.quickActionPath}>{gate.quickActionLabel ?? t("acceptance.open")}</Link>
                </div>
              ) : null}
            </article>
          ))}
          {failedGates.length === 0 ? <div className="empty-state">{t("acceptance.all_gates_passed")}</div> : null}
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">{t("acceptance.remaining_work")}</div>
            <h2>{t("acceptance.weakest_stage_tasks")}</h2>
          </div>
        </div>
        <div className="grid-three">
          {blockingTasks.map((task) => (
            <article className="audit-card" key={task.taskId}>
              <div className="audit-head">
                <strong>{task.title}</strong>
                <span className="status-badge warn">{task.priority.toUpperCase()}</span>
              </div>
              <div className="project-copy">{task.nextAction ?? task.remainingGaps[0] ?? t("acceptance.waiting")}</div>
              <div className="metric-row">
                <span>{t("acceptance.weakest_stage")}</span>
                <strong>{task.weakestStageTitle ?? task.weakestStageId ?? t("acceptance.unknown")}</strong>
              </div>
              <div className="project-foot">
                <span>{task.acceptanceGateIds.length} {t("acceptance.failed_gates_suffix")}</span>
                {task.quickActionPath ? <Link href={task.quickActionPath}>{task.quickActionLabel ?? t("acceptance.open")}</Link> : null}
              </div>
            </article>
          ))}
          {blockingTasks.length === 0 ? <div className="empty-state">{t("acceptance.no_blocking_tasks")}</div> : null}
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">{t("acceptance.provider_evidence")}</div>
            <h2>{t("acceptance.provider_evidence_gaps")}</h2>
          </div>
        </div>
        <div className="grid-three">
          {providerEvidenceGaps.map((provider) => (
            <article className="audit-card" key={provider.provider}>
              <div className="audit-head">
                <strong>{provider.provider}</strong>
                <span className="status-badge warn">{provider.evidenceGapType}</span>
              </div>
              <div className="project-copy">{provider.evidenceGapSummary ?? provider.smokeAction ?? t("acceptance.evidence_refresh_required")}</div>
              <div className="metric-row">
                <span>{t("acceptance.real_total")}</span>
                <strong>
                  {provider.realConnectionCount} / {provider.totalConnectionCount}
                </strong>
              </div>
              <div className="metric-row">
                <span>{t("acceptance.strict_ready")}</span>
                <strong>{provider.strictEligibleCount}</strong>
              </div>
              <div className="project-foot">
                <span>{provider.acceptanceGateId ?? "provider evidence"}</span>
                {provider.smokeActionPath ? <Link href={provider.smokeActionPath}>{provider.smokeActionLabel ?? t("acceptance.run_smoke")}</Link> : null}
              </div>
            </article>
          ))}
          {providerEvidenceGaps.length === 0 ? <div className="empty-state">{t("acceptance.provider_evidence_complete")}</div> : null}
        </div>
      </section>

      <section className="panel" id="visual-farm-runtime">
        <div className="section-heading">
          <div>
            <div className="eyebrow">{t("acceptance.visual_farm")}</div>
            <h2>{t("acceptance.visual_farm_gaps")}</h2>
          </div>
          <span className={visualFarmBlocked ? "status-badge danger" : "status-badge good"}>
            {visualFarmStatus.readinessGapType ?? "none"}
          </span>
        </div>
        <div className="grid-three">
          <article className="audit-card">
            <div className="audit-head">
              <strong>{t("acceptance.strict_publish_readiness")}</strong>
              <span className={visualFarmStatus.strictPublishReady ? "status-badge good" : "status-badge danger"}>
                {visualFarmStatus.strictPublishReady ? t("acceptance.ready") : t("acceptance.blocked")}
              </span>
            </div>
            <div className="project-copy">{visualFarmStatus.readinessGapSummary ?? "Visual farm readiness status is unavailable."}</div>
            <div className="metric-row">
              <span>{t("acceptance.acceptance_gate")}</span>
              <strong>{visualFarmStatus.acceptanceGateId ?? "visual_farm_runtime_ready"}</strong>
            </div>
            <div className="project-foot">
              <span>{visualFarmStatus.remediationAction ?? "Keep probe evidence fresh"}</span>
              {visualFarmStatus.remediationActionPath ? (
                <Link href={visualFarmStatus.remediationActionPath}>{visualFarmStatus.remediationActionLabel ?? "Open"}</Link>
              ) : null}
            </div>
          </article>
          <article className="audit-card">
            <div className="audit-head">
              <strong>{t("acceptance.probe_freshness")}</strong>
              <span className={visualFarmStatus.probeFresh ? "status-badge good" : "status-badge warn"}>
                {visualFarmStatus.probeFresh ? t("acceptance.fresh") : t("acceptance.stale")}
              </span>
            </div>
            <div className="metric-row">
              <span>{t("acceptance.connected_blocking")}</span>
              <strong>
                {visualFarmStatus.lastProbeConnectedCount} / {visualFarmStatus.lastProbeBlockingCount}
              </strong>
            </div>
            <div className="metric-row">
              <span>{t("acceptance.freshness_window")}</span>
              <strong>{visualFarmStatus.probeFreshnessMinutes}m</strong>
            </div>
            <div className="project-copy">{t("acceptance.last_probe")} {formatDateTime(visualFarmStatus.lastProbeExecutedAt ?? visualFarmStatus.generatedAt, locale)}</div>
          </article>
          <article className="audit-card">
            <div className="audit-head">
              <strong>{t("acceptance.run_evidence")}</strong>
              <span className={visualFarmStatus.lastRunFailedCaseCount ? "status-badge danger" : "status-badge good"}>
                {visualFarmStatus.runCount} {t("acceptance.runs_suffix")}
              </span>
            </div>
            <div className="metric-row">
              <span>{t("acceptance.connected_cases")}</span>
              <strong>{visualFarmStatus.lastRunConnectedCaseCount}</strong>
            </div>
            <div className="metric-row">
              <span>{t("acceptance.failed_fallback_blocked")}</span>
              <strong>
                {visualFarmStatus.lastRunFailedCaseCount} / {visualFarmStatus.lastRunFallbackCaseCount} / {visualFarmStatus.lastRunStrictBlockedCaseCount}
              </strong>
            </div>
            <div className="project-copy">{visualFarmStatus.notes[0] ?? "Latest visual regression run has no notes."}</div>
          </article>
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">{t("acceptance.product_benchmark")}</div>
            <h2>{t("acceptance.capability_diagnostics")}</h2>
          </div>
        </div>
        <div className="stack">
          {capabilities.map((capability) => (
            <article className="audit-card" key={capability.capabilityId}>
              <div className="audit-head">
                <strong>{capability.title}</strong>
                <span className={maturityClass(capability.currentStatus)}>{capability.currentStatus}</span>
              </div>
              <div className="metric-row">
                <span>{t("acceptance.maturity_score")}</span>
                <strong>{capability.maturityScore}</strong>
              </div>
              <div className="metric-row">
                <span>{t("acceptance.weakest_stage")}</span>
                <strong>{capability.weakestStageTitle ?? capability.weakestStageId ?? t("acceptance.unknown")}</strong>
              </div>
              <div className="grid-three">
                {capability.workflowStages.map((stage) => (
                  <div className="stat-card" key={`${capability.capabilityId}-${stage.stageId}`}>
                    <div className="stat-label">{stage.title}</div>
                    <div className="stat-value">{stage.score}</div>
                    <div className="stat-caption">{stage.gaps[0] ?? stage.status}</div>
                  </div>
                ))}
              </div>
              <div className="project-foot">
                <span>{capability.comparableProducts.join(" / ")}</span>
                {recommendedIds.has(capability.capabilityId) ? <span className="status-badge accent">{t("acceptance.recommended_next")}</span> : null}
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
