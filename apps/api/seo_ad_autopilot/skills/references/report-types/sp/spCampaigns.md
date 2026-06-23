---
reportTypeId: spCampaigns
adProduct: SPONSORED_PRODUCTS
groupBy: ["campaign"]
timeUnit: [DAILY, SUMMARY]
format: GZIP_JSON
dateRange:
  maxSpanDays: 31
  dataRetentionDays: 95
---

# SP Campaigns Report

Performance data for Sponsored Products campaigns.

## Configuration

| Parameter | Value |
|-----------|-------|
| adProduct | SPONSORED_PRODUCTS |
| groupBy | campaign |
| timeUnit | DAILY / SUMMARY |

## Base Metrics

| Column | Description |
|--------|-------------|
| date | Report date (DAILY only) |
| startDate | Report start date (SUMMARY only) |
| endDate | Report end date (SUMMARY only) |
| campaignId | Campaign identifier |
| campaignName | Campaign name |
| impressions | Number of impressions |
| clicks | Number of clicks |
| cost | Total cost (USD) |
| sales7d | Sales attributed within 7 days |
| sales14d | Sales attributed within 14 days |
| purchases7d | Purchases within 7 days |
| purchases14d | Purchases within 14 days |
| acosClicks7d | ACoS (7-day click) |
| acosClicks14d | ACoS (14-day click) |
| roasClicks7d | ROAS (7-day click) |
| roasClicks14d | ROAS (14-day click) |

## Filters

| Filter | Values |
|--------|--------|
| campaignStatus | ENABLED, PAUSED, ARCHIVED |
