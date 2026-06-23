# SEO-AD AutoPilot - 重构架构

## 核心变化

本次重构将项目从"Google 专属 SEO 工具"升级为**多搜索引擎 + GEO + 多广告平台**的增长执行平台。

### 1. 搜索引擎抽象层 (`search_engines/`)

支持所有主流搜索引擎，包括传统 SEO 和 GEO（生成式引擎优化）：

| 引擎 | 类型 | 说明 |
|------|------|------|
| Google | SEO | 传统搜索优化 |
| Bing | SEO | 微软搜索优化 |
| Baidu | SEO | 百度搜索优化（中国市场） |
| Yandex | SEO | Yandex 搜索优化（俄罗斯市场） |
| ChatGPT | GEO | ChatGPT 搜索优化 |
| Perplexity | GEO | Perplexity AI 搜索优化 |
| Claude | GEO | Claude AI 搜索优化 |

**GEO 优化要点**：
- 引用信号：内容需要有清晰的来源和数据支持
- 实体优化：结构化数据帮助 AI 理解实体
- 内容结构：清晰的标题、列表、表格便于 AI 解析
- 权威信号：作者信息、发布日期、更新时间

### 2. 广告平台抽象层 (`ad_platforms/`)

支持多种广告平台，自动发现和适配最佳平台：

| 平台 | 类型 | 最低流量要求 |
|------|------|-------------|
| Google AdSense | AdSense | 1,000+ 月访问 |
| Mediavine | Programmatic | 50,000+ 月会话 |
| Ezoic | Programmatic | 10,000+ 月访问 |
| AdThrive | Programmatic | 100,000+ 月页面浏览 |
| Monumetric | Programmatic | 10,000+ 月页面浏览 |
| PubMatic | Programmatic | 50,000+ 月访问 |

**自动适配逻辑**：
- 根据站点类型推荐最合适的平台
- 根据流量规模评估平台可行性
- 考虑地区、内容类型、变现目标

### 3. Agent 体系 (`agents/`)

借鉴 BettaFish 的多 Agent 辩论机制：

| Agent | 职责 | 输入 | 输出 |
|-------|------|------|------|
| Sniffer | 站点分析 | URL、DOM、Meta | SiteProfile |
| Query | 机会搜索 | SiteProfile、趋势源 | OpportunitySet |
| GEO | GEO 分析 | 站点数据 | GEO 优化建议 |
| Strategist | 策略综合 | 所有 Agent 输出 | 执行计划 |
| UX Reviewer | UX 审查 | 策略、页面结构 | 布局建议、风险评分 |
| Coordinator | 工作流编排 | 所有 Agent 输出 | Skill 调用序列 |

**辩论机制**：
- Agent 可以挑战其他 Agent 的结论
- 挑战者提出质疑，被挑战者辩护
- 最终综合得出更可靠的结论

### 4. Skill 体系 (`skills/`)

借鉴 OpenClaw 的可插拔 Skill 注册：

| Skill | 类别 | 风险等级 | 说明 |
|-------|------|---------|------|
| SiteCrawler | Crawl | Read-only | 网站抓取 |
| StyleExtractor | Analyze | Read-only | 风格提取 |
| SiteAnalyzer | Analyze | Read-only | 站点分析 |
| ContentGenerator | Generate | Medium | 内容生成 |
| SchemaBuilder | Generate | Low | 结构化数据 |
| GitHubPRCreator | Deploy | High | GitHub PR 创建 |
| CMSPublisher | Deploy | High | CMS 发布 |
| MetricsCollector | Monitor | Read-only | 指标收集 |
| AlertManager | Monitor | Low | 告警管理 |

**Skill 特性**：
- 标准化的输入/输出 schema
- 风险等级分类
- 审批门控
- 可回滚性

## 架构优势

1. **搜索引擎无关**：不再绑定 Google，支持全球所有主流搜索引擎
2. **GEO 原生支持**：针对 ChatGPT/Perplexity/Claude 等 AI 搜索引擎优化
3. **多广告平台**：自动发现和适配最佳广告平台
4. **Agent 协同**：多 Agent 辩论机制提高分析可靠性
5. **Skill 可插拔**：标准化 Skill 接口，易于扩展

## 下一步

1. 实现真实的搜索引擎 API 集成
2. 实现真实的广告平台 API 集成
3. 完善 Agent 辩论机制
4. 添加更多 Skill 实现
5. 构建前端控制台
