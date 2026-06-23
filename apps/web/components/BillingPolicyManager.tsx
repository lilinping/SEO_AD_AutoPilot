"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import type {
  WorkspaceBillingPolicyUpdateRequest,
  WorkspaceBillingReport,
  WorkspaceBillingSettlementExecutionHistoryReport,
  WorkspaceBillingSettlementExecutionReport,
  WorkspaceBillingSettlementGatewayPublishReport,
  WorkspaceBillingSettlementProviderRequirementsReport,
} from "@seo-ad-autopilot/contracts";
import {
  executeWorkspaceBillingSettlement,
  getWorkspaceBillingSettlementHistory,
  getWorkspaceBillingSettlementProviderRequirements,
  publishWorkspaceBillingGatewayPolicy,
  updateWorkspaceBillingPolicy,
} from "@/lib/api";
import { SettlementExecutionEditor } from "@/components/SettlementExecutionEditor";
import { StatusPill } from "@/components/StatusPill";

type EditableBillingPolicy = {
  planTier: "starter" | "growth" | "scale" | "enterprise";
  commercialModeEnabled: "true" | "false";
  settlementEnabled: "true" | "false";
  settlementProviderName: string;
  settlementAccountRef: string;
  settlementCurrency: string;
  settlementWindowDays: string;
  settlementHoldbackPercent: string;
  settlementPayoutThresholdCents: string;
  monthlyProjectLimit: string;
  monthlyTaskLimit: string;
  monthlyDeployLimit: string;
  monthlyBudgetCents: string;
  overageBlocking: "true" | "false";
  notes: string;
};

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

type SettlementFieldPreset = Partial<SettlementExecutionForm>;

type SettlementRequirementProfile = WorkspaceBillingSettlementProviderRequirementsReport["entries"][number];
type SettlementConditionalRequirement = SettlementRequirementProfile["conditionalRequirements"][number];

function inferSettlementProvider(
  providerName: string,
): "paypal" | "stripe" | "ach" | "bank_transfer" | "wise" | "payoneer" | "airwallex" | "tipalti" | "hyperwallet" | "ad_network" | "adsense" | "gam" | "mediavine" | "ezoic" | "freestar" | "raptive" | "monumetric" | "other" {
  const normalized = providerName.trim().toLowerCase().replace(/[\s_-]+/g, "");
  if (normalized.includes("paypal")) return "paypal";
  if (normalized.includes("stripe")) return "stripe";
  if (normalized === "ach" || normalized.includes("ach")) return "ach";
  if (normalized.includes("wise")) return "wise";
  if (normalized.includes("payoneer")) return "payoneer";
  if (normalized.includes("airwallex")) return "airwallex";
  if (normalized.includes("tipalti")) return "tipalti";
  if (normalized.includes("hyperwallet")) return "hyperwallet";
  if (normalized.includes("googleadmanager") || normalized.includes("admanager") || normalized === "gam") return "gam";
  if (normalized.includes("adsense")) return "adsense";
  if (normalized.includes("mediavine")) return "mediavine";
  if (normalized.includes("ezoic")) return "ezoic";
  if (normalized.includes("freestar")) return "freestar";
  if (normalized.includes("raptive") || normalized.includes("adthrive")) return "raptive";
  if (normalized.includes("monumetric")) return "monumetric";
  if (normalized.includes("adnetwork")) return "ad_network";
  if (normalized.includes("wiretransfer") || normalized.includes("banktransfer") || normalized.includes("bankpayout")) return "bank_transfer";
  return "other";
}

function defaultExecutionForm(report: WorkspaceBillingReport): SettlementExecutionForm {
  const providerName = report.policy.settlementProviderName || "manual";
  return {
    providerName,
    amountCents: String(report.settlement.settlementDueCents || report.settlement.netSettlementCents || report.settlement.grossEstimatedCents || 0),
    memo: "",
    destinationType: "",
    destinationRef: "",
    beneficiaryName: "",
    beneficiaryEmail: "",
    rail: "",
    countryCode: "",
    recipientType: "",
    externalAccountToken: "",
    iban: "",
    routingNumber: "",
    swiftCode: "",
    companyEntryDescription: "",
  };
}

