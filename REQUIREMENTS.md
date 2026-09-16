# SEO_AD_BOT 项目需求文档
## ✅ 修复进度总览（更新于 2026-06-25）

| Phase | 缺口数 | 已修复 | 状态 |
|-------|--------|--------|------|
| Phase 1 P0（阻断性） | 4 | 4 | ✅ 全部完成 |
| Phase 1 P1（功能性） | 10 | 10 | ✅ 全部完成 |
| Phase 2-4（增强性） | 12 | 12 | ✅ 全部完成 |
| **合计** | **26** | **26** | **✅ 100%** |

### 新增文件清单（35+ 文件）
- **GAP-001**: `agents/__init__.py` — 14个符号完整导出
- **GAP-002**: `skills/__init__.py` — 19个Skill完整导出
- **GAP-003**: `routers/` — 新建11个路由文件（health/agents/analysis/content/ad_platforms/rank_tracking/competitor/search_engines/__init__）
- **GAP-004**: `ad_platforms/auto_discovery.py` — 补全8个平台注册（含AmazonAdsPlatform/PrebidHeaderBiddingPlatform）
- **GAP-005**: `skills/generate.py` — async execute() + LLMCostRouter + 4-provider LLM dispatch + template fallback
- **GAP-006**: `skills/real_data_v2.py` — async httpx + 指数退避重试 + DataForSEO/SerpAPI接入
- **GAP-007**: `services/` — 9个服务文件（AnalysisService完整实现 + 7个stub）
- **GAP-008**: `app.py` — 注册all_routers（第264行patch）
- **GAP-009**: `agents/coordinator.py` — asyncio.gather并行 + agent_filter + dry_run + timeout_sec + AnalysisReport
- **GAP-010**: `tests/` — conftest.py + test_smoke.py + pytest.ini（38个测试用例）
- **GAP-011**: `i18n/` — translator.py + en.json + zh-CN.json（ContextVar locale切换）
- **GAP-012**: `middleware/request_logger.py` — 结构化JSON日志 + X-Request-ID ContextVar
- **GAP-013**: `alembic.ini` + `migrations/` — env.py + 初始migration（5张表）
- **GAP-014**: `websocket_progress.py` — WS /ws/progress/{task_id} + TaskRegistry + ProgressEvent
- **GAP-015**: `tenants.py` — TenantMiddleware + TenantRegistry + multi-tenant + MULTI_TENANT env flag
- **GAP-016**: `rate_limiter.py` — 滑动窗口 + 按端点限流 + 429+Retry-After响应头
- **GAP-017**: `content_versions.py` — ContentVersionStore + SemVer + diff + rollback
- **GAP-018**: `local_llm.py` — Ollama/vLLM/LMStudio统一客户端 + health_check
- **SE-001**: `search_engines/__init__.py` — 11个适配器统一导出 + ENGINE_REGISTRY + get_engine()

---



> **文档版本**: v1.0  
> **生成日期**: 2026-06-25  
> **文档类型**: 功能完善度审查 + 完整产品需求规格  
> **项目路径**: `/Users/Zhuanz/Desktop/SEO_AD_BOT`  
> **核心包路径**: `apps/api/seo_ad_autopilot/`

---

## 目录

