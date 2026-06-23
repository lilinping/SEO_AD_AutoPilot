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
  iban: string;
  routingNumber: string;
  swiftCode: string;
  companyEntryDescription: string;
};

export function SettlementRecipientFields({
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
      {visibleMetadataFields.includes("recipientType") ? (
        <input
          value={executionForm.recipientType}
          onChange={(event) => onExecutionFormChange((current) => ({ ...current, recipientType: event.target.value }))}
          placeholder={getMetadataFieldPlaceholder("recipientType")}
        />
      ) : null}
      {visibleMetadataFields.includes("externalAccountToken") ? (
        <input
          value={executionForm.externalAccountToken}
          onChange={(event) => onExecutionFormChange((current) => ({ ...current, externalAccountToken: event.target.value }))}
          placeholder={getMetadataFieldPlaceholder("externalAccountToken")}
        />
      ) : null}
    </>
  );
}