function buildFallbackRequirementProfile(
  providerKind: ReturnType<typeof inferSettlementProvider>,
): SettlementRequirementProfile | null {
  switch (providerKind) {
    case "paypal":
      return {
        providerName: "paypal",
        providerLabel: "PayPal Payouts",
        destinationTypes: ["paypal_account", "recipient"],
        rails: [],
        requiredFields: ["providerName", "amountCents", "destinationType", "destinationRef", "beneficiaryEmail"],
        metadataFields: [],
        conditionalRequirements: [
          {
            whenField: "destinationType",
            whenValue: "recipient",
            requiredFields: [],
            metadataFields: ["recipientType"],
            notes: ["recipient payouts require metadata.recipientType."],
          },
        ],
        notes: ["Local fallback requirement profile."],
      };
    case "stripe":
      return {
        providerName: "stripe",
        providerLabel: "Stripe Connect",
        destinationTypes: ["connected_account", "external_account"],
        rails: [],
        requiredFields: ["providerName", "amountCents", "destinationType", "destinationRef"],
        metadataFields: [],
        conditionalRequirements: [
          {
            whenField: "destinationType",
            whenValue: "external_account",
            requiredFields: [],
            metadataFields: ["externalAccountToken"],
            notes: ["external_account payouts require metadata.externalAccountToken."],
          },
        ],
        notes: ["Local fallback requirement profile."],
      };
    case "ach":
      return {
        providerName: "ach",
        providerLabel: "ACH Transfer",
        destinationTypes: ["bank_account"],
        rails: ["ach"],
        requiredFields: ["providerName", "amountCents", "destinationType", "destinationRef", "beneficiaryName", "countryCode", "rail"],
        metadataFields: ["companyEntryDescription"],
        conditionalRequirements: [],
        notes: ["Local fallback requirement profile."],
      };
    case "bank_transfer":
      return {
        providerName: "bank_transfer",
        providerLabel: "Bank Transfer",
        destinationTypes: ["bank_account"],
        rails: ["swift", "sepa", "wire"],
        requiredFields: ["providerName", "amountCents", "destinationType", "destinationRef", "beneficiaryName", "countryCode", "rail"],
        metadataFields: [],
        conditionalRequirements: [
          {
            whenField: "rail",
            whenValue: "swift",
            requiredFields: [],
            metadataFields: ["swiftCode"],
            notes: ["swift rail requires metadata.swiftCode."],
          },
          {
            whenField: "rail",
            whenValue: "sepa",
            requiredFields: [],
            metadataFields: ["iban"],
            notes: ["sepa rail requires metadata.iban."],
          },
          {
            whenField: "rail",
            whenValue: "wire",
            requiredFields: [],
            metadataFields: ["routingNumber"],
            notes: ["wire rail requires metadata.routingNumber."],
          },
        ],
        notes: ["Local fallback requirement profile."],
      };
    case "wise":
      return {
        providerName: "wise",
        providerLabel: "Wise Payouts",
        destinationTypes: ["bank_account"],
        rails: ["sepa", "swift", "local"],
        requiredFields: ["providerName", "amountCents", "destinationType", "destinationRef", "beneficiaryName", "countryCode"],
        metadataFields: [],
        conditionalRequirements: [],
        notes: ["Local fallback requirement profile."],
      };
    case "payoneer":
      return {
        providerName: "payoneer",
        providerLabel: "Payoneer Payouts",
        destinationTypes: ["bank_account"],
        rails: ["local", "swift"],
        requiredFields: ["providerName", "amountCents", "destinationType", "destinationRef", "beneficiaryName", "countryCode"],
        metadataFields: [],
        conditionalRequirements: [],
        notes: ["Local fallback requirement profile."],
      };
    case "airwallex":
      return {
        providerName: "airwallex",
        providerLabel: "Airwallex Transfers",
        destinationTypes: ["bank_account"],
        rails: ["local", "swift"],
        requiredFields: ["providerName", "amountCents", "destinationType", "destinationRef", "beneficiaryName", "countryCode"],
        metadataFields: [],
        conditionalRequirements: [],
        notes: ["Local fallback requirement profile."],
      };
    case "tipalti":
      return {
        providerName: "tipalti",
        providerLabel: "Tipalti Payouts",
        destinationTypes: ["bank_account"],
        rails: ["local", "swift"],
        requiredFields: ["providerName", "amountCents", "destinationType", "destinationRef", "beneficiaryName", "countryCode", "rail"],
        metadataFields: [],
        conditionalRequirements: [
          {
            whenField: "rail",
            whenValue: "swift",
            requiredFields: ["rail"],
            metadataFields: ["swiftCode"],
            notes: ["swift rail requires metadata.swiftCode."],
          },
        ],
        notes: ["Local fallback requirement profile."],
      };
    case "hyperwallet":
      return {
        providerName: "hyperwallet",
        providerLabel: "Hyperwallet Payouts",
        destinationTypes: ["bank_account"],
        rails: ["local", "swift"],
        requiredFields: ["providerName", "amountCents", "destinationType", "destinationRef", "beneficiaryName", "countryCode", "rail"],
        metadataFields: [],
        conditionalRequirements: [
          {
            whenField: "rail",
            whenValue: "swift",
            requiredFields: ["rail"],
            metadataFields: ["swiftCode"],
            notes: ["swift rail requires metadata.swiftCode."],
          },
        ],
        notes: ["Local fallback requirement profile."],
      };
    case "ad_network":
      return {
        providerName: "ad_network",
        providerLabel: "Ad Network Settlement",
        destinationTypes: [],
        rails: [],
        requiredFields: ["providerName", "amountCents"],
        metadataFields: [],
        conditionalRequirements: [],
        notes: ["Project-scoped ad settlement requires a project context and real ad evidence.", "Local fallback requirement profile."],
      };
    case "adsense":
      return {
        providerName: "adsense",
        providerLabel: "Google AdSense Settlement",
        destinationTypes: [],
        rails: [],
        requiredFields: ["providerName", "amountCents"],
        metadataFields: [],
        conditionalRequirements: [],
        notes: ["Project-scoped ad settlement requires a project context and real ad evidence.", "Local fallback requirement profile."],
      };
    case "gam":
      return {
        providerName: "gam",
        providerLabel: "Google Ad Manager Settlement",
        destinationTypes: [],
        rails: [],
        requiredFields: ["providerName", "amountCents"],
        metadataFields: [],
        conditionalRequirements: [],
        notes: ["Project-scoped ad settlement requires a project context and real ad evidence.", "Local fallback requirement profile."],
      };
    case "mediavine":
      return {
        providerName: "mediavine",
        providerLabel: "Mediavine Settlement",
        destinationTypes: [],
        rails: [],
        requiredFields: ["providerName", "amountCents"],
        metadataFields: [],
        conditionalRequirements: [],
        notes: ["Project-scoped ad settlement requires a project context and real ad evidence.", "Local fallback requirement profile."],
      };
    case "ezoic":
      return {
        providerName: "ezoic",
        providerLabel: "Ezoic Settlement",
        destinationTypes: [],
        rails: [],
        requiredFields: ["providerName", "amountCents"],
        metadataFields: [],
        conditionalRequirements: [],
        notes: ["Project-scoped ad settlement requires a project context and real ad evidence.", "Local fallback requirement profile."],
      };
    case "freestar":
      return {
        providerName: "freestar",
        providerLabel: "Freestar Settlement",
        destinationTypes: [],
        rails: [],
        requiredFields: ["providerName", "amountCents"],
        metadataFields: [],
        conditionalRequirements: [],
        notes: ["Project-scoped ad settlement requires a project context and real ad evidence.", "Local fallback requirement profile."],
      };
    case "raptive":
      return {
        providerName: "raptive",
        providerLabel: "Raptive Settlement",
        destinationTypes: [],
        rails: [],
        requiredFields: ["providerName", "amountCents"],
        metadataFields: [],
        conditionalRequirements: [],
        notes: ["Project-scoped ad settlement requires a project context and real ad evidence.", "Local fallback requirement profile."],
      };
    case "monumetric":
      return {
        providerName: "monumetric",
        providerLabel: "Monumetric Settlement",
        destinationTypes: [],
        rails: [],
        requiredFields: ["providerName", "amountCents"],
        metadataFields: [],
        conditionalRequirements: [],
        notes: ["Project-scoped ad settlement requires a project context and real ad evidence.", "Local fallback requirement profile."],
      };
    default:
      return null;
  }
}

function buildSettlementPreset(
  providerKind: ReturnType<typeof inferSettlementProvider>,
  requirementProfile?: SettlementRequirementProfile | null,
): SettlementFieldPreset {
  const preferredDestinationType = requirementProfile?.destinationTypes[0] ?? "";
  const preferredRail = requirementProfile?.rails[0] ?? "";
  switch (providerKind) {
    case "paypal":
      return {
        destinationType: preferredDestinationType || "paypal_account",
        rail: preferredRail,
        countryCode: "US",
        recipientType: "EMAIL",
        companyEntryDescription: "",
        externalAccountToken: "",
        iban: "",
        routingNumber: "",
        swiftCode: "",
      };
    case "stripe":
      return {
        destinationType: preferredDestinationType || "connected_account",
        countryCode: "US",
        rail: preferredRail,
        recipientType: "",
        companyEntryDescription: "",
        iban: "",
        routingNumber: "",
        swiftCode: "",
      };
    case "ach":
      return {
        destinationType: preferredDestinationType || "bank_account",
        rail: preferredRail || "ach",
        countryCode: "US",
        recipientType: "",
        externalAccountToken: "",
        iban: "",
        routingNumber: "",
        swiftCode: "",
      };
    case "bank_transfer":
      return {
        destinationType: preferredDestinationType || "bank_account",
        rail: preferredRail || "swift",
        countryCode: "US",
        recipientType: "",
        externalAccountToken: "",
        companyEntryDescription: "",
      };
    case "wise":
      return {
        destinationType: preferredDestinationType || "bank_account",
        rail: preferredRail || "sepa",
        countryCode: "DE",
        recipientType: "",
        externalAccountToken: "",
        companyEntryDescription: "",
      };
    default:
      return {};
  }
}

function parseMetadataFieldKey(raw: string): string {
  return raw.split("(")[0]?.trim() ?? raw.trim();
}

