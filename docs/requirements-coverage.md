# SEO-AD AutoPilot 需求覆盖矩阵

说明：
- 这是按四份需求文档逐条对照当前实现的覆盖表，不是功能宣传页。
- 状态只有三档：`已完成`、`部分完成`、`未完成`。
- 判定原则：只要外部真实接入、自动写入、生产级观测或完整回归链路缺一项，就记为 `部分完成`，不按“看起来能用”算完成。

## 1. MVP 开发任务清单覆盖

| 任务 | 状态 | 说明 |
|---|---|---|
| E1-01 URL 输入、任务创建、项目存档 | 已完成 | 已有项目创建、任务流、项目存档与控制台入口 |
| E1-02 页面抓取、截图、HTML/DOM 获取 | 部分完成 | Playwright 抓取已具备诊断回传并输出截图/HTML artifact 引用（attempt/failureCode/timeout/UA），并新增 `/api/projects/{id}/crawl/diagnostics` 直接回传 snapshot、anti-bot 诊断与 HTML/截图 artifact，`/api/projects/{id}/crawl/diagnostics/history` 与 `/api/crawl/diagnostics/history` 可回放最近抓取记录；总览页也能看到 crawl 诊断历史；但仍以 opt-in 和 fallback 为主 |
| E1-03 超时、重试、UA、基础反爬 | 部分完成 | 已补抓取超时/重试/UA/backoff/jitter、额外 headers、代理池轮换（支持单代理与多代理配置）与 anti-bot 阻断特征识别；并新增项目级 runtime 覆盖（timeout/retry/UA/headers/proxy/js），支持站点级策略差异化；同时补 Playwright anti-bot 人工介入冷却窗口（含连续阻断动态放大与上限封顶）、retry 阶段对 anti-bot cooldown/manual-intervention 自动跳过；反爬策略仍需继续完善 |
| E1-04 Meta、Heading、链接、图片信息提取 | 已完成 | 站点画像与技术 SEO 报告已输出相关结构化字段 |
| E2-01 Business Classifier Prompt/规则 | 已完成 | 已形成独立可配置的站点分类规则库与可审计分类报表 |
| E2-02 页面模板分类 | 已完成 | 首页、类目、商品、内容页等模板分类已落到画像/报告链路 |
| E2-03 StyleExtractor | 已完成 | 已形成独立风格抽取报表，可输出稳定的风格 token 与模块指导 |
| E2-04 SiteProfile JSON 落库 | 已完成 | SiteProfile/Project 结构已实现并可持久化 |
| E3-01 趋势/新闻/问答检索源 | 已完成 | 已接入 `trend/news/qa` 多源 provider 适配层，支持 strict 模式与 fallback 区分 |
| E3-02 相关性评分与价值评分 | 已完成 | 机会评分与风险评分已落在分析/策略链路 |
| E3-03 AdaptiveComponentGenerator | 已完成 | 已形成可复用的自适应组件建议报表，与预览和回滚路径闭环 |
| E3-04 Preview HTML / 截图对比 | 已完成 | 预览 diff 与页面对比已在控制台呈现 |
| E3-05 TechnicalSeoPatcher MVP | 已完成 | 发布阶段已输出结构化 `patchAudit`，并与 writeback target / provider artifact 绑定，支持严格模式阻断与审计追踪 |
| E4-01 广告适配等级模型 | 已完成 | 已有 A/B/C/D 与 no-ad 判断输出 |
| E4-02 AdSlotAuditor | 已完成 | 已加入页面级位点验证、模板覆盖和可回滚判断 |
| E4-03 广告类型推荐规则 | 已完成 | 原生/信息流/赞助位等建议已输出 |
| E4-04 至少一种 Provider 集成样例 | 已完成 | 已新增 `ad_network` 真实 connector（probe/refresh/status/failureCode/fallback）并接入 AD 审计展示；同时补充 billing gateway export，输出可落地的 nginx/caddy/HAProxy 片段 |
| E5-01 任务详情页与方案卡片 | 已完成 | 项目详情、策略页、监控页已能查看策略输出 |
| E5-02 页面前后对比预览 | 已完成 | PreviewDiff 与相关页面已可用 |
| E5-03 Approval Gateway 状态机 | 已完成 | 审批流、批量审批、风险门禁已实现，strict 阻断时可输出结构化 blocker 明细（provider/status/failureCode/fallbackReason） |
| E5-04 审计日志与审批意见 | 已完成 | 审计与运行历史已保留，并增加 connector/deploy/retry/remediation 的 span/trace 字段 |
| E6-01 GitHub PR / Patch 输出 | 已完成 | GitHub PR 写回支持真实 provider 调用，strict 模式下失败直接阻断并保留失败码 |
| E6-02 通用 Script 输出格式 | 已完成 | Script 写回支持真实 endpoint 调用，缺配置/失败时可审计且 strict 模式不伪成功 |
| E6-03 基础指标回传 | 已完成 | 已接通 Search Console/GA4 指标注入，并新增项目级指标快照历史查询接口 `/api/projects/{id}/metrics`；`MetricSnapshot` 现已补 `sourceMetricsSummary`，直接汇总 Search Console/GA4/AD 的主指标、认证来源与 fallback 原因 |
| E6-04 回滚指令与记录 | 已完成 | 已有回滚命令、回滚记录与任务状态流，项目详情页现已补 `rollbackHistory` 可审计每次回滚的原因、窗口、命令与关联任务；并新增 `/api/projects/{id}/deployments`、`/api/projects/{id}/rollbacks` 独立历史接口，项目详情页已改为直接消费这两条接口，供控制台与巡航复用 |
| E6-05 异常告警规则 | 已完成 | 已新增阻断/可恢复告警分流与 `/api/alerts` 队列输出 |
| E7 控制台首版页面 | 已完成 | 项目列表、分析结果、方案预览、设置页以及扩展页已实现 |
| E8 样本站回归集、Prompt 版本管理、Skill 回归、截图回归 | 部分完成 | 已新增视觉回归 run 记录，补 baseline/preview/diff artifact、执行模式与任务关联，并增加像素级 diff 统计（含阈值超限比）与外部截图农场 adapter；visual case 现已回链真实 `projectId/projectName/workflowTaskId/deploymentArtifactRef`，并补 `visualFarmProvider/visualFarmRunId/visualFarmEndpoint/visualFarmLatencyMs/screenshotCount/visualFarmStrictBlocked/visualFarmAuthSource`；run 级已补 `farmProvider/connectedCaseCount/strictBlockedCaseCount/failedCaseCount/fallbackCaseCount/notConfiguredCaseCount/configuredEndpointCount/configuredEndpoints/attemptedEndpointCount/attemptedEndpoints/failedEndpoints/providerAttemptCount/averageFarmLatencyMs`，并新增 `/api/visual-regressions/health` 汇总 strict mode、端点配置、最近 run 健康摘要以及 `failureBuckets`（分类/重试性/建议动作），同时新增 `/api/visual-regressions/retry` 与 `/api/visual-regressions/retry/history` 提供失败样本重试与审计追踪，且 retry history 现已支持 `projectId` 项目级过滤；视觉回归现可在 provider 返回截图 URL 时拉取并二进制落库 baseline/preview artifact，且 strict 视觉模式下若截图 URL 不可下载会显式阻断并标记 `VISUAL_FARM_SCREENSHOT_FETCH_FAILED`，若 provider 成功返回但缺少 URL/ArtifactRef 产物引用会显式阻断并标记 `VISUAL_FARM_ARTIFACT_MISSING`；视觉农场凭据现支持 `SEO_AD_BOT_VISUAL_FARM_CREDENTIALS_JSON/SEO_AD_BOT_VISUAL_FARM_SERVICE_ACCOUNT_JSON` 与自定义 `authHeader`；严格发布门禁现已纳入 visual farm probe 新鲜度与阻断故障判定（缺 probe / stale / blocking / zero-connected 均阻断），且 `GET /api/visual-farm/probe` 支持 `projectId` 项目级探测，`GET /api/visual-farm/probe/history` 支持 `projectId/strictMode` 过滤并回放项目级审计，`GET /api/visual-farm/deploy/batch/history` 现也补充 summary 摘要并支持 `projectId` 过滤；worker 现已自动编排 `visual_farm_deployment_batch`（与 probe/regression 同步触发）形成批量下发审计闭环；acceptance 页已补 visual farm runtime readiness 与 probe history 审计；Prompt 版本管理现已支持 `/api/prompts` 写入、版本 upsert 与激活；验收页已新增 real read/write provider evidence 明细卡片，并补 visual run 历史审计卡片与 prompt/skill 质量摘要，以支撑 `real_provider_samples` gate 的可审计追踪；截图农场现已新增 `/api/visual-farm/export` 输出 nginx/caddy/HAProxy 片段以支撑网关落地，但生产部署仍未完全完成 |

