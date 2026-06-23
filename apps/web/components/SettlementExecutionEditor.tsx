"use client";

import type { WorkspaceBillingSettlementProviderRequirementsReport } from "@seo-ad-autopilot/contracts";

import { SettlementCoreFields } from "@/components/SettlementCoreFields";
import { SettlementMetadataFields } from "@/components/SettlementMetadataFields";
import { SettlementRequirementSummary } from "@/components/SettlementRequirementSummary";
import { StatusPill } from "@/components/StatusPill";

type SettlementExecutionForm = {
  providerName: string;
  amountCents: string;
  memo: string;
  destinationType: string;
  destinationRef: string;
  beneficiaryName: string;
  beneficiaryEmail: string;
  rail: string;
  countryCode: string;
  recipientType: string;
  externalAccountToken: string;
  iban: string;
  routingNumber: string;
  swiftCode: string;
  companyEntryDescription: string;
};

type SettlementRequirementProfile = WorkspaceBillingSettlementProviderRequirementsReport["entries"][number];
type SettlementConditionalRequirement = SettlementRequirementProfile["conditionalRequirements"][number];

export function SettlementExecutionEditor({
  executionForm,
  onExecutionFormChange,
  settlementProviderKind,
  settlementValidationHints,
  isPending,
  onApplyPreset,
  onPreview,
  onExecute,
  effectiveRequirementProfile,
  selectedRequirementProfile,
  requirementCompletion,
  visibleCoreFields,
  visibleMetadataFields,
  activeConditionalRequirements,
  prettifyRequirementValue,
  getMetadataFieldPlaceholder,
}: {
  executionForm: SettlementExecutionForm;
  onExecutionFormChange: (updater: (current: SettlementExecutionForm) => SettlementExecutionForm) => void;
  settlementProviderKind: string;
  settlementValidationHints: string[];
  isPending: boolean;
  onApplyPreset: () => void;
  onPreview: () => void;
  onExecute: () => void;
  effectiveRequirementProfile: SettlementRequirementProfile | null;
  selectedRequirementProfile: SettlementRequirementProfile | null;
  requirementCompletion: { completed: number; total: number };
  visibleCoreFields: {
    beneficiaryName: boolean;
    beneficiaryEmail: boolean;
    rail: boolean;
    countryCode: boolean;
  };
  visibleMetadataFields: string[];
  activeConditionalRequirements: SettlementConditionalRequirement[];
  prettifyRequirementValue: (value: string) => string;
  getMetadataFieldPlaceholder: (fieldKey: string) => string;
}) {
  return (
    <div className="stack" style={{ marginTop: 12 }}>
      <div className="project-foot">
        <span>Execution form</span>
        <StatusPill tone={settlementValidationHints.length ? "warn" : "good"}>{settlementProviderKind}</StatusPill>
        <button className="button button-secondary" type="button" onClick={onApplyPreset} disabled={isPending}>
          Apply preset
        </button>
      </div>
      <SettlementCoreFields
        executionForm={executionForm}
        onExecutionFormChange={onExecutionFormChange}
        effectiveRequirementProfile={effectiveRequirementProfile}
        visibleCoreFields={visibleCoreFields}
        prettifyRequirementValue={prettifyRequirementValue}
      />
      <SettlementMetadataFields
        visibleMetadataFields={visibleMetadataFields}
        executionForm={executionForm}
        onExecutionFormChange={onExecutionFormChange}
        getMetadataFieldPlaceholder={getMetadataFieldPlaceholder}
      />
      <div className="project-copy" style={{ marginTop: 4 }}>
        {settlementValidationHints.length ? `Missing or invalid: ${settlementValidationHints.join(" · ")}` : "Form is ready for live settlement execution."}
      </div>
      <SettlementRequirementSummary
        effectiveRequirementProfile={effectiveRequirementProfile}
        selectedRequirementProfile={selectedRequirementProfile}
        requirementCompletion={requirementCompletion}
        activeConditionalRequirements={activeConditionalRequirements}
      />
      <button className="button" type="button" onClick={onPreview} disabled={isPending}>
        Run settlement preview
      </button>
      <button className="button button-primary" type="button" onClick={onExecute} disabled={isPending || settlementValidationHints.length > 0}>
        Execute settlement
      </button>
    </div>
  );
}