function hasMetadataField(form: SettlementExecutionForm, fieldKey: string): boolean {
  switch (fieldKey) {
    case "recipientType":
      return Boolean(form.recipientType.trim());
    case "externalAccountToken":
      return Boolean(form.externalAccountToken.trim());
    case "companyEntryDescription":
      return Boolean(form.companyEntryDescription.trim());
    case "iban":
      return Boolean(form.iban.trim());
    case "routingNumber":
      return Boolean(form.routingNumber.trim());
    case "swiftCode":
      return Boolean(form.swiftCode.trim());
    default:
      return false;
  }
}

function getVisibleMetadataFields(requirementProfile?: SettlementRequirementProfile | null): string[] {
  return (requirementProfile?.metadataFields ?? []).map(parseMetadataFieldKey);
}

function getActiveConditionalRequirements(
  form: SettlementExecutionForm,
  requirementProfile?: SettlementRequirementProfile | null,
): SettlementConditionalRequirement[] {
  if (!requirementProfile?.conditionalRequirements.length) return [];
  return requirementProfile.conditionalRequirements.filter((rule) => {
    const currentValue =
      rule.whenField === "destinationType"
        ? form.destinationType.trim()
        : rule.whenField === "rail"
          ? form.rail.trim().toLowerCase()
          : "";
    const expectedValue = rule.whenField === "rail" ? rule.whenValue.trim().toLowerCase() : rule.whenValue.trim();
    return Boolean(currentValue) && currentValue === expectedValue;
  });
}