## 2. PRD 覆盖

| 主题 | 状态 | 说明 |
|---|---|---|
| 白帽增长、先预览后执行、体验优先、可解释可回滚 | 已完成 | 产品交互与审批/回滚策略已按该原则设计 |
| 输入 URL / 仓库 / CMS / Script 接入 | 部分完成 | URL 与连接模型已在，GitHub/CMS/Script 已具备独立 connector 且支持多 endpoint 顺序探测、失败回传、连接级最近成功/失败时间戳，以及项目级/工作区级连接调用历史视图（含 `authSource`、`latencyMs`、`fallbackReason`、汇总 `provider/status/action/failureCode` 计数，接口为 `/api/projects/{id}/connections/history`、`/api/connectors/history`，且 `connector.refreshed` 刷新事件也会显式记录认证来源；项目级历史现在也支持 `provider/status/action` 过滤，和工作区级保持一致）；同时连接对象已显式输出 `providerMode`、`strictEligible`、`blockingReason`，并新增 `recentEvidenceLabel/recentEvidenceRef/recentEvidenceAt` 直接标识最近一次真实命中的站点/属性/repo/草稿/脚本证据；Search Console/GA4 现已额外支持 `credentialsJson`/`serviceAccountJson` 直连凭据解析，trend/news/qa 市场读源也已支持 `*_PROVIDER_CREDENTIALS_JSON/*_PROVIDER_SERVICE_ACCOUNT_JSON` 与自定义 `authHeader`，GitHub/CMS/Script 的 probe+writeback 也已支持 `credentialsJson/serviceAccountJson` 与自定义 `authHeader`；默认连接判定现已识别 GitHub/CMS/Script 的 `*_CREDENTIALS_JSON/*_SERVICE_ACCOUNT_JSON` 环境凭据，并支持通过 `SEO_AD_BOT_CMS_PROVIDER_URL` 提供 CMS 默认草稿端点以避免启动即 missing-credentials；现已新增项目级 `/api/projects/{id}/connections/evidence` 与工作区级 `/api/connectors/evidence` 独立证据报告，且工作区报告额外补 `providerSummaries`，并支持 `provider/mode/strictOnly/limit` 过滤，便于监控/巡航按 provider 精准观察真实证据覆盖；项目级/工作区级健康视图也会汇总 real/fallback/unconfigured/strict-ready/strict-gap 统计，并新增 provider 维度覆盖统计、strict-ready project 计数与占比、strict-ready project 样本（ID/名称/URL）、blocking project 计数与占比、top blocking provider 排名、top strict-gap provider 排名、top strict-ready provider 排名，以及工作区级 real-connected / real-connected rate / zero-real / zero-real rate / zero-strict / zero-strict rate / strict-ready / strict-ready rate / partial-strict / partial-strict rate / fully-strict / fully-strict rate provider 列表，另含主失败类别/主失败码/主阻断原因汇总、provider 级建议动作、受影响项目样本（ID/名称/URL）、real coverage / strict coverage / blocking rate 比例，并补充 read/write 分层的 real/strict 覆盖率指标与 `readRealLastEvidenceAt/writeRealLastEvidenceAt` 最近真实证据时间戳（项目级 `connectors/health` 也补齐同名字段）；严格发布门禁现已补 read provider 证据新鲜度校验（`search_console/ga4/sitemap/playwright` 过期会阻断，failureCode=`*_EVIDENCE_STALE`），前端可直接识别真实 provider 与 fallback/未就绪状态；仍需扩大真实生产环境接通范围 |
| 网站识别、诊断、站点成熟度评分 | 已完成 | SiteProfile、技术 SEO、风险与评分已实现 |
| 内容机会发现与内容模块生成 | 部分完成 | 已有内容策略与预览，并支持 trend/news/qa 多 endpoint 拉取、sourceRef 结构化与非 strict synthetic 降级；真实 market evidence 现已直接驱动 SEO 机会生成，并会直接进入 `ContentStrategyReport.marketSignals`、追加 trend/news/qa 导向的 cluster 与 calendar 条目；项目详情的 `MarketEvidenceReport` 也已补 `summaries`，可直接审计 connected/synthetic/failed、最近抓取时间、认证来源与 fallback 原因，且新增项目级 `/api/projects/{id}/market-evidence/health` 作为 strict/fresh 健康摘要；仍需扩大生产可用源覆盖 |
| 技术 SEO 修补 | 部分完成 | 已补发布前后 DOM/meta/schema 关键字段审计（含 patchAudit、verifiedPatch、patch manifest artifact 绑定）；真实大规模外部写回覆盖仍需继续扩展 |
| 广告适配、广告位审计、广告主匹配 | 部分完成 | 审计和建议有了，且 `AdAuditReport` 现已补充报告级 `negativeConditions` 与建议级负例条件，能直接解释“不建议接广告”与“何时阻断该广告位”；真实 provider/结算/回传未完成 |
| 代码级接入、CMS 接入、Universal Script、手工导入 | 部分完成 | 控制台和产物记录已支持，`DeploymentRecord` 现已补 `writebackSummary`，可直接查看写回 provider、success/failed/skipped、last endpoint、successful/failed endpoints 与 average latency；项目详情页也新增 `deploymentHistory` 时间线，可回放同站点历史部署记录、任务状态、审批状态、回滚 ID 与时间戳；但未形成全量接入闭环 |
| 审批网关 | 已完成 | 已有审批、批量审批、风险阈值与任务状态机 |
| 监控与告警 | 部分完成 | 已新增规则引擎、Webhook 多通道路由、On-call policy 路由（primary/escalation）与审计，并提供项目级与全局连接健康视图（`/api/projects/{id}/connectors/health`、`/api/connectors/health`，后者支持 `projectId` 过滤），新增告警投递审计视图（`/api/alerts/deliveries`，支持 `projectId` 过滤）和轮值覆盖视图（`/api/alerts/oncall/coverage`，支持 `projectId` 上下文）；`/api/alerts` 与 `/api/alerts/latest` 也支持 `projectId` 单项目过滤并回传 `projectId`，方便控制台直接查看当前项目的 blocking/recoverable 告警；控制台 Settings、Monitor 与 Acceptance 都已暴露 on-call policy 编辑/总览，且 Monitor 和 Acceptance 也已补 alert rules 总览，同时 Acceptance 也补了 observability readiness 面板、alert delivery audit、deployment audit 与 acceptance snapshot trail，并将告警投递就绪纳入验收 gate；已补 workspace/project 级 market-evidence health 视图（`/api/market-evidence/health`、`/api/projects/{id}/market-evidence/health`）与项目样本定位；`/api/connectors/retry/history` 与 `/api/connectors/remediations` 现已显式回传 `strictMode`，且 `connectors.retry/history` 也支持 `projectId` 项目级过滤，用于区分 strict/non-strict 运行语义下的重试与修复建议；`/api/connectors/bulk-actions/history` 也已补齐 `projectId` 项目级回放与返回体上下文，便于按项目回溯批量修复动作；`/api/alerts/presets`、`/api/alerts/emit/status`、`/api/alerts/emit/history`、`/api/connectors/failures`、`/api/connectors/history` 与 `/api/connectors/evidence` 也补齐 `projectId` 项目级回放，其中 history / evidence 还回传 `projectId`，便于按项目定位连接历史与真实证据覆盖；`/api/visual-regressions/runs`、`/api/visual-regressions/health`、`/api/visual-farm/status` 与 `/api/visual-regressions/remediations` 也已补齐 `projectId` 项目级回放，可按项目过滤视觉回归 run/case、视觉健康/状态与 remediation；`alerts` history/emit history 还回传 `projectIds` 关联集合，便于按项目定位重复告警投递/抑制记录；已补 PagerDuty Events API、Opsgenie Alerts API、Splunk On-Call/VictorOps、Grafana OnCall、Linear issue 创建、Asana task 创建、ManageEngine ServiceDesk ticket 创建、BMC Helix incident 创建、monday.com item 创建、ClickUp task 创建、Redmine issue 创建、Zoho Desk ticket 创建、GitLab issue 创建、YouTrack issue 创建、Freshdesk ticket 创建、Intercom ticket 创建、Trello card 创建、Airtable record 创建、飞书机器人 webhook、钉钉机器人 webhook、企业微信机器人 webhook、Google Chat webhook、Discord webhook、Slack webhook、Teams webhook、Jira issue 创建、ServiceNow incident 创建、Zendesk ticket 创建、Freshservice ticket 创建、Azure DevOps work item 创建、Twilio SMS、Twilio Voice 与 SMTP Email，仍缺更多企业告警平台深度集成 |
| 计费与商业模式 | 部分完成 | 已补 workspace 级 billing policy / usage report / commercial-ready gate 与可持久化 plan tier、额度和预算摘要，并新增 settlement policy / settlement preview / settlement readiness / settlement gateway policy / settlement execution history / settlement gateway history；billing report、billing gateway summary、settlement execution 与 dashboard overview 也支持 `projectId` 过滤并回传 `projectId`，settlement history 现也支持 `projectId` 过滤并回传 `projectId`，gateway execution 还可按 project 回放到 dashboard/settings/monitor/acceptance/project 视图；同时已补 env/route-note 驱动的外部 HTTP settlement gateway adapter，支持 token 或 `credentialsJson`/`serviceAccountJson` 凭据解析，非 manual/local/mock provider 只有在真实 endpoint 配置且返回 2xx 时才会 completed，缺 endpoint / HTTP 失败都会显式 blocked/failed；strictProviders=true 且按项目执行结算时，现已强制要求 ad_network 真实且新鲜证据（缺失/过期分别阻断为 `SETTLEMENT_AD_EVIDENCE_MISSING` / `SETTLEMENT_AD_EVIDENCE_STALE`）；但仍未接入具体商业支付网关 SDK 或正式商户结算流程 |
| 多角色、多站点、自动巡航 | 部分完成 | 有多项目与 worker tick，并新增 worker 执行历史接口 `/api/worker/executions`（支持 `projectId/stage/status/action/limit` 过滤，且返回体回传 `projectId`）及 Monitor 页面执行轨迹视图，可审计 queued/completed/failed/requeued/skipped_duplicate；同时新增项目级 `/api/projects/{id}/cruise/health` 和 workspace 级 `/api/worker/cruise/health` 自动巡航健康视图，后者也支持 `projectId` 过滤与回传，可直观看到 auto-cruise 启用项目、due/overdue 项目与最近同步时间；workspace 级 `/api/market-evidence/health`、`/api/template-market`、`/api/billing`、`/api/billing/gateway`、`/api/billing/settlement/execute`、`/api/experiments`、`/api/localization`、`/api/model-gateway` 也支持 `projectId` 过滤与回传；`/api/overview` 也支持 `projectId` 单项目 dashboard 回放，并把 connectors/market/cruise 健康一起收口，且现在也补了 `skillRegression` 全局回归摘要；项目详情页也已补 `runtimeRouteHistory`、`runtimeEdgeDeploymentHistory`、`runtimeEdgeDeploymentBatchHistory`、`billingGatewayHistory`、`modelGatewayHistory`、`connectorHistory`、`connectorFailures`、`visualRegressionRuns`、`visualRegressionHealth`、`visualRegressionRemediation`、`visualFarmStatus`、`visualFarmProbeHistory`、`runtimeIngressBatchHistory` 与 `runtimeIngressBatchHealth`，可直接看单项目运行轨迹、历史路由、连接失败聚合与视觉回归/视觉农场/ingress 状态；其中 runtime-edge/runtime-ingress/visual-farm 的历史接口现在也都补了 summary 汇总字段，便于按项目查看单次轨迹与整体健康；并新增 `/api/runtime-edge/deploy/batch/history` 与 `/api/runtime-ingress/bundle/batch/health` 用于工作区/项目级批量发布健康评估；worker 也已自动下发 `runtime_edge_deployment_batch`、`runtime_ingress_bundle_batch` 与 `visual_farm_deployment_batch`；workspace 级 auto-cruise policy 也已支持 `/api/policy` 写回；`/api/runtime-route/health` 与 `/api/runtime-route/history` 也补齐 `projectId` 回传，便于按项目查看 runtime-ready 与 preview-only 轨迹；并将 `workspace_auto_cruise` 纳入 acceptance gate；但还不是完整的生产巡航编排 |

