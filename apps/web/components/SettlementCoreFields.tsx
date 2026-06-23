"use client";

import type { WorkspaceBillingSettlementProviderRequirementsReport } from "@seo-ad-autopilot/contracts";

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

export function SettlementCoreFields({
  executionForm,
  onExecutionFormChange,
  effectiveRequirementProfile,
  visibleCoreFields,
  prettifyRequirementValue,
}: {
  executionForm: SettlementExecutionForm;
  onExecutionFormChange: (updater: (current: SettlementExecutionForm) => SettlementExecutionForm) => void;
  effectiveRequirementProfile: SettlementRequirementProfile | null;
  visibleCoreFields: {
    beneficiaryName: boolean;
    beneficiaryEmail: boolean;
    rail: boolean;
    countryCode: boolean;
  };
  prettifyRequirementValue: (value: string) => string;
}) {
  return (
    <>
      <input
        value={executionForm.providerName}
        onChange={(event) => onExecutionFormChange((current) => ({ ...current, providerName: event.target.value }))}
        placeholder="execution provider name"
      />
      <input
        value={executionForm.amountCents}
        onChange={(event) => onExecutionFormChange((current) => ({ ...current, amountCents: event.target.value }))}
        placeholder="execution amount cents"
      />
      <input
        value={executionForm.memo}
        onChange={(event) => onExecutionFormChange((current) => ({ ...current, memo: event.target.value }))}
        placeholder="execution memo"
      />
      {effectiveRequirementProfile?.destinationTypes.length ? (
        <select value={executionForm.destinationType} onChange={(event) => onExecutionFormChange((current) => ({ ...current, destinationType: event.target.value }))}>
          <option value="">select destination type</option>
          {effectiveRequirementProfile.destinationTypes.map((value) => (
            <option key={value} value={value}>
              {prettifyRequirementValue(value)}
            </option>
          ))}
        </select>
      ) : (
        <input
          value={executionForm.destinationType}
          onChange={(event) => onExecutionFormChange((current) => ({ ...current, destinationType: event.target.value }))}
          placeholder="destination type"
        />
      )}
      <input
        value={executionForm.destinationRef}
        onChange={(event) => onExecutionFormChange((current) => ({ ...current, destinationRef: event.target.value }))}
        placeholder="destination ref"
      />
      {visibleCoreFields.beneficiaryName ? (
        <input
          value={executionForm.beneficiaryName}
          onChange={(event) => onExecutionFormChange((current) => ({ ...current, beneficiaryName: event.target.value }))}
          placeholder="beneficiary name"
        />
      ) : null}
      {visibleCoreFields.beneficiaryEmail ? (
        <input
          value={executionForm.beneficiaryEmail}
          onChange={(event) => onExecutionFormChange((current) => ({ ...current, beneficiaryEmail: event.target.value }))}
          placeholder="beneficiary email"
        />
      ) : null}
      {visibleCoreFields.rail ? (
        effectiveRequirementProfile?.rails.length ? (
          <select value={executionForm.rail} onChange={(event) => onExecutionFormChange((current) => ({ ...current, rail: event.target.value }))}>
            <option value="">select rail</option>
            {effectiveRequirementProfile.rails.map((value) => (
              <option key={value} value={value}>
                {prettifyRequirementValue(value)}
              </option>
            ))}
          </select>
        ) : (
          <input
            value={executionForm.rail}
            onChange={(event) => onExecutionFormChange((current) => ({ ...current, rail: event.target.value }))}
            placeholder="rail"
          />
        )
      ) : null}
      {visibleCoreFields.countryCode ? (
        <input
          value={executionForm.countryCode}
          onChange={(event) => onExecutionFormChange((current) => ({ ...current, countryCode: event.target.value }))}
          placeholder="country code"
        />
      ) : null}
    </>
  );
}
