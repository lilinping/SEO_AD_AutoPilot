# SEO-AD AutoPilot - 阶段开发与生产闭环任务清单 (TODO List)

为了实现从当前“偏展示/本地状态”到**“全功能生产闭环”**的跨越，以下梳理了完整的待办任务清单和当前的最新开发进展。

---

## 📋 核心开发任务清单 (Task Backlog) & 最新进展

### 1. `/ecommerce` & `/keywords` 路由后端真实对接
- [ ] **`/ecommerce` 后端对接 (中高优先级)**
  - **当前状态**：前端 `apps/web/app/ecommerce/page.tsx` 已经编写了完整的 UI 与请求逻辑（向 `${API_BASE}/ecommerce/analyze` 发送 POST），后端也有 `EcommerceAnalysisSkill` 核心分析逻辑。
  - **待办任务**：
    - 确保 `EcommerceAnalysisSkill` 中针对 Amazon、Shopify 等平台的爬取与解析器已经具备真实抓取或 API 凭证，移除 Mock fallback 逻辑。
    - 联调并确保请求没有跨域（CORS）阻碍。
- [ ] **`/keywords` 后端对接 (中高优先级)**
  - **当前状态**：前端已实现单/多关键词调研、分类聚类 UI。
  - **待办任务**：
    - 将 `KeywordResearchSkill` 内的搜索引擎数据采集逻辑从 `fallback/synthetic` 数据源切换为真实的 Google Custom Search API、Bing Web Search API 或百度站长 API。
    - 实现对 `target_market`（如 US, CN 等）的地域专属 Volume 真实采集与系数微调。

### 2. `/settings` 配置面板读写闭环
- [x] **后端配置读写 API 落地 (高优先级) — 🎉 已完成**
  - **当前进展**：已在 `apps/api/seo_ad_autopilot/routers/settings.py` 中实现了完整的 GET 和 POST 端点。配置会被安全地读写并持久化到项目根目录下的 `var/settings.json` 中，并在保存时动态将变量同步至 `os.environ` 环境变量中。
  - **配置加载路由**：已在 `apps/api/seo_ad_autopilot/routers/__init__.py` 中完成模块化路由器注册，完美适配整体 FastAPI 生命周期。
- [x] **前端配置读写闭环 — 🎉 已完成**
  - **当前进展**：已重构前端 `apps/web/app/settings/page.tsx` 页面。使用了动态 React 状态接管，在 `useEffect` 中自动向后端获取配置进行初始化填充。
  - **保存闭环**：添加了“保存设置”功能按钮与加载、保存中状态、保存成功/失败 banner。输入参数点击保存后，前端配置会实时通过 `fetch` 的 `POST` 请求同步回后端持久化保存，实现了真正的前后端读写闭环。

### 3. Next.js 编译噪音消除 (`Dynamic server usage` Fallback)
- [x] **构建编译配置优化 (中优先级) — 🎉 已完成**
  - **当前进展**：通过对可能引起动态渲染噪音的 `apps/web/app/ecommerce/page.tsx` 和 `apps/web/app/keywords/page.tsx` 页面文件末尾显式声明 `export const dynamic = "force-dynamic";`，明确告知编译链这是动态服务端渲染路由，完美解决了 `next build` 阶段由于未指定静态/动态而产生的 fallback 噪音警告。

### 4. 运行环境与启动脚本整理
- [ ] **补全普通 Shell 环境下的全局 PATH**
  - **当前状态**：普通 Shell 启动经常找不到 `pnpm / node / git`。
  - **待办任务**：
    - 整理 `start-all.sh`、`start-web.sh` 和 `start-api.sh` 脚本，在脚本顶部显式、自动地寻找本地 Node.js 路径，或者通过软链接补充全局 PATH。
- [ ] **PNPM 一键安装与环境预检**
  - **待办任务**：
    - 在 `setup.sh` 中增加 Node.js 与 pnpm 自动预检逻辑，不存在时提示引导安装。

### 5. 外部 Provider 凭证闭环 (搜索引擎、结算、发布网关)
- [ ] **全面打通真实凭证流程**
  - **当前状态**：在没有真实凭证时，系统退回到 `synthetic`（合成数据）或 `fallback` 状态。
  - **待办任务**：
    - 统一梳理 Google/Bing 搜索、各主流广告平台（AdSense/Mediavine）以及发布网关（GitHub/CMS）的配置读取逻辑。
    - 确保在 `.env` 中缺少对应 API Key 时，有清晰的“未配置”提示和操作指南，而不是生硬地抛出执行错误。

---

## 🔄 开发状态同步记录

| 任务模块 | 前端状态 | 后端状态 | 闭环瓶颈 | 推荐下一步 |
| :--- | :--- | :--- | :--- | :--- |
| **电商分析** | 页面逻辑已就绪 | `routers/ecommerce.py` 已通，Skill 逻辑已通 | 真实爬取/抓取链路未完全闭环 | 联调试运行抓取真实网页，消除 noise 已完成 |
| **关键词研究** | 页面逻辑已就绪 | `routers/keywords.py` 已通，Skill 逻辑已通 | 真实搜索引擎 API 绑定 | 配置真实 Google Custom API 测试，noise 已消除 |
| **设置面板** | 🎉 **动态读写就绪** | 🎉 **GET/POST 路由及持久化已跑通** | 无（已实现完全闭环） | 在 UI 界面调试环境变量保存并校验 |

*此文件作为开发接力棒。后续任何 AI 助手或开发人员启动时，均可直接读取此文件继续任务开发。*