## 3. 技术架构覆盖

| 架构项 | 状态 | 说明 |
|---|---|---|
| Next.js / React 控制台 | 已完成 | 控制台已落地 |
| FastAPI 主控制面 | 已完成 | API 服务可运行 |
| Playwright 浏览器自动化 | 部分完成 | 已接入，但 opt-in、偏分析侧，未做到完全稳定的全链路服务 |
| Redis 队列 / 异步任务 | 部分完成 | 已补队列去重入队、失败重试、指数退避延迟重排与审计事件（memory/db/redis 均支持 not-before 语义），新增 worker 执行历史 API/控制台筛选视图，并拆出独立 `apps/worker` 服务入口（支持健康探针、状态文件、故障阈值退出）；API/控制台现已补 `worker/service/health` 与 `worker/queue/health`，其中 Redis 队列健康已支持连通性探测（connected/latency/failureCode/error/queueDepth），DB 队列也补了显式 session probe 与 `DB_*` failureCode，并纳入 `runtime_architecture_production` 验收 gate，避免“只配了 redis 但不可达”伪通过；生产编排治理仍需继续完善 |
| PostgreSQL + 对象存储 | 部分完成 | 已补对象存储后端抽象（local/http 可切换）并接入视觉回归产物写入，且支持生产开关强制 Postgres/禁止 SQLite fallback；HTTP artifact store 已支持远端读写（含 token 鉴权）以满足审计回放；仍未完成全量生产部署与迁移治理 |
| LangGraph / 状态机 / 自研编排 | 已完成 | 有 WorkflowService、Coordinator、审批和回滚状态流 |
| OpenTelemetry + Sentry | 部分完成 | 已补严格观测模式（缺依赖/初始化失败可强制报错）并增强 connector/deploy/monitor/rollback 关键链路 span 属性与异常事件；仍需企业级 exporter/告警平台深度落地 |
| 多模型路由 / 模型网关 | 部分完成 | 已补 workspace 级 model gateway policy / readiness report / route editor 与 suite 覆盖摘要，并新增 model gateway replay / history 接口与 dashboard/settings 首页回放视图，可审计 route provider / priority / reason，但尚未接入真实多模型执行层 |

