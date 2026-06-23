"use client";

import type { WorkspaceBillingSettlementProviderRequirementsReport } from "@seo-ad-autopilot/contracts";

type SettlementRequirementProfile = WorkspaceBillingSettlementProviderRequirementsReport["entries"][number];
type SettlementConditionalRequirement = SettlementRequirementProfile["conditionalRequirements"][number];

export function SettlementRequirementSummary({
  effectiveRequirementProfile,
  selectedRequirementProfile,
  requirementCompletion,
  activeConditionalRequirements,
}: {
  effectiveRequirementProfile: SettlementRequirementProfile | null;
  selectedRequirementProfile: SettlementRequirementProfile | null;
  requirementCompletion: { completed: number; total: number };
  activeConditionalRequirements: SettlementConditionalRequirement[];
}) {
  return (
    <>
      {effectiveRequirementProfile ? (
        <div className="audit-meta" style={{ marginTop: 4 }}>
          {selectedRequirementProfile ? "backend profile" : "fallback profile"} · destination {effectiveRequirementProfile.destinationTypes.join(", ") || "n/a"} · rails{" "}
          {effectiveRequirementProfile.rails.join(", ") || "n/a"} · required {effectiveRequirementProfile.requiredFields.join(", ")} · metadata{" "}
          {effectiveRequirementProfile.metadataFields.join(", ") || "none"} · conditional{" "}
          {effectiveRequirementProfile.conditionalRequirements.length
            ? effectiveRequirementProfile.conditionalRequirements.map((rule) => `${rule.whenField}=${rule.whenValue}:${rule.metadataFields.join("/") || rule.requiredFields.join("/")}`).join(" · ")
            : "none"} · completion {requirementCompletion.completed}/{requirementCompletion.total || 0}
        </div>
      ) : null}
      {activeConditionalRequirements.length ? (
        <div className="audit-meta" style={{ marginTop: 4 }}>
          active rules · {activeConditionalRequirements.map((rule) => `${rule.whenField}=${rule.whenValue}`).join(" · ")}
        </div>
      ) : null}
    </>
  );
}
