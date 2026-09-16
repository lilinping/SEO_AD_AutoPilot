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

const statusClass = (passed: boolean) => (passed ? "status-badge good" : "status-badge danger");
const maturityClass = (status: string) => {
  if (status === "production_ready" || status === "operational") return "status-badge good";
  if (status === "missing") return "status-badge danger";
  return "status-badge warn";
};

export default async function AcceptancePage() {
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
        <div className="eyebrow">Acceptance</div>
        <h1>上线验收与成熟度缺口</h1>
        <p className="hero-copy">
          汇总验收 gate、成熟产品对标和剩余阻断任务，直接暴露每项能力最薄弱的流程阶段。
        </p>
        <div className="hero-meta">
          <span className={dataSource === "live" ? "status-badge good" : "status-badge warn"}>
            {dataSource === "live" ? "Live API" : "Fallback data"}
          </span>
          <span className="status-badge accent">Generated {formatDateTime(acceptance.generatedAt)}</span>
          <span className={statusClass(acceptance.passed)}>{acceptance.passed ? "Passed" : "Blocked"}</span>
        </div>
      </section>

      <section className="panel">
        <div className="stat-grid">
          <div className="stat-card">
            <div className="stat-label">Gates</div>
            <div className="stat-value">{acceptance.gates.length}</div>
            <div className="stat-caption">上线验收检查项</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Failed</div>
            <div className="stat-value">{failedGates.length}</div>
            <div className="stat-caption">当前阻断 gate</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Maturity</div>
            <div className="stat-value">{Math.round(benchmark.averageMaturityScore)}</div>
            <div className="stat-caption">成熟产品对标平均分</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Blocking tasks</div>
            <div className="stat-value">{remaining.blockingCount}</div>
            <div className="stat-caption">按缺口生成的阻断任务</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Read evidence</div>
            <div className="stat-value">{acceptance.readRealEvidenceCount}</div>
            <div className="stat-caption">真实读取证据样本</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Write evidence</div>
            <div className="stat-value">{acceptance.writeRealEvidenceCount}</div>
            <div className="stat-caption">真实写回证据样本</div>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Blocking gates</div>
            <h2>当前验收阻断</h2>
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
                <span>Expected</span>
                <strong>{gate.expected}</strong>
              </div>
              <div className="metric-row">
                <span>Actual</span>
                <strong>{gate.actual}</strong>
              </div>
              {gate.quickActionPath ? (
                <div className="project-foot">
                  <span>{gate.notes[0] ?? "Needs remediation"}</span>
                  <Link href={gate.quickActionPath}>{gate.quickActionLabel ?? "Open"}</Link>
                </div>
              ) : null}
            </article>
          ))}
          {failedGates.length === 0 ? <div className="empty-state">全部验收 gate 已通过</div> : null}
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Remaining work</div>
            <h2>阻断任务与最弱阶段</h2>
          </div>
        </div>
        <div className="grid-three">
          {blockingTasks.map((task) => (
            <article className="audit-card" key={task.taskId}>
              <div className="audit-head">
                <strong>{task.title}</strong>
                <span className="status-badge warn">{task.priority.toUpperCase()}</span>
              </div>
              <div className="project-copy">{task.nextAction ?? task.remainingGaps[0] ?? "等待补齐"}</div>
              <div className="metric-row">
                <span>Weakest stage</span>
                <strong>{task.weakestStageTitle ?? task.weakestStageId ?? "Unknown"}</strong>
              </div>
              <div className="project-foot">
                <span>{task.acceptanceGateIds.length} failed gates</span>
                {task.quickActionPath ? <Link href={task.quickActionPath}>{task.quickActionLabel ?? "Open"}</Link> : null}
              </div>
            </article>
          ))}
          {blockingTasks.length === 0 ? <div className="empty-state">暂无阻断任务</div> : null}
        </div>
      </section>

      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Provider evidence</div>
            <h2>真实 Provider 证据缺口</h2>
          </div>
        </div>
        <div className="grid-three">
          {providerEvidenceGaps.map((provider) => (
            <article className="audit-card" key={provider.provider}>
              <div className="audit-head">
                <strong>{provider.provider}</strong>
                <span className="status-badge warn">{provider.evidenceGapType}</span>
              </div>
              <div className="project-copy">{provider.evidenceGapSummary ?? provider.smokeAction ?? "Evidence refresh required"}</div>
              <div className="metric-row">
                <span>Real / Total</span>
                <strong>
                  {provider.realConnectionCount} / {provider.totalConnectionCount}
                </strong>
              </div>
              <div className="metric-row">
                <span>Strict-ready</span>
                <strong>{provider.strictEligibleCount}</strong>
              </div>
              <div className="project-foot">
                <span>{provider.acceptanceGateId ?? "provider evidence"}</span>
                {provider.smokeActionPath ? <Link href={provider.smokeActionPath}>{provider.smokeActionLabel ?? "Run smoke"}</Link> : null}
              </div>
            </article>
          ))}
          {providerEvidenceGaps.length === 0 ? <div className="empty-state">真实 provider 证据已覆盖当前连接</div> : null}
        </div>
      </section>

      <section className="panel" id="visual-farm-runtime">
        <div className="section-heading">
          <div>
            <div className="eyebrow">Visual farm</div>
            <h2>视觉农场生产化缺口</h2>
          </div>
          <span className={visualFarmBlocked ? "status-badge danger" : "status-badge good"}>
            {visualFarmStatus.readinessGapType ?? "none"}
          </span>
        </div>
        <div className="grid-three">
          <article className="audit-card">
            <div className="audit-head">
              <strong>Strict publish readiness</strong>
              <span className={visualFarmStatus.strictPublishReady ? "status-badge good" : "status-badge danger"}>
                {visualFarmStatus.strictPublishReady ? "ready" : "blocked"}
              </span>
            </div>
            <div className="project-copy">{visualFarmStatus.readinessGapSummary ?? "Visual farm readiness status is unavailable."}</div>
            <div className="metric-row">
              <span>Acceptance gate</span>
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
              <strong>Probe freshness</strong>
              <span className={visualFarmStatus.probeFresh ? "status-badge good" : "status-badge warn"}>
                {visualFarmStatus.probeFresh ? "fresh" : "stale"}
              </span>
            </div>
            <div className="metric-row">
              <span>Connected / Blocking</span>
              <strong>
                {visualFarmStatus.lastProbeConnectedCount} / {visualFarmStatus.lastProbeBlockingCount}
              </strong>
            </div>
            <div className="metric-row">
              <span>Freshness window</span>
              <strong>{visualFarmStatus.probeFreshnessMinutes}m</strong>
            </div>
            <div className="project-copy">Last probe {formatDateTime(visualFarmStatus.lastProbeExecutedAt ?? visualFarmStatus.generatedAt)}</div>
          </article>
          <article className="audit-card">
            <div className="audit-head">
              <strong>Run evidence</strong>
              <span className={visualFarmStatus.lastRunFailedCaseCount ? "status-badge danger" : "status-badge good"}>
                {visualFarmStatus.runCount} runs
              </span>
            </div>
            <div className="metric-row">
              <span>Connected cases</span>
              <strong>{visualFarmStatus.lastRunConnectedCaseCount}</strong>
            </div>
            <div className="metric-row">
              <span>Failed / Fallback / Blocked</span>
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
            <div className="eyebrow">Product benchmark</div>
            <h2>成熟能力流程诊断</h2>
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
                <span>Maturity score</span>
                <strong>{capability.maturityScore}</strong>
              </div>
              <div className="metric-row">
                <span>Weakest stage</span>
                <strong>{capability.weakestStageTitle ?? capability.weakestStageId ?? "Unknown"}</strong>
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
                {recommendedIds.has(capability.capabilityId) ? <span className="status-badge accent">Recommended next</span> : null}
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
