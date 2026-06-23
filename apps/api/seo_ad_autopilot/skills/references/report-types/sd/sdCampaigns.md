---
reportTypeId: sdCampaigns
adProduct: SPONSORED_DISPLAY
groupBy: ["campaign"]
timeUnit: [DAILY, SUMMARY]
format: GZIP_JSON
dateRange:
  maxSpanDays: 31
  dataRetentionDays: 60
---

# SD Campaigns Report

Performance data for Sponsored Display campaigns.

## Configuration

| Parameter | Value |
|-----------|-------|
| adProduct | SPONSORED_DISPLAY |
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
| sales | Total sales |
| purchases | Total purchases |
| acos | Advertising Cost of Sales |
| roas | Return on Ad Spend |

## Filters

| Filter | Values |
|--------|--------|
| campaignStatus | ENABLED, PAUSED, ARCHIVED |