function prettifyRequirementValue(value: string): string {
  return value
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function getMetadataFieldPlaceholder(fieldKey: string): string {
  switch (fieldKey) {
    case "recipientType":
      return "paypal recipient type";
    case "externalAccountToken":
      return "stripe external account token";
    case "companyEntryDescription":
      return "ach company entry description";
    case "iban":
      return "bank transfer iban";
    case "routingNumber":
      return "bank transfer routing number";
    case "swiftCode":
      return "bank transfer swift code";
    default:
      return fieldKey;
  }
}

function getRequirementFieldLabel(fieldKey: string): string {
  switch (fieldKey) {
    case "providerName":
      return "provider name";
    case "amountCents":
      return "amount cents";
    case "destinationType":
      return "destination type";
    case "destinationRef":
      return "destination ref";
    case "beneficiaryName":
      return "beneficiary name";
    case "beneficiaryEmail":
      return "beneficiary email";
    case "countryCode":
      return "country code";
    case "rail":
      return "rail";
    case "recipientType":
      return "recipient type";
    case "externalAccountToken":
      return "external account token";
    case "companyEntryDescription":
      return "company entry description";
    case "iban":
      return "IBAN";
    case "routingNumber":
      return "routing number";
    case "swiftCode":
      return "SWIFT code";
    case "projectId":
      return "project id";
    default:
      return prettifyRequirementValue(fieldKey);
  }
}

function getVisibleCoreFields(
  providerKind: ReturnType<typeof inferSettlementProvider>,
  requirementProfile?: SettlementRequirementProfile | null,
  activeConditionalRequirements: SettlementConditionalRequirement[] = [],
): {
  beneficiaryName: boolean;
  beneficiaryEmail: boolean;
  rail: boolean;
  countryCode: boolean;
} {
  const requiredFields = new Set(requirementProfile?.requiredFields ?? []);
  for (const rule of activeConditionalRequirements) {
    for (const field of rule.requiredFields) requiredFields.add(field);
  }
  return {
    beneficiaryName: requiredFields.has("beneficiaryName") || providerKind === "wise",
    beneficiaryEmail: requiredFields.has("beneficiaryEmail") || providerKind === "paypal",
    rail: requiredFields.has("rail") || Boolean(requirementProfile?.rails.length),
    countryCode: requiredFields.has("countryCode") || providerKind === "wise",
  };
}

function buildSettlementMetadata(
  providerKind: ReturnType<typeof inferSettlementProvider>,
  form: SettlementExecutionForm,
  visibleMetadataFields: string[],
): Record<string, unknown> {
  const metadata: Record<string, unknown> = {};
  if (visibleMetadataFields.includes("recipientType") && form.recipientType.trim()) metadata.recipientType = form.recipientType.trim();
  if (visibleMetadataFields.includes("externalAccountToken") && form.externalAccountToken.trim()) metadata.externalAccountToken = form.externalAccountToken.trim();
  if (visibleMetadataFields.includes("companyEntryDescription") && form.companyEntryDescription.trim()) {
    metadata.companyEntryDescription = form.companyEntryDescription.trim();
  }
  if (visibleMetadataFields.includes("iban") && form.iban.trim()) metadata.iban = form.iban.trim();
  if (visibleMetadataFields.includes("routingNumber") && form.routingNumber.trim()) metadata.routingNumber = form.routingNumber.trim();
  if (visibleMetadataFields.includes("swiftCode") && form.swiftCode.trim()) metadata.swiftCode = form.swiftCode.trim();

  if (providerKind === "paypal" && form.recipientType.trim()) metadata.recipientType ??= form.recipientType.trim();
  if (providerKind === "stripe" && form.externalAccountToken.trim()) metadata.externalAccountToken ??= form.externalAccountToken.trim();
  if (providerKind === "ach" && form.companyEntryDescription.trim()) metadata.companyEntryDescription ??= form.companyEntryDescription.trim();
  if (providerKind === "bank_transfer") {
    if (form.iban.trim()) metadata.iban ??= form.iban.trim();
    if (form.routingNumber.trim()) metadata.routingNumber ??= form.routingNumber.trim();
    if (form.swiftCode.trim()) metadata.swiftCode ??= form.swiftCode.trim();
  }
  return metadata;
}

function buildSettlementProviderPayload(
  providerKind: ReturnType<typeof inferSettlementProvider>,
  form: SettlementExecutionForm,
  beneficiaryEmail: string | null,
  visibleMetadataFields: string[],
): Record<string, unknown> {
  const providerPayload: Record<string, unknown> = {};
  if (providerKind === "paypal") {
    if (visibleMetadataFields.includes("recipientType") && form.recipientType.trim()) providerPayload.recipientType = form.recipientType.trim();
    if (beneficiaryEmail) providerPayload.recipientEmail = beneficiaryEmail;
  }
  if (providerKind === "stripe" && visibleMetadataFields.includes("externalAccountToken") && form.externalAccountToken.trim()) {
    providerPayload.externalAccountToken = form.externalAccountToken.trim();
  }
  if (providerKind === "ach" && visibleMetadataFields.includes("companyEntryDescription") && form.companyEntryDescription.trim()) {
    providerPayload.companyEntryDescription = form.companyEntryDescription.trim();
  }
  if (providerKind === "bank_transfer") {
    if (visibleMetadataFields.includes("iban") && form.iban.trim()) providerPayload.iban = form.iban.trim();
    if (visibleMetadataFields.includes("routingNumber") && form.routingNumber.trim()) providerPayload.routingNumber = form.routingNumber.trim();
    if (visibleMetadataFields.includes("swiftCode") && form.swiftCode.trim()) providerPayload.swiftCode = form.swiftCode.trim();
  }
  return providerPayload;
}

function sanitizeExecutionFormForRequirements(
  form: SettlementExecutionForm,
  providerKind: ReturnType<typeof inferSettlementProvider>,
  requirementProfile?: SettlementRequirementProfile | null,
): SettlementExecutionForm {
  const preset = buildSettlementPreset(providerKind, requirementProfile);
  const activeConditionalRequirements = getActiveConditionalRequirements(form, requirementProfile);
  const visibleCoreFields = getVisibleCoreFields(providerKind, requirementProfile, activeConditionalRequirements);
  const visibleMetadataFields = new Set([
    ...getVisibleMetadataFields(requirementProfile),
    ...activeConditionalRequirements.flatMap((rule) => rule.metadataFields.map(parseMetadataFieldKey)),
  ]);
  const allowedDestinationTypes = requirementProfile?.destinationTypes ?? [];
  const allowedRails = requirementProfile?.rails ?? [];

  const destinationType =
    allowedDestinationTypes.length > 0 && form.destinationType.trim() && !allowedDestinationTypes.includes(form.destinationType.trim())
      ? ""
      : form.destinationType;
  const rail =
    allowedRails.length > 0 && form.rail.trim() && !allowedRails.includes(form.rail.trim().toLowerCase())
      ? ""
      : form.rail;

  return {
    ...form,
    destinationType: destinationType || preset.destinationType || "",
    rail: visibleCoreFields.rail ? rail || preset.rail || "" : "",
    countryCode: visibleCoreFields.countryCode ? form.countryCode || preset.countryCode || "" : "",
    beneficiaryName: visibleCoreFields.beneficiaryName ? form.beneficiaryName : "",
    beneficiaryEmail: visibleCoreFields.beneficiaryEmail ? form.beneficiaryEmail : "",
    recipientType: visibleMetadataFields.has("recipientType") ? form.recipientType || preset.recipientType || "" : "",
    externalAccountToken: visibleMetadataFields.has("externalAccountToken") ? form.externalAccountToken || preset.externalAccountToken || "" : "",
    companyEntryDescription: visibleMetadataFields.has("companyEntryDescription")
      ? form.companyEntryDescription || preset.companyEntryDescription || ""
      : "",
    iban: visibleMetadataFields.has("iban") ? form.iban || preset.iban || "" : "",
    routingNumber: visibleMetadataFields.has("routingNumber") ? form.routingNumber || preset.routingNumber || "" : "",
    swiftCode: visibleMetadataFields.has("swiftCode") ? form.swiftCode || preset.swiftCode || "" : "",
  };
}

function areExecutionFormsEqual(a: SettlementExecutionForm, b: SettlementExecutionForm): boolean {
  return (
    a.providerName === b.providerName &&
    a.amountCents === b.amountCents &&
    a.memo === b.memo &&
    a.destinationType === b.destinationType &&
    a.destinationRef === b.destinationRef &&
    a.beneficiaryName === b.beneficiaryName &&
    a.beneficiaryEmail === b.beneficiaryEmail &&
    a.rail === b.rail &&
    a.countryCode === b.countryCode &&
    a.recipientType === b.recipientType &&
    a.externalAccountToken === b.externalAccountToken &&
    a.iban === b.iban &&
    a.routingNumber === b.routingNumber &&
    a.swiftCode === b.swiftCode &&
    a.companyEntryDescription === b.companyEntryDescription
  );
}

function getRequirementCompletionSummary(
  form: SettlementExecutionForm,
  requirementProfile?: SettlementRequirementProfile | null,
): { completed: number; total: number } {
  if (!requirementProfile) return { completed: 0, total: 0 };
  const activeConditionalRequirements = getActiveConditionalRequirements(form, requirementProfile);
  const requiredFields = new Set(requirementProfile.requiredFields);
  const metadataFields = [
    ...requirementProfile.metadataFields.map(parseMetadataFieldKey),
    ...activeConditionalRequirements.flatMap((rule) => rule.metadataFields.map(parseMetadataFieldKey)),
  ];
  for (const rule of activeConditionalRequirements) {
    for (const field of rule.requiredFields) requiredFields.add(field);
  }
  const fieldChecks: Array<boolean> = [];

  if (requiredFields.has("providerName")) fieldChecks.push(Boolean(form.providerName.trim()));
  if (requiredFields.has("amountCents")) fieldChecks.push(Boolean(form.amountCents.trim()));
  if (requiredFields.has("destinationType")) fieldChecks.push(Boolean(form.destinationType.trim()));
  if (requiredFields.has("destinationRef")) fieldChecks.push(Boolean(form.destinationRef.trim()));
  if (requiredFields.has("beneficiaryName")) fieldChecks.push(Boolean(form.beneficiaryName.trim()));
  if (requiredFields.has("beneficiaryEmail")) fieldChecks.push(Boolean(form.beneficiaryEmail.trim()));
  if (requiredFields.has("countryCode")) fieldChecks.push(Boolean(form.countryCode.trim()));
  if (requiredFields.has("rail")) fieldChecks.push(Boolean(form.rail.trim()));
  for (const metadataField of metadataFields) fieldChecks.push(hasMetadataField(form, metadataField));

  return {
    completed: fieldChecks.filter(Boolean).length,
    total: fieldChecks.length,
  };
}

function getSettlementValidationHints(
  providerKind: ReturnType<typeof inferSettlementProvider>,
  form: SettlementExecutionForm,
  requirementProfile?: SettlementRequirementProfile | null,
): string[] {
  const hints: string[] = [];
  const activeConditionalRequirements = getActiveConditionalRequirements(form, requirementProfile);
  const requiredFields = new Set(requirementProfile?.requiredFields ?? []);
  const metadataFields = [
    ...((requirementProfile?.metadataFields ?? []).map(parseMetadataFieldKey)),
    ...activeConditionalRequirements.flatMap((rule) => rule.metadataFields.map(parseMetadataFieldKey)),
  ];
  for (const rule of activeConditionalRequirements) {
    for (const field of rule.requiredFields) requiredFields.add(field);
  }
  const allowedDestinationTypes = requirementProfile?.destinationTypes ?? [];
  const allowedRails = requirementProfile?.rails ?? [];
  if (!form.providerName.trim() || requiredFields.has("providerName")) hints.push(...(!form.providerName.trim() ? [`${getRequirementFieldLabel("providerName")} is required.`] : []));
  if (!form.amountCents.trim() || requiredFields.has("amountCents")) hints.push(...(!form.amountCents.trim() ? [`${getRequirementFieldLabel("amountCents")} is required.`] : []));
  if (!form.destinationType.trim() || requiredFields.has("destinationType")) hints.push(...(!form.destinationType.trim() ? [`${getRequirementFieldLabel("destinationType")} is required.`] : []));
  if (!form.destinationRef.trim() || requiredFields.has("destinationRef")) hints.push(...(!form.destinationRef.trim() ? [`${getRequirementFieldLabel("destinationRef")} is required.`] : []));
  if (requiredFields.has("beneficiaryName") && !form.beneficiaryName.trim()) hints.push(`${getRequirementFieldLabel("beneficiaryName")} is required.`);
  if (requiredFields.has("beneficiaryEmail") && !form.beneficiaryEmail.trim()) hints.push(`${getRequirementFieldLabel("beneficiaryEmail")} is required.`);
  if (requiredFields.has("countryCode") && !form.countryCode.trim()) hints.push(`${getRequirementFieldLabel("countryCode")} is required.`);
  if (requiredFields.has("rail") && !form.rail.trim()) hints.push(`${getRequirementFieldLabel("rail")} is required.`);
  if (allowedDestinationTypes.length > 0 && form.destinationType.trim() && !allowedDestinationTypes.includes(form.destinationType.trim())) {
    hints.push(`Destination type must be ${allowedDestinationTypes.join(" or ")}.`);
  }
  if (allowedRails.length > 0 && form.rail.trim() && !allowedRails.includes(form.rail.trim().toLowerCase())) {
    hints.push(`Rail must be ${allowedRails.join(", ")}.`);
  }
  for (const metadataField of metadataFields) {
    if (!hasMetadataField(form, metadataField)) {
      hints.push(`${getRequirementFieldLabel(metadataField)} is required.`);
    }
  }
  return hints;
}

function toEditable(report: WorkspaceBillingReport): EditableBillingPolicy {
  return {
    planTier: report.policy.planTier,
    commercialModeEnabled: report.policy.commercialModeEnabled ? "true" : "false",
    settlementEnabled: report.policy.settlementEnabled ? "true" : "false",
    settlementProviderName: report.policy.settlementProviderName,
    settlementAccountRef: report.policy.settlementAccountRef ?? "",
    settlementCurrency: report.policy.settlementCurrency,
    settlementWindowDays: String(report.policy.settlementWindowDays),
    settlementHoldbackPercent: String(report.policy.settlementHoldbackPercent),
    settlementPayoutThresholdCents: String(report.policy.settlementPayoutThresholdCents),
    monthlyProjectLimit: String(report.policy.monthlyProjectLimit),
    monthlyTaskLimit: String(report.policy.monthlyTaskLimit),
    monthlyDeployLimit: String(report.policy.monthlyDeployLimit),
    monthlyBudgetCents: String(report.policy.monthlyBudgetCents),
    overageBlocking: report.policy.overageBlocking ? "true" : "false",
    notes: report.policy.notes.join("\n"),
  };
}

function asInteger(raw: string, fallback: number): number {
  const value = Number(raw);
  if (Number.isNaN(value)) return fallback;
  return Math.max(0, Math.trunc(value));
}

export function BillingPolicyManager({
  report,
  initialProjectId = "",
  initialProjectLabel = "",
}: {
  report: WorkspaceBillingReport;
  initialProjectId?: string;
  initialProjectLabel?: string;
}) {
  const router = useRouter();
  const [form, setForm] = useState<EditableBillingPolicy>(() => toEditable(report));
  const [historyProjectId, setHistoryProjectId] = useState(initialProjectId);
  const [message, setMessage] = useState("Ready");
  const [gatewayPublish, setGatewayPublish] = useState<WorkspaceBillingSettlementGatewayPublishReport | null>(null);
  const [settlementHistory, setSettlementHistory] = useState<WorkspaceBillingSettlementExecutionHistoryReport>({ total: 0, entries: [] });
  const [lastExecution, setLastExecution] = useState<WorkspaceBillingSettlementExecutionReport | null>(null);
  const [providerRequirements, setProviderRequirements] = useState<WorkspaceBillingSettlementProviderRequirementsReport | null>(null);
  const [executionForm, setExecutionForm] = useState<SettlementExecutionForm>(() => defaultExecutionForm(report));
  const [isPending, startTransition] = useTransition();

  const commercialStatus = useMemo(() => (report.commercialReady ? "ready" : "not ready"), [report.commercialReady]);
  const settlementProviderKind = useMemo(() => inferSettlementProvider(executionForm.providerName || form.settlementProviderName), [executionForm.providerName, form.settlementProviderName]);
  const selectedRequirementProfile = useMemo(
    () => providerRequirements?.entries.find((entry) => entry.providerName === settlementProviderKind) ?? null,
    [providerRequirements, settlementProviderKind],
  );
  const effectiveRequirementProfile = useMemo(
    () => selectedRequirementProfile ?? buildFallbackRequirementProfile(settlementProviderKind),
    [selectedRequirementProfile, settlementProviderKind],
  );
  const activeConditionalRequirements = useMemo(
    () => getActiveConditionalRequirements(executionForm, effectiveRequirementProfile),
    [executionForm, effectiveRequirementProfile],
  );
  const visibleMetadataFields = useMemo(
    () => [
      ...new Set([
        ...getVisibleMetadataFields(effectiveRequirementProfile),
        ...activeConditionalRequirements.flatMap((rule) => rule.metadataFields.map(parseMetadataFieldKey)),
      ]),
    ],
    [effectiveRequirementProfile, activeConditionalRequirements],
  );
  const visibleCoreFields = useMemo(
    () => getVisibleCoreFields(settlementProviderKind, effectiveRequirementProfile, activeConditionalRequirements),
    [effectiveRequirementProfile, settlementProviderKind, activeConditionalRequirements],
  );
  const requirementCompletion = useMemo(
    () => getRequirementCompletionSummary(executionForm, effectiveRequirementProfile),
    [executionForm, effectiveRequirementProfile],
  );
  const settlementValidationHints = useMemo(
    () => getSettlementValidationHints(settlementProviderKind, executionForm, effectiveRequirementProfile),
    [settlementProviderKind, executionForm, effectiveRequirementProfile],
  );

  useEffect(() => {
    let mounted = true;
    void getWorkspaceBillingSettlementHistory(5, historyProjectId)
      .then((history) => {
        if (mounted) setSettlementHistory(history);
      })
      .catch(() => {
        if (mounted) setSettlementHistory({ total: 0, entries: [] });
      });
    return () => {
      mounted = false;
    };
  }, [historyProjectId, report.generatedAt]);

  useEffect(() => {
    let mounted = true;
    void getWorkspaceBillingSettlementProviderRequirements()
      .then((result) => {
        if (mounted) setProviderRequirements(result);
      })
      .catch(() => {
        if (mounted) setProviderRequirements(null);
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    setHistoryProjectId(initialProjectId);
  }, [initialProjectId]);

  useEffect(() => {
    setExecutionForm((current) => {
      const next = {
        ...current,
        providerName: current.providerName || form.settlementProviderName,
        amountCents: current.amountCents || String(report.settlement.settlementDueCents || report.settlement.netSettlementCents || 0),
      };
      return areExecutionFormsEqual(current, next) ? current : next;
    });
  }, [form.settlementProviderName, report.settlement.settlementDueCents, report.settlement.netSettlementCents]);

  useEffect(() => {
    setExecutionForm((current) => {
      const next = {
        ...current,
        ...buildSettlementPreset(settlementProviderKind, effectiveRequirementProfile),
        providerName: current.providerName || form.settlementProviderName,
        amountCents: current.amountCents || String(report.settlement.settlementDueCents || report.settlement.netSettlementCents || 0),
      };
      return areExecutionFormsEqual(current, next) ? current : next;
    });
  }, [settlementProviderKind, effectiveRequirementProfile, form.settlementProviderName, report.settlement.settlementDueCents, report.settlement.netSettlementCents]);

  useEffect(() => {
    setExecutionForm((current) => {
      const next = sanitizeExecutionFormForRequirements(
        {
          ...current,
          providerName: current.providerName || form.settlementProviderName,
        },
        settlementProviderKind,
        effectiveRequirementProfile,
      );
      return areExecutionFormsEqual(current, next) ? current : next;
    });
  }, [settlementProviderKind, effectiveRequirementProfile, form.settlementProviderName]);

  useEffect(() => {
    setExecutionForm((current) => {
      const next = sanitizeExecutionFormForRequirements(current, settlementProviderKind, effectiveRequirementProfile);
      return areExecutionFormsEqual(current, next) ? current : next;
    });
  }, [executionForm.destinationType, executionForm.rail, settlementProviderKind, effectiveRequirementProfile]);

  async function save() {
    setMessage("Saving billing policy...");
    try {
      const payload: WorkspaceBillingPolicyUpdateRequest = {
        planTier: form.planTier,
        commercialModeEnabled: form.commercialModeEnabled === "true",
        settlementEnabled: form.settlementEnabled === "true",
        settlementProviderName: form.settlementProviderName.trim() || "manual",
        settlementAccountRef: form.settlementAccountRef.trim() || null,
        settlementCurrency: form.settlementCurrency.trim() || "USD",
        settlementWindowDays: asInteger(form.settlementWindowDays, report.policy.settlementWindowDays),
        settlementHoldbackPercent: asInteger(form.settlementHoldbackPercent, report.policy.settlementHoldbackPercent),
        settlementPayoutThresholdCents: asInteger(form.settlementPayoutThresholdCents, report.policy.settlementPayoutThresholdCents),
        monthlyProjectLimit: asInteger(form.monthlyProjectLimit, report.policy.monthlyProjectLimit),
        monthlyTaskLimit: asInteger(form.monthlyTaskLimit, report.policy.monthlyTaskLimit),
        monthlyDeployLimit: asInteger(form.monthlyDeployLimit, report.policy.monthlyDeployLimit),
        monthlyBudgetCents: asInteger(form.monthlyBudgetCents, report.policy.monthlyBudgetCents),
        overageBlocking: form.overageBlocking === "true",
        notes: form.notes
          .split("\n")
          .map((item) => item.trim())
          .filter((item) => item.length > 0),
      };
      const result = await updateWorkspaceBillingPolicy(payload);
      setForm(toEditable(result));
      setMessage(`Saved ${result.policy.planTier} billing policy.`);
      startTransition(() => router.refresh());
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to save billing policy.");
    }
  }

  async function runSettlement(dryRun: boolean) {
    if (!dryRun && settlementValidationHints.length > 0) {
      setMessage(`Blocked by form validation · ${settlementValidationHints[0]}`);
      return;
    }
    setMessage(dryRun ? "Running settlement preview..." : "Executing settlement...");
    try {
      const destinationType = executionForm.destinationType.trim() || null;
      const destinationRef = executionForm.destinationRef.trim() || null;
      const beneficiaryName = executionForm.beneficiaryName.trim() || null;
      const beneficiaryEmail = executionForm.beneficiaryEmail.trim() || null;
      const rail = executionForm.rail.trim() || null;
      const countryCode = executionForm.countryCode.trim().toUpperCase() || null;
      const metadata = buildSettlementMetadata(settlementProviderKind, executionForm, visibleMetadataFields);
      const providerPayload = buildSettlementProviderPayload(settlementProviderKind, executionForm, beneficiaryEmail, visibleMetadataFields);
      const result = await executeWorkspaceBillingSettlement({
        dryRun,
        providerName: executionForm.providerName.trim() || form.settlementProviderName.trim() || report.policy.settlementProviderName,
        accountRef: form.settlementAccountRef.trim() || null,
        currency: form.settlementCurrency.trim() || report.policy.settlementCurrency,
        amountCents: asInteger(executionForm.amountCents, report.settlement.settlementDueCents || report.settlement.netSettlementCents || 0),
        memo: executionForm.memo.trim() || (dryRun ? "Preview from billing policy editor." : "Execution from billing policy editor."),
        projectId: historyProjectId.trim() || null,
        destinationType,
        destinationRef,
        beneficiaryName,
        beneficiaryEmail,
        rail,
        countryCode,
        metadata,
        providerPayload,
      });
      setLastExecution(result);
      setMessage(`${dryRun ? "Preview" : "Execution"} ${result.execution.status} · ${result.execution.message ?? "settlement updated."}`);
      setSettlementHistory((current) => ({ total: Math.min(5, current.total + 1), entries: [result.execution, ...current.entries].slice(0, 5) }));
      startTransition(() => router.refresh());
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to execute settlement.");
    }
  }

  async function publishGateway() {
    setMessage("Publishing settlement gateway...");
    try {
      const result = await publishWorkspaceBillingGatewayPolicy();
      setGatewayPublish(result);
      setMessage(`Published settlement gateway via ${result.providerName} (${result.status}).`);
      startTransition(() => router.refresh());
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Failed to publish settlement gateway.");
    }
  }

  function applySuggestedPreset() {
    setExecutionForm((current) => ({
      ...current,
      ...buildSettlementPreset(settlementProviderKind, effectiveRequirementProfile),
      providerName: current.providerName || form.settlementProviderName,
      amountCents: current.amountCents || String(report.settlement.settlementDueCents || report.settlement.netSettlementCents || 0),
    }));
    setMessage(`Applied ${settlementProviderKind} preset.`);
  }

  return (
    <div className="stack" style={{ marginTop: 12 }}>
      <div className="stat-grid">
        <section className="stat-card stat-card-accent">
          <div className="stat-card-label">Plan tier</div>
          <div className="stat-card-value">{report.policy.planTier}</div>
          <div className="stat-card-caption">Commercial mode {report.policy.commercialModeEnabled ? "enabled" : "disabled"}</div>
        </section>
        <section className="stat-card">
          <div className="stat-card-label">Commercial readiness</div>
          <div className="stat-card-value">{commercialStatus}</div>
          <div className="stat-card-caption">{report.commercialReady ? "Plan and usage are within limits." : "Commercial rollout is not yet ready."}</div>
        </section>
        <section className="stat-card">
          <div className="stat-card-label">Usage / budget</div>
          <div className="stat-card-value">{report.usage.budgetLimitUsedPercent}%</div>
          <div className="stat-card-caption">Estimated {report.usage.estimatedUsageCents} cents this month</div>
        </section>
        <section className="stat-card">
          <div className="stat-card-label">Settlement readiness</div>
          <div className="stat-card-value">{report.settlement.settlementReady ? "ready" : "blocked"}</div>
          <div className="stat-card-caption">{report.settlement.settlementDueCents} cents due · threshold {report.settlement.payoutThresholdCents}</div>
        </section>
        <section className="stat-card">
          <div className="stat-card-label">Settlement gateway</div>
          <div className="stat-card-value">{report.settlementGateway?.gatewayReady ? "ready" : "partial"}</div>
          <div className="stat-card-caption">
            {report.settlementGateway ? `${report.settlementGateway.routeReadyCount}/${report.settlementGateway.routeCount} routes ready` : "No settlement gateway report."}
          </div>
        </section>
      </div>
      <div className="project-foot">
        <span>Policy editor</span>
        <StatusPill tone={report.commercialReady ? "good" : "warn"}>{report.commercialReady ? "commercial-ready" : "needs work"}</StatusPill>
      </div>
      <div className="stack" style={{ marginTop: 12 }}>
        <select value={form.planTier} onChange={(event) => setForm((current) => ({ ...current, planTier: event.target.value as EditableBillingPolicy["planTier"] }))}>
          <option value="starter">starter</option>
          <option value="growth">growth</option>
          <option value="scale">scale</option>
          <option value="enterprise">enterprise</option>
        </select>
        <select
          value={form.commercialModeEnabled}
          onChange={(event) => setForm((current) => ({ ...current, commercialModeEnabled: event.target.value as EditableBillingPolicy["commercialModeEnabled"] }))}
        >
          <option value="true">commercial mode enabled</option>
          <option value="false">commercial mode disabled</option>
        </select>
        <select
          value={form.settlementEnabled}
          onChange={(event) => setForm((current) => ({ ...current, settlementEnabled: event.target.value as EditableBillingPolicy["settlementEnabled"] }))}
        >
          <option value="true">settlement enabled</option>
          <option value="false">settlement disabled</option>
        </select>
        <input
          value={form.settlementProviderName}
          onChange={(event) => setForm((current) => ({ ...current, settlementProviderName: event.target.value }))}
          placeholder="settlement provider name"
        />
        <input
          value={form.settlementAccountRef}
          onChange={(event) => setForm((current) => ({ ...current, settlementAccountRef: event.target.value }))}
          placeholder="settlement account ref"
        />
        <input
          value={form.settlementCurrency}
          onChange={(event) => setForm((current) => ({ ...current, settlementCurrency: event.target.value }))}
          placeholder="settlement currency"
        />
        <input
          value={form.settlementWindowDays}
          onChange={(event) => setForm((current) => ({ ...current, settlementWindowDays: event.target.value }))}
          placeholder="settlement window days"
        />
        <input
          value={form.settlementHoldbackPercent}
          onChange={(event) => setForm((current) => ({ ...current, settlementHoldbackPercent: event.target.value }))}
          placeholder="settlement holdback percent"
        />
        <input
          value={form.settlementPayoutThresholdCents}
          onChange={(event) => setForm((current) => ({ ...current, settlementPayoutThresholdCents: event.target.value }))}
          placeholder="settlement payout threshold cents"
        />
        <input
          value={historyProjectId}
          onChange={(event) => setHistoryProjectId(event.target.value)}
          placeholder="project id (history filter and settlement context)"
        />
        <select
          value={form.overageBlocking}
          onChange={(event) => setForm((current) => ({ ...current, overageBlocking: event.target.value as EditableBillingPolicy["overageBlocking"] }))}
        >
          <option value="true">overage blocking on</option>
          <option value="false">overage blocking off</option>
        </select>
        <input
          value={form.monthlyProjectLimit}
          onChange={(event) => setForm((current) => ({ ...current, monthlyProjectLimit: event.target.value }))}
          placeholder="monthly project limit"
        />
        <input
          value={form.monthlyTaskLimit}
          onChange={(event) => setForm((current) => ({ ...current, monthlyTaskLimit: event.target.value }))}
          placeholder="monthly task limit"
        />
        <input
          value={form.monthlyDeployLimit}
          onChange={(event) => setForm((current) => ({ ...current, monthlyDeployLimit: event.target.value }))}
          placeholder="monthly deploy limit"
        />
        <input
          value={form.monthlyBudgetCents}
          onChange={(event) => setForm((current) => ({ ...current, monthlyBudgetCents: event.target.value }))}
          placeholder="monthly budget cents"
        />
        <textarea
          value={form.notes}
          onChange={(event) => setForm((current) => ({ ...current, notes: event.target.value }))}
          placeholder="notes, one per line"
          rows={4}
        />
      </div>
      <div className="project-foot">
        <span>{report.warnings.length ? report.warnings.join(" · ") : "No billing warnings."}</span>
        <button className="button button-primary" type="button" onClick={() => void save()} disabled={isPending}>
          Save billing policy
        </button>
        <button className="button button-secondary" type="button" onClick={() => void publishGateway()} disabled={isPending}>
          Publish gateway
        </button>
      </div>
      <div className="grid-two">
        <div className="suite-card">
          <div className="project-foot">
            <span>Usage snapshot</span>
            <StatusPill tone={report.usage.overBudgetLimit ? "danger" : "neutral"}>{report.usage.overBudgetLimit ? "over budget" : "within budget"}</StatusPill>
          </div>
          <ul className="metric-list">
            <li>Active projects: {report.usage.activeProjectCount} / {report.policy.monthlyProjectLimit} ({report.usage.projectLimitUsedPercent}%)</li>
            <li>Tasks: {report.usage.taskCount} / {report.policy.monthlyTaskLimit} ({report.usage.taskLimitUsedPercent}%)</li>
            <li>Deploys 30d: {report.usage.deployCount30d} / {report.policy.monthlyDeployLimit} ({report.usage.deployLimitUsedPercent}%)</li>
            <li>Rollbacks 30d: {report.usage.rollbackCount30d}</li>
            <li>Auto deploys 30d: {report.usage.autoDeployCount30d}</li>
            <li>Strict-ready projects: {report.usage.strictReadyProjectCount}</li>
          </ul>
        </div>
        <div className="suite-card">
          <div className="project-foot">
            <span>Recommendations</span>
            <StatusPill tone={report.recommendations.length ? "warn" : "good"}>{report.recommendations.length}</StatusPill>
          </div>
          <ul className="metric-list">
            {report.recommendations.length === 0 ? <li>No recommendations.</li> : report.recommendations.map((item) => <li key={item}>{item}</li>)}
          </ul>
          <div className="project-copy">Usage, settlement, and plan state are persisted in the workspace state directory, so they can gate commercial readiness without a payment provider.</div>
        </div>
        <div className="suite-card">
          <div className="project-foot">
            <span>Settlement preview</span>
            <StatusPill tone={report.settlement.settlementReady ? "good" : report.settlement.settlementBlocked ? "warn" : "neutral"}>
              {report.settlement.settlementReady ? "ready" : report.settlement.settlementBlocked ? "blocked" : "idle"}
            </StatusPill>
          </div>
          <ul className="metric-list">
            <li>Provider: {report.settlement.settlementProviderName}</li>
            <li>Latest execution: {settlementHistory.entries[0]?.createdAt ?? "n/a"}</li>
            <li>Account: {report.settlement.settlementAccountRef ?? "unbound"}</li>
            <li>Currency: {report.settlement.settlementCurrency}</li>
            <li>Window: {report.settlement.settlementWindowDays} days</li>
            <li>Holdback: {report.settlement.settlementHoldbackPercent}%</li>
            <li>Gross estimated: {report.settlement.grossEstimatedCents} cents</li>
            <li>Holdback: {report.settlement.holdbackCents} cents</li>
            <li>Net settlement: {report.settlement.netSettlementCents} cents</li>
            <li>Due now: {report.settlement.settlementDueCents} cents</li>
          <li>Latest request: {settlementHistory.entries[0] ? `${settlementHistory.entries[0].requestMethod ?? "POST"} ${settlementHistory.entries[0].requestPath ?? "/api/billing/settlement/execute"}` : "n/a"}</li>
          <li>Latest due: {settlementHistory.entries[0]?.dueCents ?? "n/a"} cents</li>
          <li>Gateway ready: {settlementHistory.entries[0] ? (settlementHistory.entries[0].gatewayReady ? "yes" : "no") : "n/a"}</li>
          <li>Gateway route: {settlementHistory.entries[0]?.gatewayRouteProviderName ?? "n/a"} · fallback {settlementHistory.entries[0]?.gatewayRouteFallbackProviderName ?? "n/a"} · priority {settlementHistory.entries[0]?.gatewayRoutePriority ?? "n/a"} · reason {settlementHistory.entries[0]?.gatewayRouteReason ?? "n/a"}</li>
            <li>Gateway provider: {settlementHistory.entries[0]?.gatewayProviderName ?? "n/a"}</li>
            <li>Route ready: {settlementHistory.entries[0] ? (settlementHistory.entries[0].gatewayRouteReady ? "yes" : "no") : "n/a"}</li>
            <li>Failure code: {settlementHistory.entries[0]?.failureCode ?? "none"}</li>
            <li>Retryable: {settlementHistory.entries[0] ? (settlementHistory.entries[0].retryable ? "yes" : "no") : "n/a"}</li>
          </ul>
          <div className="project-foot" style={{ marginTop: 12 }}>
            <span>Settlement actions</span>
            <StatusPill tone={lastExecution?.execution.status === "completed" ? "good" : lastExecution?.execution.status === "failed" || lastExecution?.execution.status === "blocked" ? "danger" : "neutral"}>
              {lastExecution ? lastExecution.execution.status : "idle"}
            </StatusPill>
          </div>
          {lastExecution ? (
            <div className="audit-meta" style={{ marginTop: 8 }}>
              {lastExecution.execution.requestMethod ?? "POST"} {lastExecution.execution.requestPath ?? "/api/billing/settlement/execute"} · gateway{" "}
              {lastExecution.execution.gatewayProviderName ?? "n/a"} · route {lastExecution.execution.gatewayRouteProviderName ?? "n/a"} · priority {lastExecution.execution.gatewayRoutePriority ?? "n/a"} · failureCode={lastExecution.execution.failureCode ?? "none"} · retryable={
                lastExecution.execution.retryable ? "yes" : "no"
              } · {lastExecution.execution.dryRun ? "preview" : "live"} · reason {lastExecution.execution.gatewayRouteReason ?? "n/a"} · project{" "}
              {lastExecution.execution.projectName ?? lastExecution.execution.projectId ?? historyProjectId ?? "workspace"}
            </div>
          ) : null}
          <SettlementExecutionEditor
            executionForm={executionForm}
            onExecutionFormChange={setExecutionForm}
            settlementProviderKind={settlementProviderKind}
            settlementValidationHints={settlementValidationHints}
            isPending={isPending}
            onApplyPreset={applySuggestedPreset}
            onPreview={() => void runSettlement(true)}
            onExecute={() => void runSettlement(false)}
            effectiveRequirementProfile={effectiveRequirementProfile}
            selectedRequirementProfile={selectedRequirementProfile}
            requirementCompletion={requirementCompletion}
            visibleCoreFields={visibleCoreFields}
            visibleMetadataFields={visibleMetadataFields}
            activeConditionalRequirements={activeConditionalRequirements}
            prettifyRequirementValue={prettifyRequirementValue}
            getMetadataFieldPlaceholder={getMetadataFieldPlaceholder}
          />
          <div className="project-copy" style={{ marginTop: 12 }}>
            Settlement execution stays local unless the billing provider is connected. Provider-specific fields are collected here and normalized into `providerPayload` for the external gateway.
          </div>
        </div>
      </div>
      {report.settlementGateway ? (
        <>
          <div className="suite-card">
            <div className="project-foot">
              <span>Gateway preview</span>
              <StatusPill tone={report.settlementGateway.gatewayReady ? "good" : "warn"}>
                {report.settlementGateway.gatewayReady ? "ready" : "partial"}
              </StatusPill>
            </div>
            <ul className="metric-list">
              {report.settlementGateway.routes.slice(0, 4).map((route) => (
                <li key={`${route.providerName}-${route.priority}`}>
                  {route.providerName}: {route.resolvedProviderName} ({route.routeReady ? "ready" : "fallback"}) · priority {route.priority}
                </li>
              ))}
            </ul>
          </div>
          <div className="suite-card">
            <div className="project-foot">
              <span>Gateway publish</span>
              <StatusPill tone={gatewayPublish?.status === "completed" ? "good" : gatewayPublish?.status === "failed" ? "danger" : "neutral"}>
                {gatewayPublish?.status ?? "idle"}
              </StatusPill>
            </div>
            <ul className="metric-list">
              <li>Provider: {gatewayPublish?.providerName ?? "n/a"}</li>
              <li>Endpoint: {gatewayPublish?.gatewayEndpoint ?? "n/a"}</li>
              <li>Artifact: {gatewayPublish?.gatewayArtifactId ?? "n/a"}</li>
              <li>URL: {gatewayPublish?.gatewayUrl ?? "n/a"}</li>
              <li>Auth: {gatewayPublish?.authSource ?? "n/a"}</li>
              <li>Failure: {gatewayPublish?.failureCode ?? "none"}</li>
              <li>Retryable: {gatewayPublish?.retryable ? "yes" : "no"}</li>
            </ul>
            <div className="project-copy">{gatewayPublish?.message ?? "No gateway publish executed yet."}</div>
          </div>
        </>
      ) : null}
      <div className="suite-card">
        <div className="project-foot">
          <span>Settlement history</span>
          <StatusPill tone={settlementHistory.entries.length ? "neutral" : "warn"}>{settlementHistory.total}</StatusPill>
        </div>
        {historyProjectId ? (
          <div className="audit-meta" style={{ marginBottom: 12 }}>
            Filtered by project <strong>{initialProjectLabel ? `${initialProjectLabel} (${historyProjectId})` : historyProjectId}</strong>
          </div>
        ) : null}
        <ul className="metric-list">
          {settlementHistory.entries.length === 0 ? (
            <li>No settlement executions yet.</li>
          ) : (
            settlementHistory.entries.slice(0, 5).map((entry) => (
              <li key={entry.auditId}>
                {entry.createdAt} · {entry.status} · {entry.providerName} · gateway {entry.gatewayProviderName ?? "n/a"} · {entry.dueCents} due · {entry.dryRun ? "dry-run" : "live"} ·{" "}
                {entry.requestMethod ?? "POST"} {entry.requestPath ?? "/api/billing/settlement/execute"} · ready {entry.settlementReady ? "yes" : "no"} · gateway{" "}
                {entry.gatewayReady ? "ready" : "partial"} · route {entry.gatewayRouteProviderName ?? "n/a"} · priority {entry.gatewayRoutePriority ?? "n/a"} ({entry.gatewayRouteReady ? "ready" : "fallback"}) · reason {entry.gatewayRouteReason ?? "n/a"} · failure {entry.failureCode ?? "none"} · retryable {entry.retryable ? "yes" : "no"}
                {entry.providerPayload && Object.keys(entry.providerPayload).length ? ` · providerPayload ${Object.keys(entry.providerPayload).join(",")}` : ""}
                {entry.projectId ? (
                  <>
                    {" "}
                    · project <Link href={`/projects/${entry.projectId}`}>{entry.projectName ?? entry.projectId}</Link>
                  </>
                ) : null}
              </li>
            ))
          )}
        </ul>
      </div>
      <div className="alert-box">{message}</div>
    </div>
  );
}
