"use client";

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
  companyEntryDescription: string;
  iban: string;
  routingNumber: string;
  swiftCode: string;
};

export function SettlementBankRailFields({
  visibleMetadataFields,
  executionForm,
  onExecutionFormChange,
  getMetadataFieldPlaceholder,
}: {
  visibleMetadataFields: string[];
  executionForm: SettlementExecutionForm;
  onExecutionFormChange: (updater: (current: SettlementExecutionForm) => SettlementExecutionForm) => void;
  getMetadataFieldPlaceholder: (fieldKey: string) => string;
}) {
  return (
    <>
      {visibleMetadataFields.includes("companyEntryDescription") ? (
        <input
          value={executionForm.companyEntryDescription}
          onChange={(event) => onExecutionFormChange((current) => ({ ...current, companyEntryDescription: event.target.value }))}
          placeholder={getMetadataFieldPlaceholder("companyEntryDescription")}
        />
      ) : null}
      {visibleMetadataFields.includes("iban") ? (
        <input
          value={executionForm.iban}
          onChange={(event) => onExecutionFormChange((current) => ({ ...current, iban: event.target.value }))}
          placeholder={getMetadataFieldPlaceholder("iban")}
        />
      ) : null}
      {visibleMetadataFields.includes("routingNumber") ? (
        <input
          value={executionForm.routingNumber}
          onChange={(event) => onExecutionFormChange((current) => ({ ...current, routingNumber: event.target.value }))}
          placeholder={getMetadataFieldPlaceholder("routingNumber")}
        />
      ) : null}
      {visibleMetadataFields.includes("swiftCode") ? (
        <input
          value={executionForm.swiftCode}
          onChange={(event) => onExecutionFormChange((current) => ({ ...current, swiftCode: event.target.value }))}
          placeholder={getMetadataFieldPlaceholder("swiftCode")}
        />
      ) : null}
    </>
  );
}