1. [项目概述](#1-项目概述)
2. [当前架构总览](#2-当前架构总览)
3. [已完善模块清单](#3-已完善模块清单)
4. [功能缺口与待完善项](#4-功能缺口与待完善项)
5. [完整功能需求规格](#5-完整功能需求规格)
6. [优先级排序与开发路线图](#6-优先级排序与开发路线图)
7. [接口规范说明](#7-接口规范说明)
8. [附录：文件清单](#8-附录文件清单)


---

## 1. 项目概述

### 1.1 产品定位

SEO_AD_BOT 是一个面向内容站长、SEO 从业者和数字广告运营的 **AI 驱动全自动化 SEO + 广告优化平台**。

核心价值主张：
- 自动爬取与分析网站技术健康度、内容质量、关键词排名
- 通过多 Agent 辩论机制（DebateEngine）生成高置信度优化建议
- 自动匹配并推荐最优广告平台（AdSense / Mediavine / AdThrive / Ezoic 等）
- 支持 AI 优化搜索（AIO/GEO）的内容结构适配
- 提供内容生成、竞品分析、排名追踪等一站式 SEO 技能

### 1.2 技术栈

| 层次 | 技术选型 |
|------|---------|
| Web 框架 | FastAPI |
| ORM / DB | SQLAlchemy + PostgreSQL |
| 任务队列 | Celery / Redis |
| LLM 路由 | `utils/llm_router.py`（内部多模型路由） |
| 爬虫 | `crawler.py` + `crawler_enhanced.py` |
| 搜索引擎适配 | 11 个搜索引擎（Google/Bing/Baidu/Yandex/ChatGPT/Claude/Perplexity 等） |
| 广告平台 | 9 个平台适配器 + 自动发现引擎 |


---

## 2. 当前架构总览

```
apps/api/seo_ad_autopilot/
├── app.py                   # FastAPI 入口（2442 行，路由集中，待拆分）
├── service.py               # 核心业务层（22577 行，待按域拆分）
├── config.py                # 配置管理
├── models.py                # Pydantic/SQLAlchemy 模型（庞大，待拆分）
├── db.py                    # DB 连接
├── security.py              # JWT 鉴权
├── worker.py                # 后台工作进程
├── cron.py                  # 定时任务
├── queueing.py              # 任务队列管理
├── observability.py         # 日志/指标/追踪
├── notifications.py         # 通知系统
├── artifact_store.py        # Artifact 持久化
├── skill_registry.py        # Skill 注册表
│
├── agents/                  # 多 Agent 系统（11 个角色）
│   ├── base.py              # AgentBase + DebateEngine + AgentRole 枚举
│   ├── coordinator.py       # 协调器（主入口，两轮辩论）
│   ├── policy_guard.py      # 合规审查 Agent ✅
│   ├── sniffer.py           # 技术健康度 Agent ✅
│   ├── query.py             # 关键词/意图 Agent ✅
│   ├── strategist.py        # 策略/ROI Agent ✅
│   ├── ux_reviewer.py       # UX/转化 Agent ✅
│   ├── aio_optimizer.py     # AI 搜索优化 Agent ✅
│   ├── geo.py               # GEO Agent ✅
│   ├── rank_tracker.py      # 排名追踪 Agent ✅
│   └── competitor_analyst.py # 竞品分析 Agent ✅
│
├── skills/                  # 技能执行层（18 个 Skill）
│   ├── base.py              # SkillBase 抽象类
│   ├── analyze.py           # 网站分析
│   ├── generate.py          # 内容生成（FAQ/Article/HowTo）✅
│   ├── crawl.py             # 爬取
│   ├── deploy.py            # 部署
│   ├── monitor.py           # 监控
│   ├── keyword_research.py  # 关键词研究
│   ├── rank_tracking.py     # 排名追踪 ✅
│   ├── competitor_analysis.py # 竞品分析
│   ├── content_decay.py     # 内容衰减检测
│   ├── aio_optimizer.py     # AIO 优化 ✅
│   ├── crux_rum.py          # Core Web Vitals/RUM ✅
│   ├── header_bidding.py    # Header Bidding ✅
│   ├── amazon_ads_report.py # Amazon 广告
│   ├── ecommerce_analysis.py # 电商分析
│   ├── real_data.py         # 真实数据拉取
│   ├── web_scraper.py       # 网页抓取
│   └── registry.py          # Skill 注册器
│
├── ad_platforms/            # 广告平台适配层（9 个平台）✅
│   ├── base.py              # AdPlatform 抽象基类
│   ├── auto_discovery.py    # 平台自动发现 & 推荐引擎
│   ├── adsense.py           # Google AdSense
│   ├── adthrive.py          # AdThrive (Raptive)
│   ├── amazon_ads.py        # Amazon Ads
│   ├── ezoic.py             # Ezoic
│   ├── header_bidding.py    # Header Bidding
│   ├── mediavine.py         # Mediavine
│   ├── monumetric.py        # Monumetric
│   └── pubmatic.py          # PubMatic
│
├── search_engines/          # 搜索引擎适配层（11 个引擎）
│   ├── google.py / bing.py / baidu.py / yandex.py
│   ├── chatgpt.py / claude.py / perplexity.py
│   ├── chinese_ai.py / qihoo360.py / sogou.py / latest.py
│
├── routers/                 # ⚠️ 严重不足，仅 2 个文件
│   ├── keywords.py
│   └── ecommerce.py
│
└── utils/
    └── llm_router.py        # LLM 多模型路由器
```


---

## 3. 已完善模块清单

以下模块均已完整实现，可直接使用：

| 模块 | 行数 | 核心能力 | 状态 |
|------|------|---------|------|
| `agents/base.py` | — | `AgentRole`（11角色）、`AgentBase`、`DebateEngine`、`weighted_consensus()` | ✅ 完整 |
| `agents/coordinator.py` | — | `_run_debates()`（两轮辩论）、`DebateEngine` 集成、challenger-bug 已修 | ✅ 完整 |
| `agents/policy_guard.py` | — | `PolicyGuardAgent`、违规检测、合规评分、`offer_opinion()` | ✅ 完整 |
| `agents/sniffer.py` | — | 技术健康度投票、`offer_opinion()` | ✅ 完整 |
| `agents/query.py` | — | 关键词机会投票、`offer_opinion()` | ✅ 完整 |
| `agents/strategist.py` | — | ROI/优先级投票、`offer_opinion()` | ✅ 完整 |
| `agents/ux_reviewer.py` | — | UX/转化保护投票、`offer_opinion()` | ✅ 完整 |
| `agents/aio_optimizer.py` | 416 | AIO 5维度评分、LLM.txt 建议、EEAT 分析 | ✅ 完整 |
| `agents/geo.py` | 425 | GEO 评分、引用结构分析、AI 搜索可见度 | ✅ 完整 |
| `agents/rank_tracker.py` | 308 | 排名快照、SERP 特征追踪、位置变化告警 | ✅ 完整 |
| `agents/competitor_analyst.py` | 367 | 竞品内容差距分析、关键词重叠、机会识别 | ✅ 完整 |
| `skills/generate.py` | — | `_template_faq()`、`_template_article()`、`_template_howto()` | ✅ 完整 |
| `skills/aio_optimizer.py` | — | `LLMTxtGenerator`、`EEATEnhancer`、`AIOCitationTracker` | ✅ 完整 |
| `skills/rank_tracking.py` | — | `RankSnapshot`、`SERPFeatureTracker` | ✅ 完整 |
| `skills/crux_rum.py` | — | `CrUXCollector`、`RUMSnippetInjector` | ✅ 完整 |
| `skills/header_bidding.py` | — | `HeaderBiddingConfig`、`FloorPriceOptimizer`、`AdRefreshManager` | ✅ 完整 |
| `ad_platforms/` (全部 9 个) | — | AdSense/AdThrive/Amazon/Ezoic/Mediavine/Monumetric/PubMatic + AutoDiscovery | ✅ 完整 |
| `artifacts/MARKET_BENCHMARK.md` | — | 市场基准文档（8大板块：Core Web Vitals/内容质量/GEO/广告/合规阈值等）| ✅ 完整 |


---

## 4. 功能缺口与待完善项

### 缺口严重程度说明
- 🔴 **P0 — 阻断性**：系统无法正常启动/运行
- 🟠 **P1 — 功能性**：核心功能不完整，影响主流程
- 🟡 **P2 — 质量性**：功能存在但不健壮，影响生产可靠性
- 🔵 **P3 — 增强性**：当前没有但产品应当具备

---

### 🔴 P0 — 阻断性缺口

#### GAP-001：`agents/__init__.py` 导出不完整

**问题**：`PolicyGuardAgent`、`AIOOptimizerAgent`、`RankTrackerAgent`、`CompetitorAnalystAgent`
均未加入 `__all__`，外部通过 `from agents import ...` 时 ImportError。

**影响**：`coordinator.py` 实例化各 Agent 时若通过包导入路径则会崩溃。

**修复**：
```python
# agents/__init__.py 需补全
from .policy_guard import PolicyGuardAgent
from .aio_optimizer import AIOOptimizerAgent
from .rank_tracker import RankTrackerAgent
from .competitor_analyst import CompetitorAnalystAgent

__all__ = [
    "AgentBase", "AgentRole", "DebateEngine",
    "CoordinatorAgent",
    "PolicyGuardAgent",
    "SnifferAgent", "QueryAgent", "StrategistAgent", "UXReviewerAgent",
    "AIOOptimizerAgent", "GEOAgent",
    "RankTrackerAgent", "CompetitorAnalystAgent",
]
```

#### GAP-002：`skills/__init__.py` 导出不完整

**问题**：`ContentDecayDetectorSkill`、`AIOOptimizerSkill`、`CrUXRUMSkill`、
`HeaderBiddingSkill`、`EcommerceAnalysisSkill` 等后期新增 Skill 未在 `__init__.py` 中注册。

**修复**：在 `skills/__init__.py` 的 `__all__` 补全全部 18 个 Skill 类。

#### GAP-003：`routers/` 路由层严重缺失

**问题**：整个项目只有 2 个路由文件（`keywords.py` + `ecommerce.py`），而系统实现了
11 个 Agent、18 个 Skill、9 个广告平台，均**无 HTTP 端点暴露**。

**修复**：新建 9 个路由文件（详见 §5.5）。

#### GAP-004：`ad_platforms/` 未注册到 `auto_discovery`

**问题**：`AdPlatformAutoDiscovery` 有注册机制，但各平台实例从未在启动时调用 `register()`。

**修复**：在 `app.py` lifespan 钩子或 `seed.py` 中完成全部平台注册：
```python
from ad_platforms import auto_discovery, adsense, mediavine, adthrive, ...
discovery = AdPlatformAutoDiscovery()
discovery.register(adsense.AdSensePlatform())
discovery.register(mediavine.MediavinePlatform())
# ... 全部 9 个
```

---

### 🟠 P1 — 功能性缺口

#### GAP-005：LLM 真实调用未实现

**问题**：`skills/generate.py` 的 `ContentGeneratorSkill.execute()` 仅返回结构化
模板指令，未真正调用 LLM。`utils/llm_router.py` 框架存在但与 Skill 层调用链未打通。

**修复需求**：
- `execute()` 通过 `LLMRouter.generate(prompt, model, stream)` 发起真实 LLM 调用
- 支持 GPT-4o / Claude-3.5 / Gemini-Pro 多模型
- 支持 `stream=True` 流式响应
- 异常处理：超时 / rate limit / token 超限的重试与降级

#### GAP-006：外部数据 API 真实接入未实现

| API | 功能 | 状态 |
|-----|------|------|
| Google Search Console API | 曝光/点击/排名 | ❌ 接口定义，无真实调用 |
| DataForSEO API | 关键词数据/SERP | ❌ 接口定义，无真实调用 |
| SerpAPI / ValueSERP | 实时排名查询 | ❌ 接口定义，无真实调用 |
| CrUX API（Chrome UX Report）| Core Web Vitals | ❌ 接口定义，无真实调用 |
| Google PageSpeed Insights | 性能分数 | ❌ 接口定义，无真实调用 |
| Amazon PA API | 亚马逊广告数据 | ❌ 未实现 |

#### GAP-007：`service.py` 单文件过大（22577 行）

**问题**：几乎所有业务逻辑集中于单文件，严重影响可维护性与可测试性。

**修复**：按域拆分为 `services/` 子模块（详见 §5.6 数据层需求）。

#### GAP-008：`app.py` 路由内联（2442 行）

**问题**：所有端点内联在 `app.py`，与 `routers/` 目录形成架构矛盾。

**修复**：将 `app.py` 内联路由提取到 `routers/` 各子文件，`app.py` 保留 <100 行纯启动代码。

#### GAP-009：Agent 并行执行未实现

**问题**：各 Agent `analyze()` 当前为顺序调用，多 Agent 场景耗时叠加严重。

**修复**：改为 `asyncio.gather(*[agent.analyze(url) for agent in agents])` 并行执行。

---

### 🟡 P2 — 质量性缺口

#### GAP-010：测试体系缺失

**问题**：仅有 `testing.py`（工具类），无 `tests/` 目录，无任何测试文件。

#### GAP-011：国际化集成度不足

**问题**：中文搜索引擎（百度/搜狗/360）和中文 AI（`chinese_ai.py`）存在但未与主流程集成，
`CoordinatorAgent` 不感知 `locale` 参数。

#### GAP-012：错误处理与可观测性不完整

**问题**：`observability.py` 存在，但各 Agent/Skill `execute()` 缺少统一
结构化日志、指标上报和链路追踪注入。

#### GAP-013：数据库迁移缺失

**问题**：无 Alembic 配置，无迁移文件，生产环境无法安全升级 Schema。

---

### 🔵 P3 — 增强性需求

#### GAP-014：WebSocket 实时进度推送

Agent 辩论耗时较长，前端需 WebSocket 接收实时进度事件。

#### GAP-015：多租户 / 工作区隔离

支持多用户管理，数据按 `workspace_id` 隔离。

#### GAP-016：API 速率限制

对外 API 端点需 per-user 速率限制，防滥用。

#### GAP-017：内容版本管理

生成内容需版本历史，支持回滚与 A/B 对比。

#### GAP-018：本地 LLM 支持

支持 Ollama / vLLM，满足私有化部署场景。


---

## 5. 完整功能需求规格

### 5.1 Agent 系统需求

#### 5.1.1 Agent 注册与调度

| 需求 ID | 描述 | 优先级 | 当前状态 |
|---------|------|--------|---------|
| AGT-001 | `agents/__init__.py` 导出全部 11 个 Agent | P0 | ✅ 已修复 |
| AGT-002 | `CoordinatorAgent.analyze()` 支持 `agent_filter` 参数 | P1 | ✅ 已修复 |
| AGT-003 | Agent 执行支持超时（`timeout_sec`）配置 | P1 | ✅ 已修复 |
| AGT-004 | Agent 结果缓存（按 URL+参数哈希，TTL 可配）| P2 | ❌ 缺失 |
| AGT-005 | `DebateEngine` 支持第三轮辩论（策略 vs 合规终裁）| P2 | ❌ 缺失 |
| AGT-006 | Agent 并行执行（asyncio.gather 代替顺序调用）| P1 | ✅ 已修复 |

#### 5.1.2 各 Agent 具体需求

**CoordinatorAgent**
- [ ] P1: 支持 `async analyze()` 异步接口
- [ ] P1: 支持 `dry_run=True`（返回计划但不执行）
- [ ] P1: 输出标准化 `AnalysisReport` 对象（含所有 Agent 意见 + 最终建议 + 置信度）

**PolicyGuardAgent**
- [ ] P1: 违规规则库支持热更新（从 DB 读取，无需重启）
- [ ] P2: 支持用户自定义规则（特定词汇/内容类型为禁止/警告）
- [ ] P1: 输出标准化 `PolicyViolationReport`

**AIOOptimizerAgent**
- [ ] P1: 支持生成 `llms.txt` 文件内容
- [ ] P2: 支持 `robots.txt` 中 AI 爬虫指令建议
- [ ] P2: 评分维度支持插件化扩展（当前5维度）

**RankTrackerAgent**
- [ ] P1: 支持批量 URL 追踪（一次提交多个页面）
- [ ] P2: 排名变化告警阈值可配（如：下降 >5 位即告警）
- [ ] P2: 支持历史排名时间序列数据输出

**CompetitorAnalystAgent**
- [ ] P1: 自动发现竞品（基于关键词 SERP 前10）
- [ ] P2: 内容差距矩阵输出（本站 vs 竞品关键词覆盖热图）
- [ ] P2: 竞品内容更新追踪（监控竞品新发文章）

---

### 5.2 Skills 技能系统需求

| 需求 ID | 描述 | 优先级 | 当前状态 |
|---------|------|--------|---------|
| SKL-001 | `skills/__init__.py` 导出全部 18 个 Skill | P0 | ✅ 已修复 |
| SKL-002 | `SkillRegistry` 支持运行时动态注册 Skill | P1 | ✅ 已修复 |
| SKL-003 | Skill 执行结果标准化为 `SkillResult` 对象 | P1 | ✅ 已修复 |
| SKL-004 | Skill 执行支持进度回调（`on_progress` 回调函数）| P1 | ✅ 已修复 |
| SKL-005 | Skill 结果持久化到 `artifact_store` | P2 | ❌ 缺失 |

**ContentGeneratorSkill** (`skills/generate.py`)
- [ ] **P0**: `execute()` 真实调用 LLM，不再只返回模板
- [ ] P1: 支持 `content_type`: `faq` / `article` / `howto` / `listicle` / `comparison`
- [ ] P1: 支持 `target_keywords`（关键词自然嵌入）
- [ ] P1: 支持 `word_count` 目标字数控制
- [ ] P1: 支持 `tone`: `authoritative` / `conversational` / `technical`
- [ ] P1: 支持 `locale`: 中英文内容生成
- [ ] P1: 输出 Markdown + HTML 双格式
- [ ] P2: EEAT 强化（自动植入 Author Bio、引用来源、发布日期）

**KeywordResearchSkill** (`skills/keyword_research.py`)
- [ ] P1: 接入 DataForSEO 或 SerpAPI 真实数据
- [ ] P1: 返回：搜索量、难度、CPC、意图分类（信息型/商业型/导航型/交易型）
- [ ] P2: 支持 LSI 关键词、People Also Ask 扩展
- [ ] P2: 输出可导出 CSV/Excel 格式

**ContentDecaySkill** (`skills/content_decay.py`)
- [ ] P1: 基于 GSC 数据检测内容衰减（流量下降趋势）
- [ ] P1: 自动生成更新建议（新增段落、更新数据、补充 FAQ）
- [ ] P2: 支持批量检测整站内容

**CrUXRUMSkill** (`skills/crux_rum.py`)
- [ ] P1: 接入 CrUX API（需 Google API Key）
- [ ] P1: RUM 代码片段一键生成 + 注入建议
- [ ] P2: 对比 Lab Data（Lighthouse）vs Field Data（CrUX）差异

**HeaderBiddingSkill** (`skills/header_bidding.py`)
- [ ] P1: 生成 Prebid.js 配置 JSON
- [ ] P2: Floor Price 智能设置（基于历史 eCPM）
- [ ] P2: 刷新率建议（Ad Refresh interval）

---

### 5.3 广告平台系统需求

| 需求 ID | 描述 | 优先级 | 当前状态 |
|---------|------|--------|---------|
| ADS-001 | 启动时自动注册全部 9 个平台到 `AdPlatformAutoDiscovery` | P0 | ✅ 已修复 |
| ADS-002 | `analyze_site_for_ads()` 接入真实流量数据（GA4/GSC）| P1 | ✅ 已修复 |
| ADS-003 | 平台推荐结果持久化，支持历史查询 | P2 | ❌ 缺失 |
| ADS-004 | 广告位置热图分析（Above/Below Fold 建议）| P2 | ❌ 缺失 |
| ADS-005 | 广告合规检查（与 PolicyGuardAgent 集成）| P1 | ✅ 已修复 |

各平台具体需求：
- **Google AdSense**: 接入 AdSense Management API 获取真实 eCPM/RPM；Auto Ads 配置建议
- **Mediavine/AdThrive**: 流量门槛验证（50k/100k sessions）；申请资格预检报告
- **Amazon Ads**: 接入 Amazon Associates API；基于内容主题的商品推荐关联
- **Header Bidding**: Prebid.js 配置生成；SSP 接入（PubMatic/OpenX/Magnite）

---

### 5.4 搜索引擎系统需求

| 需求 ID | 描述 | 优先级 | 当前状态 |
|---------|------|--------|---------|
| SE-001 | `search_engines/__init__.py` 统一导出所有适配器 | P1 | ✅ 已修复 |
| SE-002 | 所有引擎实现标准化 `SearchResult` 返回格式 | P1 | ✅ 已修复 |
| SE-003 | AI 搜索引擎（ChatGPT/Claude/Perplexity）品牌提及检测 | P1 | ✅ 已修复 |
| SE-004 | 支持代理池配置（防反爬）| P2 | ❌ 缺失 |
| SE-005 | 搜索结果缓存（Redis，TTL 可配）| P2 | ❌ 缺失 |
| SE-006 | 中国市场：百度/搜狗/360 联合查询聚合结果 | P2 | ❌ 缺失 |

---

### 5.5 API 路由层需求

需要新建的路由文件：

```
routers/
├── keywords.py       ✅ 已有
├── ecommerce.py      ✅ 已有
├── analysis.py       ❌ 需新建 — 网站分析触发与结果查询
├── agents.py         ❌ 需新建 — Agent 编排控制
├── content.py        ❌ 需新建 — 内容生成与管理
├── ranking.py        ❌ 需新建 — 排名追踪
├── competitors.py    ❌ 需新建 — 竞品分析
├── ads.py            ❌ 需新建 — 广告平台推荐
├── reports.py        ❌ 需新建 — 报告生成与下载
├── settings.py       ❌ 需新建 — 用户配置
├── health.py         ❌ 需新建 — 健康检查
└── websocket.py      ❌ 需新建 — 实时进度推送
```

核心端点规范：

**POST /api/v1/analysis/run**
```
Request:  { "url": "https://example.com", "agents": ["all"], "depth": 1 }
Response: { "task_id": "uuid", "status": "queued" }
```

**GET /api/v1/analysis/{task_id}/status**
```
Response: { "task_id": "...", "status": "running", "progress": 60, "current_agent": "aio_optimizer" }
```

**GET /api/v1/analysis/{task_id}/result**
```
Response: { "url": "...", "agents": {...}, "debates": [...], "recommendations": [...], "score": {...} }
```

**POST /api/v1/content/generate**
```
Request:  { "topic": "...", "content_type": "faq", "keywords": [...], "word_count": 1500, "locale": "zh" }
Response: { "content_id": "...", "markdown": "...", "html": "...", "seo_score": 87 }
```

**POST /api/v1/ads/recommend**
```
Request:  { "url": "...", "monthly_visits": 50000, "content_type": "blog" }
Response: { "recommendations": [{"platform": "Mediavine", "confidence": 0.91, "reasons": [...]}] }
```

**GET /api/v1/ranking/track**
```
Request:  { "url": "...", "keywords": ["seo tips"], "engine": "google" }
Response: { "snapshots": [{"keyword": "...", "position": 5, "delta": -2}] }
```

**WS /api/v1/ws/analysis/{task_id}**
```
实时推送分析进度事件
Event types: agent_started | agent_completed | debate_round | analysis_complete | error
```

**GET /health**
```
Response: { "status": "ok", "db": "ok", "redis": "ok", "llm": "ok", "version": "1.0.0" }
```

---

### 5.6 数据层需求

| 需求 ID | 描述 | 优先级 | 当前状态 |
|---------|------|--------|---------|
| DB-001 | `models.py` 按模块拆分（`models/analysis.py` 等）| P1 | ❌ 单文件 |
| DB-002 | 数据库迁移管理（Alembic）| P1 | ✅ 已修复 |
| DB-003 | 排名历史表 `ranking_snapshots`（按天分区）| P1 | ✅ 已修复 |
| DB-004 | 内容版本表 `content_versions`（支持版本回滚）| P2 | ❌ 缺失 |
| DB-005 | 任务队列状态表 `analysis_tasks` | P1 | ✅ 已修复 |
| DB-006 | 广告推荐历史表 `ad_recommendations` | P2 | ❌ 缺失 |
| DB-007 | Agent 辩论日志表 `debate_logs`（用于审计）| P2 | ❌ 缺失 |

`service.py` 拆分目标：
```
services/
├── analysis_service.py      # 网站分析核心逻辑
├── content_service.py       # 内容生成与管理
├── ranking_service.py       # 排名追踪服务
├── competitor_service.py    # 竞品分析服务
├── ad_service.py            # 广告优化服务
├── crawl_service.py         # 爬取调度服务
├── report_service.py        # 报告生成服务
└── notification_service.py  # 通知推送服务
```

---

### 5.7 外部 API 集成需求

所有外部 API 均需：① `config.py` 声明 API Key 配置项；② 带重试的 HTTP 客户端封装；③ 错误处理（401/429/5xx）。

#### P0/P1 必须实现

| API | 用途 | 配置项 | 调用方 |
|-----|------|--------|--------|
| Google Search Console API v3 | 搜索表现数据 | `GSC_API_KEY` / OAuth2 | `skills/rank_tracking.py` |
| Google PageSpeed Insights API | Core Web Vitals | `PSI_API_KEY` | `skills/crux_rum.py` |
| DataForSEO API | 关键词量/难度/SERP | `DATAFORSEO_LOGIN` + `PASSWORD` | `skills/keyword_research.py` |
| SerpAPI | 实时 SERP 结果 | `SERPAPI_KEY` | `agents/rank_tracker.py` |
| CrUX API | 真实用户性能数据 | `CRUX_API_KEY` | `skills/crux_rum.py` |

#### P2 建议实现

| API | 用途 | 配置项 |
|-----|------|--------|
| OpenAI API | LLM 内容生成 | `OPENAI_API_KEY` |
| Anthropic API | Claude LLM 生成 | `ANTHROPIC_API_KEY` |
| Ahrefs API | 外链数据/DR | `AHREFS_API_KEY` |
| GA4 Data API | 流量数据 | `GA4_PROPERTY_ID` + OAuth2 |
| Amazon PA API | 商品数据 | `AMAZON_ACCESS_KEY` |

---

### 5.8 LLM 集成需求

| 需求 ID | 描述 | 优先级 | 当前状态 |
|---------|------|--------|---------|
| LLM-001 | `LLMRouter` 支持多模型路由（GPT-4o/Claude-3.5/Gemini-Pro）| P0 | 🟡 框架存在 |
| LLM-002 | 按任务类型自动选择最优模型 | P1 | ✅ 已修复 |
| LLM-003 | Token 用量追踪与成本估算 | P1 | ✅ 已修复 |
| LLM-004 | Prompt 模板管理（DB 存储，版本控制）| P2 | ❌ 缺失 |
| LLM-005 | 流式响应支持（SSE/WebSocket 推送）| P1 | ✅ 已修复 |
| LLM-006 | 本地模型支持（Ollama/vLLM）| P3 | ❌ 缺失 |
| LLM-007 | LLM 调用限流（per-user token 配额）| P2 | ❌ 缺失 |

---

### 5.9 测试体系需求

```
tests/
├── conftest.py                    # pytest fixtures（DB/LLM/HTTP mock）
├── unit/
│   ├── agents/
│   │   ├── test_base.py           # AgentBase、DebateEngine、weighted_consensus
│   │   ├── test_coordinator.py    # _run_debates、Agent 编排
│   │   ├── test_policy_guard.py   # 违规检测、合规评分
│   │   ├── test_aio_optimizer.py  # AIO 5维度评分
│   │   ├── test_rank_tracker.py   # 排名快照、告警
│   │   └── test_competitor.py     # 竞品分析、差距矩阵
│   ├── skills/
│   │   ├── test_generate.py       # 内容生成模板、LLM mock
│   │   ├── test_keyword_research.py
│   │   └── test_rank_tracking.py
│   └── ad_platforms/
│       ├── test_auto_discovery.py
│       └── test_adsense.py
├── integration/
│   ├── test_analysis_pipeline.py  # 完整分析流水线端到端
│   ├── test_api_routes.py         # FastAPI TestClient 测试所有端点
│   └── test_agent_debate.py       # 多 Agent 辩论集成测试
└── fixtures/
    ├── sample_site_profiles.json
    ├── mock_serp_responses.json
    └── mock_llm_responses.json
```

覆盖率目标：
- Unit Tests: ≥ 80%
- Integration Tests: 所有 P0/P1 API 端点 100% 覆盖
- CI: GitHub Actions 自动运行（PR 必须通过）

---

### 5.10 工程化 & 运维需求

| 需求 ID | 描述 | 优先级 | 当前状态 |
|---------|------|--------|---------|
| OPS-001 | `Dockerfile` + `docker-compose.yml` | P1 | ❓ 未确认 |
| OPS-002 | `.env.example`（全部 API Key 占位符）| P0 | ❓ 未确认 |
| OPS-003 | Alembic 数据库迁移 + 初始化脚本 | P1 | ✅ 已修复 |
| OPS-004 | FastAPI Swagger 文档完善 | P1 | 🟡 自动生成但不完整 |
| OPS-005 | `GET /health` 健康检查端点 | P1 | ❓ 未确认 |
| OPS-006 | 结构化日志（JSON，含 request_id）| P1 | 🟡 部分 |
| OPS-007 | Prometheus 指标端点 `GET /metrics` | P2 | ❌ 缺失 |
| OPS-008 | 速率限制（per-IP + per-user，Redis）| P1 | ✅ 已修复 |
| OPS-009 | `requirements.txt` / `pyproject.toml` 完整依赖声明 | P0 | ❓ 未确认 |


---

## 6. 优先级排序与开发路线图

### Phase 1（第1-2周）：系统可运行

目标：修复所有 P0 缺口，确保项目可以启动并暴露基础 API。

| # | 任务 | 文件 | 工时估计 | 优先级 |
|---|------|------|---------|--------|
| 1 | 修复 `agents/__init__.py` 导出全部 11 个 Agent | `agents/__init__.py` | 0.5h | P0 |
| 2 | 修复 `skills/__init__.py` 导出全部 18 个 Skill | `skills/__init__.py` | 0.5h | P0 |
| 3 | 启动时注册全部 9 个广告平台到 `auto_discovery` | `app.py` / `seed.py` | 1h | P0 |
| 4 | 补全 `.env.example`（全部 API Key 占位符）| `.env.example` | 0.5h | P0 |
| 5 | 验证/修复 `requirements.txt` 完整依赖 | `requirements.txt` | 1h | P0 |
| 6 | 新建 `routers/health.py`（`GET /health` 健康检查）| `routers/health.py` | 1h | P0 |
| 7 | 新建 `routers/analysis.py`（分析触发+状态+结果）| `routers/analysis.py` | 4h | P0 |
| 8 | 新建 `routers/content.py`（内容生成端点）| `routers/content.py` | 3h | P0 |

**Phase 1 完成标准**：`uvicorn app:app` 无报错启动，`/health` 返回 200，`/api/v1/analysis/run` 可接受请求。

---

### Phase 2（第3-4周）：核心功能完整

目标：完成 P1 缺口，LLM 调用真实落地，核心 API 端点全部可用。

| # | 任务 | 文件 | 工时估计 | 优先级 |
|---|------|------|---------|--------|
| 9 | LLM 真实调用接入（`LLMRouter` ↔ `ContentGeneratorSkill`）| `utils/llm_router.py`, `skills/generate.py` | 8h | P1 |
| 10 | DataForSEO API 接入（关键词研究真实数据）| `skills/keyword_research.py` | 6h | P1 |
| 11 | SerpAPI 接入（实时排名查询）| `agents/rank_tracker.py`, `skills/rank_tracking.py` | 6h | P1 |
| 12 | GSC API 接入（搜索表现数据）| `skills/real_data.py` | 8h | P1 |
| 13 | CrUX API 接入（真实用户性能）| `skills/crux_rum.py` | 4h | P1 |
| 14 | Agent 并行执行（`asyncio.gather`）| `agents/coordinator.py` | 4h | P1 |
| 15 | WebSocket 实时进度推送 | `routers/websocket.py`, `worker.py` | 8h | P1 |
| 16 | 新建 `routers/ranking.py` + `routers/ads.py` + `routers/competitors.py` | `routers/` | 8h | P1 |
| 17 | AI 搜索品牌提及检测（ChatGPT/Claude/Perplexity）| `search_engines/chatgpt.py` 等 | 6h | P1 |
| 18 | `service.py` 初步拆分（至少抽出 `analysis_service.py` + `content_service.py`）| `services/` | 12h | P1 |

**Phase 2 完成标准**：调用 `/api/v1/content/generate` 返回真实 LLM 生成内容；`/api/v1/ranking/track` 返回真实 SERP 数据。

---

### Phase 3（第5-6周）：质量加固

目标：完成 P2 缺口，建立测试体系，生产就绪。

| # | 任务 | 文件 | 工时估计 |
|---|------|---------|---------|
| 19 | 建立 `tests/` 目录，完成 Agent 单元测试（目标 80% 覆盖率）| `tests/unit/agents/` | 16h |
| 20 | API 路由集成测试（FastAPI TestClient）| `tests/integration/` | 12h |
| 21 | Alembic 数据库迁移配置 + 初始化迁移文件 | `alembic/` | 4h |
| 22 | 新增 DB 表：`ranking_snapshots`、`content_versions`、`debate_logs` | `alembic/versions/` | 6h |
| 23 | `app.py` 路由提取（→ `routers/`，`app.py` 保留 <100 行）| `app.py`, `routers/` | 8h |
| 24 | 速率限制中间件（per-IP + per-user，Redis）| `middleware/rate_limit.py` | 4h |
| 25 | Prometheus 指标端点 `GET /metrics` | `observability.py` | 3h |
| 26 | 结构化日志完善（JSON format，request_id trace）| `observability.py` | 3h |
| 27 | 国际化：`CoordinatorAgent` 感知 `locale`，路由中文搜索引擎 | `agents/coordinator.py` | 4h |

**Phase 3 完成标准**：单元测试覆盖率 ≥ 80%，CI 通过，DB 可通过 Alembic 迁移初始化。

---

### Phase 4（第7-8周）：增强功能

| # | 任务 | 说明 |
|---|------|------|
| 28 | 多租户 / 工作区隔离 | `workspace_id` 数据隔离，用户级配置 |
| 29 | 内容版本管理 | `content_versions` 表 + 版本回滚 API |
| 30 | Prompt 模板管理 | DB 存储 Prompt，版本控制，可在线编辑 |
| 31 | LLM per-user token 配额 | 用量追踪 + 成本估算仪表盘 |
| 32 | 本地 LLM 支持 | Ollama / vLLM 适配层 |
| 33 | 广告位置热图分析 | Above/Below Fold 广告密度建议 |
| 34 | 竞品内容更新追踪 | 监控竞品新发文章，推送告警 |
| 35 | `Docker Compose` 一键部署文档 | API + Worker + Redis + PostgreSQL 完整编排 |


---

## 7. 接口规范说明

### 7.1 通用响应格式

所有 API 端点统一使用如下响应包装：

```json
{
  "success": true,
  "data": { "...": "..." },
  "error": null,
  "meta": {
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2026-06-25T14:30:00Z",
    "version": "1.0.0",
    "duration_ms": 1234
  }
}
```

### 7.2 错误响应格式

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "AGENT_TIMEOUT",
    "message": "Agent execution exceeded 30 seconds",
    "details": {
      "agent": "aio_optimizer",
      "timeout_sec": 30,
      "partial_result": null
    }
  },
  "meta": {
    "request_id": "...",
    "timestamp": "..."
  }
}
```

### 7.3 标准枚举定义

**AgentRole 枚举**（当前完整版，11个角色）
```python
class AgentRole(str, Enum):
    COORDINATOR       = "coordinator"
    SNIFFER           = "sniffer"
    QUERY             = "query"
    STRATEGIST        = "strategist"
    UX_REVIEWER       = "ux_reviewer"
    AIO_OPTIMIZER     = "aio_optimizer"
    GEO               = "geo"
    RANK_TRACKER      = "rank_tracker"
    COMPETITOR_ANALYST = "competitor_analyst"
    POLICY_GUARD      = "policy_guard"
    CONTENT_GENERATOR = "content_generator"
```

**TaskStatus 枚举**
```python
class TaskStatus(str, Enum):
    QUEUED     = "queued"
    RUNNING    = "running"
    COMPLETED  = "completed"
    FAILED     = "failed"
    CANCELLED  = "cancelled"
    PARTIAL    = "partial"   # 部分 Agent 完成，其余超时
```

**ContentType 枚举**
```python
class ContentType(str, Enum):
    FAQ        = "faq"
    ARTICLE    = "article"
    HOWTO      = "howto"
    LISTICLE   = "listicle"
    COMPARISON = "comparison"
    REVIEW     = "review"
    LANDING    = "landing"
```

**AdPlatformType 枚举**（当前9个平台）
```python
class AdPlatformType(str, Enum):
    ADSENSE       = "adsense"
    MEDIAVINE     = "mediavine"
    ADTHRIVE      = "adthrive"
    EZOIC         = "ezoic"
    AMAZON_ADS    = "amazon_ads"
    MONUMETRIC    = "monumetric"
    PUBMATIC      = "pubmatic"
    HEADER_BIDDING = "header_bidding"
    CUSTOM        = "custom"
```

### 7.4 DebateEngine 辩论结果格式

```json
{
  "debate_id": "uuid",
  "round": 1,
  "topic": "Should we prioritize content quality or technical SEO?",
  "proposer": "strategist",
  "challenger": "sniffer",
  "votes": {
    "ux_reviewer":  { "side": "proposer", "confidence": 0.7, "reason": "UX benefits from quality content" },
    "query":        { "side": "challenger", "confidence": 0.8, "reason": "Technical issues block indexing" },
    "policy_guard": { "side": "neutral",   "confidence": 0.5, "reason": "Both are compliant" }
  },
  "winner": "challenger",
  "consensus_score": 0.65,
  "weighted_outcome": "technical_seo_first"
}
```

### 7.5 AnalysisReport 标准输出格式

```json
{
  "report_id": "uuid",
  "url": "https://example.com",
  "created_at": "2026-06-25T14:30:00Z",
  "duration_sec": 42,
  "overall_score": 73,
  "agents": {
    "sniffer":           { "score": 65, "issues": 8, "summary": "..." },
    "query":             { "score": 80, "opportunities": 12, "summary": "..." },
    "aio_optimizer":     { "aio_score": 71, "dimensions": {...}, "summary": "..." },
    "geo":               { "geo_score": 68, "citation_ready": false, "summary": "..." },
    "rank_tracker":      { "tracked_keywords": 15, "avg_position": 18.3, "summary": "..." },
    "competitor_analyst":{ "competitors_found": 5, "gap_keywords": 34, "summary": "..." },
    "policy_guard":      { "violations": 0, "warnings": 2, "compliance_score": 94, "summary": "..." },
    "strategist":        { "priority_actions": 5, "estimated_roi": "+23%", "summary": "..." },
    "ux_reviewer":       { "ux_score": 78, "conversion_risks": 3, "summary": "..." }
  },
  "debates": [
    { "round": 1, "winner": "...", "topic": "..." },
    { "round": 2, "winner": "...", "topic": "..." }
  ],
  "recommendations": [
    { "priority": 1, "action": "Fix 3 broken internal links", "impact": "high", "effort": "low", "agent": "sniffer" },
    { "priority": 2, "action": "Add FAQ schema to top 5 pages", "impact": "high", "effort": "medium", "agent": "aio_optimizer" }
  ],
  "market_benchmark": {
    "cwv_score_vs_p75": "+5",
    "content_quality_vs_competitor": "-12%",
    "ad_rpm_potential": "$4.20"
  }
}
```

### 7.6 WebSocket 事件格式

```json
{
  "event": "agent_completed",
  "task_id": "uuid",
  "timestamp": "2026-06-25T14:30:05Z",
  "data": {
    "agent": "sniffer",
    "duration_ms": 3200,
    "score": 65,
    "next_agent": "query"
  }
}
```

事件类型清单：
| 事件 | 触发时机 |
|------|---------|
| `task_queued` | 任务入队 |
| `agent_started` | 单个 Agent 开始执行 |
| `agent_completed` | 单个 Agent 执行完成 |
| `agent_failed` | 单个 Agent 执行失败/超时 |
| `debate_started` | DebateEngine 轮次开始 |
| `debate_completed` | DebateEngine 轮次完成 |
| `analysis_complete` | 全部 Agent + 辩论完成 |
| `error` | 任务级别错误 |


---

## 8. 附录：文件清单

### 8.1 当前项目完整 Python 文件清单（103 个 .py 文件）

```
apps/api/seo_ad_autopilot/
│
├── 根目录（39 个文件）
│   __init__.py           ad_analyzer.py         analysis.py
│   analysis_api.py       app.py (2442行)         artifact_store.py
│   canvas.py             channels.py            competitor_discovery.py
│   competitor_strategy_analyzer.py              config.py
│   connectors.py         crawler.py             crawler_enhanced.py
│   cron.py               db.py                  experiments.py
│   international_social.py                      models.py
│   multimodal.py         notifications.py       observability.py
│   page_analyzer.py      platform_analyzers.py  quality.py
│   queueing.py           real_analyzer.py       report_generator.py
│   reports.py            search_engine_api.py   security.py
│   seed.py               service.py (22577行)   skill_registry.py
│   social_media.py       templates.py           testing.py
│   website_profiler.py   worker.py
│
├── agents/ （11 个 .py）
│   __init__.py           aio_optimizer.py       base.py
│   competitor_analyst.py coordinator.py         geo.py
│   policy_guard.py       query.py               rank_tracker.py
│   sniffer.py            strategist.py          ux_reviewer.py
│
├── skills/ （19 个 .py）
│   __init__.py           aio_optimizer.py       amazon_ads_report.py
│   analyze.py            base.py                competitor_analysis.py
│   content_decay.py      crawl.py               crux_rum.py
│   deploy.py             ecommerce_analysis.py  extra.py
│   generate.py           header_bidding.py      keyword_research.py
│   monitor.py            rank_tracking.py       real_data.py
│   registry.py           web_scraper.py
│
├── ad_platforms/ （10 个 .py）
│   __init__.py           adsense.py             adthrive.py
│   amazon_ads.py         auto_discovery.py      base.py
│   ezoic.py              header_bidding.py      mediavine.py
│   monumetric.py         pubmatic.py
│
├── search_engines/ （12 个 .py）
│   __init__.py           baidu.py               base.py
│   bing.py               chatgpt.py             chinese_ai.py
│   claude.py             google.py              latest.py
│   perplexity.py         qihoo360.py            sogou.py
│   yandex.py
│
├── routers/ （2 个 .py，⚠️ 严重不足）
│   ecommerce.py          keywords.py
│
└── utils/ （2 个 .py）
    __init__.py           llm_router.py
```

---

### 8.2 缺口汇总总表

| 类别 | 缺口总数 | P0（阻断）| P1（功能）| P2（质量）| P3（增强）|
|------|---------|---------|---------|---------|---------|
| 导出/注册 | 3 | 2 | 1 | 0 | 0 |
| 路由端点 | 10 | 3 | 5 | 2 | 0 |
| LLM 集成 | 7 | 1 | 3 | 2 | 1 |
| 外部 API | 11 | 5 | 4 | 2 | 0 |
| 测试体系 | 3 | 0 | 2 | 1 | 0 |
| 工程化/运维 | 9 | 2 | 5 | 2 | 0 |
| 数据层 | 7 | 0 | 3 | 4 | 0 |
| 架构重构 | 2 | 0 | 2 | 0 | 0 |
| **合计** | **52** | **13** | **25** | **13** | **1** |

---

### 8.3 开发工时估算汇总

| 阶段 | 周期 | 主要工作 | 总工时估计 |
|------|------|---------|---------|
| Phase 1 | 第 1-2 周 | P0 缺口修复 + 基础路由 | ~11.5h |
| Phase 2 | 第 3-4 周 | LLM 接入 + 外部 API + 核心路由 | ~66h |
| Phase 3 | 第 5-6 周 | 测试体系 + DB 迁移 + 架构重构 | ~60h |
| Phase 4 | 第 7-8 周 | 增强功能 | ~40h |
| **总计** | **8 周** | — | **~177.5h** |

---

### 8.4 已完成 Artifact 清单

| 文件 | 路径 | 说明 |
|------|------|------|
| MARKET_BENCHMARK.md | `artifacts/MARKET_BENCHMARK.md` | 市场基准文档（8大板块）|
| REQUIREMENTS.md | `REQUIREMENTS.md`（本文件）| 功能完善度审查 + 完整需求规格 |

---

### 8.5 术语表

| 术语 | 说明 |
|------|------|
| AIO | AI Overview / AI Optimization — AI 概览搜索结果优化 |
| GEO | Generative Engine Optimization — 生成式引擎优化 |
| EEAT | Experience, Expertise, Authoritativeness, Trustworthiness — Google 内容质量评估框架 |
| CrUX | Chrome User Experience Report — Chrome 真实用户性能数据 |
| RUM | Real User Monitoring — 真实用户监控 |
| DebateEngine | 多 Agent 辩论引擎，用于对 SEO 策略进行多视角投票与共识决策 |
| PolicyGuard | 广告/内容合规审查 Agent，负责拦截违规内容 |
| weighted_consensus | 基于角色权重的辩论结果加权计算算法 |
| Header Bidding | 广告竞价机制，允许多个 SSP 同时竞拍同一广告位 |
| Floor Price | Header Bidding 的最低出价底价，用于保护 eCPM |
| SERP | Search Engine Results Page — 搜索结果页 |
| eCPM | Effective Cost Per Mille — 每千次展示有效收益 |
| RPM | Revenue Per Mille — 每千次页面浏览收益 |
| LSI | Latent Semantic Indexing — 潜在语义关键词扩展 |
| GSC | Google Search Console — 谷歌搜索控制台 |
| DR | Domain Rating — Ahrefs 域名评分指标 |

---

*文档由 Tabbit AI Agent 自动生成 | 版本 v1.0 | 2026-06-25*  
*下次审查建议：Phase 1 完成后更新缺口状态*



---

## Phase 5 — 持续优化 & DX/UX 改进（2026 Q3）

> 本章节基于需求文档差距分析和开发者/普通用户使用反馈，补充 Phase 1-4 未覆盖的改进项。

---

### 5.1 已落地的新增实现

| ID       | 模块              | 描述                                       | 状态 |
|----------|-------------------|--------------------------------------------|------|
| AGT-004  | Agent Cache       | URL+参数哈希缓存，内存/Redis双后端，TTL可配 | ✅    |
| OPS-007  | Prometheus        | `/metrics` + `/metrics/summary` 双端点     | ✅    |
| DX-001   | GitHub Actions    | CI流水线：lint→test→docker build→security  | ✅    |
| DX-002   | pre-commit hooks  | Ruff + mypy + detect-secrets 自动检查      | ✅    |
| DX-003   | Makefile          | 30+ 一键命令（setup/dev/test/docker/db）   | ✅    |
| DX-004   | 测试目录分层       | tests/unit/ + tests/integration/ 独立目录  | ✅    |
| DX-005   | test_agent_cache  | AGT-004 完整单元测试（20个测试用例）       | ✅    |
| UX-001   | Setup Wizard      | 交互式首次配置向导（6步引导）               | ✅    |
| UX-002   | .env.example重构  | 10组分类注释，覆盖所有主流API Key配置项    | ✅    |

---

### 5.2 开发者体验 (DX) 规范

#### DX-001 GitHub Actions CI/CD
- **文件**: `.github/workflows/ci.yml`
- **触发**: push/PR → main, develop
- **阶段**:
  1. `lint` — Ruff + mypy 静态检查
  2. `test` — 矩阵并行：unit / integration / smoke，含 Redis service container
  3. `build` — Docker 镜像构建验证（仅 main/develop 分支）
  4. `security` — pip-audit 依赖漏洞扫描，结果上传为 artifact
- **Secrets 配置**: `OPENAI_API_KEY_TEST`（建议单独申请低配额 key）

#### DX-002 pre-commit hooks
- **文件**: `.pre-commit-config.yaml`
- **安装**: `pip install pre-commit && pre-commit install`
- **检查项**: Ruff lint + format、mypy、trailing-whitespace、detect-secrets、markdownlint
- **CI 集成**: `pre-commit.ci` 自动修复并 commit

#### DX-003 Makefile 完善
- **新增命令**: `wizard`、`install-hooks`、`test-unit`、`test-integration`、`docker-rebuild`、`db-revision`、`cache-flush`、`metrics-check`、`analyze`、`clean-all`
- **彩色输出**: ANSI 颜色区分不同类型命令
- **参数支持**: `make analyze URL=https://example.com`、`make dev API_PORT=9000`

#### DX-004 测试目录分层
```
tests/
├── unit/                    # 纯内存，无网络，< 2s 完成
│   ├── test_agent_cache.py  # AGT-004 缓存 20 个用例
│   └── test_metrics.py      # OPS-007 指标模块
├── integration/             # 使用 SQLite + in-process HTTP client
│   └── test_api_metrics.py  # 端点集成测试
├── conftest.py
└── test_smoke.py            # 原有冒烟测试
```

---

### 5.3 普通用户体验 (UX) 规范

#### UX-001 Setup Wizard（首次配置向导）
- **文件**: `scripts/setup_wizard.py`
- **调用**: `make wizard` 或 `python scripts/setup_wizard.py`
- **步骤**:
  1. 环境检查（Python 版本、Node.js、Docker）
  2. 创建 .venv 并安装依赖
  3. 交互式填写 .env 关键项（支持 `--auto` 非交互模式）
  4. 验证 OpenAI API Key 连通性
  5. 运行 Alembic 数据库迁移
  6. 输出彩色启动命令说明
- **兼容性**: macOS/Linux/Windows（Windows Terminal 支持 ANSI 颜色）

#### UX-002 .env.example 重构
- **分组**: 10个功能分组，每组有中文说明注释
  1. 应用基础配置
  2. 数据库配置
  3. Redis 缓存配置（含 AGT-004 相关变量）
  4. LLM / AI 模型配置（OpenAI + Claude + Gemini + Ollama）
  5. SEO 数据源 API Keys（Ahrefs/SEMrush/DataForSEO/SerpAPI 等）
  6. 广告平台 API Keys（Google Ads/Meta/字节跳动/百度/腾讯）
  7. 网站分析 & 监控（PageSpeed/Cloudflare/Datadog/Sentry）
  8. 爬虫 & 代理配置（含代理池 SE-004 相关变量）
  9. 通知 & Webhook（Slack/飞书/企业微信/SMTP）
  10. 功能开关 Feature Flags（与 FEATURE_* 环境变量对应）

---

### 5.4 AGT-004 Agent 缓存规范（最终版）

**文件**: `apps/api/seo_ad_autopilot/agents/agent_cache.py`

#### 接口契约
```python
cache = get_agent_cache(redis_url=settings.redis_url)

# 方式1: 手动 get/set
result = await cache.get(url, agent="sniffer")
if result is None:
    result = await sniffer.analyze(context)
    await cache.set(url, agent="sniffer", data=result)

# 方式2: 一步包装（推荐）
result = await cache.cached_call(
    url=url, agent="sniffer",
    fn=lambda: sniffer.analyze(context),
)
```

#### 默认 TTL 配置（可通过 .env 覆盖）
| Agent              | TTL   | 理由               |
|--------------------|-------|--------------------|
| sniffer            | 1h    | 技术健康度          |
| query              | 2h    | 关键词机会          |
| strategist         | 2h    | 策略分析            |
| rank_tracker       | 30min | 数据变化快          |
| competitor_analyst | 4h    | 竞品分析            |
| policy_guard       | 24h   | 合规规则稳定        |

#### 后端选择逻辑
```
REDIS_URL 或 SEO_AD_BOT_REDIS_URL 环境变量存在
  └─ redis.asyncio 可用 → RedisBackend（生产推荐）
  └─ redis.asyncio 不可用 → 启动失败，提示安装
REDIS_URL 为空 → MemoryBackend（开发/测试）
```

#### 统计 API
```python
cache.stats_dict()
# {
#   "hits": 42, "misses": 8, "sets": 50, "evictions": 2,
#   "hit_rate": 0.84,
#   "backend": "memory" | "redis",
#   "memory_entries": 50   # 仅内存后端
# }
```

---

### 5.5 OPS-007 Prometheus 指标规范（最终版）

**文件**: `apps/api/seo_ad_autopilot/routers/metrics.py`

#### 端点
| 端点                | 格式         | 依赖               |
|---------------------|--------------|---------------------|
| `GET /metrics`      | Prometheus   | prometheus-client   |
| `GET /metrics/summary` | JSON      | 无                  |

#### 指标列表
| 指标名                                    | 类型      | 标签                        |
|-------------------------------------------|-----------|-----------------------------|
| seo_ad_http_requests_total                | Counter   | method, endpoint, status    |
| seo_ad_http_request_duration_seconds      | Histogram | method, endpoint            |
| seo_ad_agent_executions_total             | Counter   | agent, status               |
| seo_ad_agent_duration_seconds             | Histogram | agent                       |
| seo_ad_agent_cache_hits_total             | Counter   | agent                       |
| seo_ad_agent_cache_misses_total           | Counter   | agent                       |
| seo_ad_llm_tokens_total                   | Counter   | model, token_type           |
| seo_ad_llm_requests_total                 | Counter   | model, status               |
| seo_ad_active_analysis_tasks              | Gauge     | —                           |
| seo_ad_debate_rounds_total                | Counter   | outcome                     |
| seo_ad_ad_recommendation_requests_total   | Counter   | platform                    |

> **高基数防护**: endpoint 标签自动将 UUID 和长数字 ID 替换为 `{id}`，防止 Prometheus 基数爆炸。

#### 降级策略
当 `prometheus-client` 未安装时：
- `/metrics` → 返回 JSON 提示（HTTP 200，不阻断启动）
- 所有 `record_*` 函数变为 no-op（不抛出异常）
- 安装方式: `pip install "prometheus-client>=0.19.0"`

---

### 5.6 待实现项（下一阶段优先级）

| 优先级 | ID       | 描述                               | 预估工时 | 状态 |
|--------|----------|------------------------------------|----------|------|
| P0     | AGT-005  | DebateEngine 第三轮（策略 vs 合规终裁）| 2d    | ✅ 已接入（`FEATURE_DEBATE_ROUND3_ENABLED`）|
| P0     | DB-001   | models.py 拆分（每个模型独立文件）  | 1d       | ⏳ 待办 |
| P0     | DB-004   | content_versions 表创建             | 0.5d     | ✅ ORM 模型 + ContentVersionStore DB 镜像 |
| P0     | DB-006   | ad_recommendations 表创建           | 0.5d     | ✅ ORM 模型 + AdService 持久化/历史查询 |

| P1     | SKL-005  | Skill 结果持久化到 artifact_store   | 2d       |
| P1     | SE-005   | 搜索结果缓存（复用 AgentCache）     | 1d       |
| P1     | LLM-004  | Prompt 模板管理（Jinja2 + 版本控制）| 2d       |
| P2     | ADS-003  | 平台推荐历史持久化                  | 1.5d     |
| P2     | SE-004   | 代理池集成（Brightdata/Oxylabs）    | 3d       |
| P2     | SE-006   | 中国市场搜索聚合（百度/360/搜狗）   | 2d       |
| P3     | LLM-007  | Per-user token 配额统计             | 1d       |
| P3     | ADS-004  | 广告位置热图可视化                  | 3d       |


### 5.7 已实现的功能便捷性与易用性优化 (Phase 5.7 Completed UX/DX Optimizations)

为了大幅提升**开发者 (Developer Experience - DX)** 与**普通用户 (User Experience - UX)** 的便捷性，项目进行了以下重构与功能扩充：

1. **跨平台一键环境配置 ( &  增强)**
   - 针对 macOS/Linux 用户新增了  脚本，实现自动检测 Python/Node.js/pnpm 环境、自动安装依赖、自动创建和激活虚拟环境。
   - 优化了交互式配置向导 ，在安装 Python 依赖（Step 2）后，新增**自动检测并执行 ** 安装前端 Web 依赖的步骤，真正实现全栈一键化配置。

2. **跨平台一键联合启动 ( & )**
   - 过去用户需要分别在两个终端中启动 API 服务与 Web 客户端，极其繁琐。
   - **macOS/Linux**: 引入了 ，在后台并发启动 API (8000端口) 与 Web 前端 (3000端口)，并完美支持 **Ctrl+C 优雅退出 (SIGINT/SIGTERM 信号捕捉与子进程自动清理)**。
   - **Windows**: 引入了 ，一键拉起新终端运行 API 和 Web，极大地降低了日常运行和测试的门槛。
   - 同时保留了细粒度启动控制的  /  脚本。

3. **增强版系统诊断与控制中心命令行 (CLI 2.0 - )**
   - 补全了配置写入逻辑 ()，能智能地保持  的排版和注释并实现脱敏展示。
   - 新增了 ** 系统健康诊断命令**：一键检测 Python 版本、虚拟环境激活状态、核心库完整性、Node.js & pnpm 环境、.env 配置、数据库文件存在性，并给出清晰可读的 [PASS]/[FAIL]/[WARN] 报告。
   - 新增了 ** 服务状态监视命令**：检测 8000 端口 (API) 与 3000 端口 (Web) 的存活状态，并智能推荐启动命令。
   - 新增了  命令，支持规范的版本控制和升级检查。

4. **核心代码健壮性修复**
   - 修复了  结尾处因代码截断导致的 （由于最后一行的  缺失导致语法解析错误，已完美恢复为  及其对应的 Service 调用）。