## 4. 全量需求文档覆盖

| 主题 | 状态 | 说明 |
|---|---|---|
| 站点嗅探、画像、模板识别 | 已完成 | 画像与分析链路已存在 |
| SEO 内容策略、topic cluster、内链蓝图 | 已完成 | 内容策略页和接口已实现 |
| AD 位审计、ad-ready / no-ad 判断 | 已完成 | 广告安全与禁投判断已实现 |
| GitHub PR、CMS Draft、Script 发布 | 部分完成 | 三条写回路径均已支持真实调用、失败审计与 endpoint 尝试轨迹（auth source/attempts）；严格发布门禁已补必需写 provider 证据新鲜度校验（`github/cms/script_api` 过期会阻断，failureCode=`*_EVIDENCE_STALE`）；仍需扩大真实外部系统接通覆盖面 |
| 回滚、审计、审批、监控 | 已完成 | 主闭环已打通 |
| 样本回归、视觉回归、策略回归 | 部分完成 | 样本回归、视觉回归 manifest + 运行记录、skill 回归和策略回归已更完整，并已补像素级 diff、外部截图农场 adapter、strict 失败阻断，以及真实项目/工作流任务/部署产物回链；截图农场生产部署仍未完成 |
| 多语言、多站点、模板市场、A/B 实验 | 部分完成 | 已补 workspace 级 experiment policy / readiness report / settings editor，以及 localization policy / readiness report / settings editor、template market policy / readiness report / settings editor，用于控制实验分配、项目范围、locale clusters、模板目录和 rollout readiness；并新增 runtime assignment preview 接口与 project runtime-route 接口，以及 project runtime-route history / workspace runtime-route history / workspace runtime-route health report 与 settings/monitor/acceptance/project/dashboard 视图，可按 project/subject 解析实验 variant，也可按 project/locale/host 解析 localization cluster，并把 experiment/localization/model gateway 汇总到 runtime route；experiment / localization / template market / market evidence / cruise health 这些 workspace 报表现在也支持 `projectId` 过滤与回传；runtime route 现在还会回放 requestPath/requestMethod、gateway route provider/priority 与 runs 记录，便于审计请求入口；同时新增 `GET /api/projects/{id}/runtime-execute` 作为真正的请求执行入口，`block` 会在 middleware 层直接 409，`serve_preview`/`serve_runtime` 会返回实际 served mode/target/artifact，并支持 `responseMode=redirect/render/proxy`、`enforceRuntimeReady=true` 严格运行态门禁、`GET /api/projects/{id}/runtime-execute/preview`，以及 `GET/POST/PUT/PATCH/DELETE /api/projects/{id}/runtime-execute/proxy/{path}` 与 `.../proxy-strict/{path}` 的页面级子路径与写请求透传；proxy 现在会保留关键请求头与上游响应头，且 runtime host 解析已优先 `X-Forwarded-Host`（支持多值链路与端口清洗），便于真实边缘转发；并新增 `GET /api/projects/{id}/runtime-edge/config`、`GET /api/runtime-edge/routes`、`GET /api/runtime-edge/routes/overrides`、`PUT /api/runtime-edge/routes/overrides`、`GET /api/runtime-edge/map`、`GET /api/runtime-edge/export`、`GET /api/runtime-edge/validate`、`GET /api/runtime-edge/rollout-plan`、`POST /api/runtime-edge/rollout/execute`、`GET /api/runtime-edge/rollout/history`（支持 `projectId/stageId/status/strictRoutesOnly` 过滤）、`GET /api/runtime-edge/rollout/remediations`、`POST /api/runtime-edge/probe` 与 `GET /api/runtime-edge/probe/history`，其中 route overrides 可按项目覆盖 `publicPath/proxyPath/strictProxyPath/rewriteRule/upstreamHost`，用于多站点 rewrite/reverse proxy 差异化编排；probe item 已补 `failureCode/fallbackReason/retryable/authSource/provenance` 统一诊断字段，且这些 runtime-edge 汇总报表现在都会回传 `projectId`；严格模式下，runtime-ready 项目的实际 deploy 现在也会要求最近一次 strict runtime-edge probe，不满足则直接阻断，并支持导出/校验项目与工作区级边缘反向代理配置、多站点 host->proxy 路由映射、可直接落地的 Nginx map/Caddy hosts 片段、分阶段（validate/canary/full）发布计划、执行审计、阻断修复建议与健康探测审计，并新增 strict full rollout 必须先有 canary executed 的阻断规则（`CANARY_REQUIRED`）以及 `runtime_edge_rollout_ready` + `runtime_edge_probe_ready` 验收门禁；但真实站点流量接入、边缘层 rewrite/reverse proxy 和多站点生产编排仍未完成 |
| 真实广告平台接入与收益回传 | 部分完成 | 已接入 `ad_network` 真实探测与收益字段（providerFamily、providerName、providerRef、inventoryStatus、impressions、clicks、ctr、fillRate、rpm、estimated/settled daily、monthly、settlement window、currency、policy tier、payout threshold、geo coverage、provider program、revenue provenance、strict eligibility）并支持多 provider 字段别名归一化（如 AdSense/GAM/Mediavine/Ezoic/Freestar/Raptive/Monumetric/PubMatic/Seedtag/GumGum/Sovrn/Sharethrough/RevContent/Outbrain/Taboola/Yieldmo/Teads/Magnite/TripleLift/Index Exchange/Adform/Criteo/Undertone 类返回）；ad network 凭据现支持 `accessToken` 与 `credentialsJson/serviceAccountJson`，且支持 `authHeader` 自定义认证头；workspace settlement 执行在 strictProviders 模式下已绑定 ad_network 证据新鲜度，项目级结算若证据缺失或过期会被显式阻断并审计；同时新增 workspace/project 级 ad audit replay/history 视图，便于按项目回放 ad allowed / no-ad、revenue 与 failureCode；仍需对接更多真实广告平台与生产结算口径 |
| 真实趋势/新闻/问答多源接入 | 部分完成 | 已支持每类多 endpoint 真实拉取与 strict 校验，补 auth source / attempts / timeout 审计字段，支持 trend/news/qa 单源 refresh，并纳入 connections/health/runs 视图；`MarketEvidenceReport.summaries` 现已补 connected endpoints、connected source refs、average latency，可直接审计真实源命中情况；严格发布门禁现已补 trend/news/qa 证据新鲜度校验（超出 `providerEvidenceFreshnessMinutes` 直接阻断，failureCode=`*_EVIDENCE_STALE`）；已修复二次 sync 的 market provider `adapter-missing` 伪错误噪音，仍依赖 fallback，生产覆盖仍需扩大 |

