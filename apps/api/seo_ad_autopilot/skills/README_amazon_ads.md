# Amazon Ads Report Skill

基于 ClawHub `linkfox-amazon-ads-report` skill 的 Python 包装器。

## 架构说明

```
SEO_AD_BOT/
├── OpenClaw/skills/
│   ├── linkfox-amazon-ads-report/    # ClawHub skill (参考实现)
│   │   ├── SKILL.md                  # 完整使用文档
│   │   ├── scripts/
│   │   │   ├── get_report.py         # 主脚本
│   │   │   └── check_auth_dependency.py
│   │   └── references/
│   │       └── report-types/         # 报告类型元数据
│   │           ├── sp/               # SP 报告 (7个)
│   │           ├── sb/               # SB 报告 (9个)
│   │           └── sd/               # SD 报告 (6个)
│   └── linkfox-amazon-ads-auth/      # 授权依赖
│       └── scripts/
│           ├── authorize_url.py
│           ├── authorized_stores.py
│           └── refresh_token.py
│
└── apps/api/seo_ad_autopilot/
    └── skills/
        └── amazon_ads_report.py      # Python 包装器
```

## 使用流程

### 1. 授权账号（首次使用）

```python
from apps.api.seo_ad_autopilot.skills import AmazonAdsReportSkill

skill = AmazonAdsReportSkill()

# 列出已授权账号
stores = skill.list_authorized_stores()
# 返回: {"stores": [{"profileId": 123, "accountInfoName": "My Store", "countryCode": "US", ...}]}
```

### 2. 获取报告

```python
from apps.api.seo_ad_autopilot.skills import AmazonAdsReportSkill, SkillInput

skill = AmazonAdsReportSkill()

# 方式1: 自动从 reference 查找元数据
result = skill.execute(SkillInput(params={
    "profileId": 1234567890,
    "reportTypeId": "spCampaigns",
    "startDate": "2026-04-27",
    "endDate": "2026-05-03",
}))

# 方式2: 显式指定所有参数
result = skill.execute(SkillInput(params={
    "profileId": 1234567890,
    "region": "NA",
    "reportTypeId": "spSearchTerm",
    "adProduct": "SPONSORED_PRODUCTS",
    "groupBy": ["searchTerm"],
    "columns": ["searchTerm", "keyword", "matchType", "impressions", "clicks", "cost"],
    "startDate": "2026-04-01",
    "endDate": "2026-04-30",
    "timeUnit": "SUMMARY",
    "filters": [{"field": "keywordType", "values": ["BROAD", "PHRASE", "EXACT"]}],
}))
```

### 3. 查看可用报告类型

```python
# 列出所有 SP 报告
report_types = skill.get_report_types("SPONSORED_PRODUCTS")
# 返回: {"sp": ["spAdvertisedProduct", "spCampaigns", "spGrossAndInvalids", ...]}

# 获取特定报告的元数据
metadata = skill.get_report_metadata("spCampaigns", "SPONSORED_PRODUCTS")
# 返回: ReportMetadata(ad_product="SPONSORED_PRODUCTS", group_by=["campaign"], ...)
```

## 默认条件

根据 SKILL.md 文档，当用户未指定时：

| 条件 | 默认规则 |
|------|---------|
| `timeUnit` | 日期跨度 ≤ 7天 → `DAILY`；> 7天 → `SUMMARY` |
| `columns` 身份维度 | `DAILY` 时含 `date`；`SUMMARY` 时含 `startDate` + `endDate` |
| `columns` 基础指标 | `impressions` / `clicks` / `cost` |
| `columns` 归因指标 | 仅当用户提到"销售/转化/ROI/ACOS"时追加 |
| `filters` | 不加（全量返回） |
| `groupBy` | 取 frontmatter groupBy 数组第一个值 |

## 响应格式

成功：
```json
{
  "success": true,
  "reportId": "4ee811a0-...",
  "reportTypeId": "spCampaigns",
  "startDate": "2026-04-28",
  "endDate": "2026-05-04",
  "downloadPath": "/tmp/report_data.json",
  "extractedFileHttpUrl": "http://127.0.0.1:51234/download",
  "extractedFileHttpServeSeconds": 300
}
```

失败：
```json
{
  "success": false,
  "error": "Upstream HTTP 400",
  "httpStatus": 400
}
```

## 错误处理

| 状态 | 含义 | 建议 |
|------|------|------|
| `DEPENDENCY_MISSING` | 未安装 linkfox-amazon-ads-auth | 先安装依赖 |
| `HTTP 401` | accessToken 过期 | 调 refresh_token.py |
| `HTTP 403` | 权限不足 | 检查账号关联 |
| `HTTP 400` | 日期跨度超限 | 拆分拉取后合并 |
| `STILL_PROCESSING` | 报告仍在生成 | 用 reportId 续跑 |

## 参考文档

完整使用说明请参考：
- `OpenClaw/skills/linkfox-amazon-ads-report/SKILL.md`
- `OpenClaw/skills/linkfox-amazon-ads-auth/SKILL.md`
