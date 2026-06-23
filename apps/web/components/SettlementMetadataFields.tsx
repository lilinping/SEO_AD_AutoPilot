"use client";

import { SettlementBankRailFields } from "@/components/SettlementBankRailFields";
import { SettlementRecipientFields } from "@/components/SettlementRecipientFields";

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

export function SettlementMetadataFields({
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
      <SettlementRecipientFields
        visibleMetadataFields={visibleMetadataFields}
        executionForm={executionForm}
        onExecutionFormChange={onExecutionFormChange}
        getMetadataFieldPlaceholder={getMetadataFieldPlaceholder}
      />
      <SettlementBankRailFields
        visibleMetadataFields={visibleMetadataFields}
        executionForm={executionForm}
        onExecutionFormChange={onExecutionFormChange}
        getMetadataFieldPlaceholder={getMetadataFieldPlaceholder}
      />
    </>
  );
}