## 5. 结论

当前项目已经完成的是：
- 需求中最核心的“分析 -> 预览 -> 审批 -> 部署/回滚 -> 监控”主闭环。
- 控制台交互、报告页、批量操作、验收页和审计链路。
- 验收门槛 `real_provider_samples` 已按真实证据计数（read/write evidence）判定，不再仅依赖连接状态；strict 模式下还要求证据新鲜度（fresh read/write evidence）达标，避免历史成功样例造成伪通过；同时新增 `market_evidence_freshness` 门禁，将 trend/news/qa 的 connected/fresh 证据纳入验收，避免只看策略页不看内容源新鲜度；并新增 `market_workspace_readiness` 门禁，将工作区级 strict-ready 项目数纳入验收，避免单项目健康掩盖全局退化。
- SEO 内容策略、技术 SEO 建议、广告安全判断的骨架和主要页面。

当前仍未完成的是：
- 真实外部数据源和真实写回链路。
- 生产级可观测性与告警。
- 完整视觉回归与截图农场生产化能力。
- 真实支付/结算网关、深度运行时 A/B 分流与多站点编排等后续版本能力。

已新增 `/api/product-benchmark`，把当前 MVP 能力与成熟产品能力基准对齐，输出 provider、视觉农场、runtime edge、广告回传、结算网关和实验治理的成熟度、证据、缺口与下一步优先级。

下一步只建议按这个矩阵逐项补缺，不再新增文档外功能。
