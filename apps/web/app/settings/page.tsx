"use client";

import { useState } from "react";
import { useI18n } from "@/lib/i18n";

type Tab = "setup" | "search" | "social" | "ads" | "skills" | "general";

export default function SettingsPage() {
  const { t } = useI18n();
  const [activeTab, setActiveTab] = useState<Tab>("setup");
  const [expandedSection, setExpandedSection] = useState<string | null>(null);

  const toggleSection = (section: string) => {
    setExpandedSection(expandedSection === section ? null : section);
  };

  return (
    <div className="page">
      <section className="hero">
        <div className="eyebrow">{t("nav.settings")}</div>
        <h1>{t("settings.title")}</h1>
        <p className="hero-copy">{t("settings.hero_description")}</p>
      </section>

      {/* Tab Navigation */}
      <section className="panel">
        <div className="tab-nav">
          {[
            { id: "setup", label: "配置指南" },
            { id: "search", label: "搜索引擎" },
            { id: "social", label: "社交媒体" },
            { id: "ads", label: t("ads.title") },
            { id: "skills", label: t("settings.skills") },
            { id: "general", label: t("settings.configuration") },
          ].map((tab) => (
            <button
              key={tab.id}
              className={`tab-btn ${activeTab === tab.id ? "active" : ""}`}
              onClick={() => setActiveTab(tab.id as Tab)}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </section>

      {/* Setup Guide */}
      {activeTab === "setup" && (
        <section className="panel">
          <div className="section-heading">
            <div>
              <div className="eyebrow">快速开始</div>
              <h2>完整配置流程</h2>
            </div>
          </div>
          <div className="setup-steps">
            {[
              { id: "1", title: "安装与启动", desc: "make api-dev && make web-dev", done: true },
              { id: "2", title: "配置搜索引擎 API", desc: "Google/Bing/百度等", done: true },
              { id: "3", title: "配置社交媒体 API", desc: "小红书/抖音/微博/X等", done: true },
              { id: "4", title: "配置广告平台", desc: "AdSense/Mediavine等", done: true },
              { id: "5", title: "首次分析", desc: "输入URL开始分析", active: true },
              { id: "6", title: "查看结果", desc: "审查GEO评分和推荐", done: false },
            ].map((step) => (
              <div key={step.id} className={`setup-step ${step.done ? "done" : step.active ? "active" : ""}`}>
                <div className={`step-icon ${step.done ? "good" : step.active ? "accent" : "neutral"}`}>
                  {step.done ? "✓" : step.active ? "→" : step.id}
                </div>
                <div className="step-content">
                  <strong>{step.title}</strong>
                  <span>{step.desc}</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Search Engines */}
      {activeTab === "search" && (
        <section className="panel">
          <div className="section-heading">
            <div>
              <div className="eyebrow">搜索引擎配置</div>
              <h2>支持的搜索引擎</h2>
            </div>
          </div>

          {/* 国际搜索引擎 */}
          <div className="config-section">
            <div className="config-section-header" onClick={() => toggleSection("intl_search")}>
              <h3>🌍 国际搜索引擎</h3>
              <span className="toggle-icon">{expandedSection === "intl_search" ? "−" : "+"}</span>
            </div>
            {expandedSection === "intl_search" && (
              <div className="config-grid">
                {[
                  { name: "Google", env: "SEO_AD_BOT_GOOGLE_API_KEY", desc: "Custom Search API", docs: "console.cloud.google.com" },
                  { name: "Bing", env: "SEO_AD_BOT_BING_API_KEY", desc: "Web Search API", docs: "portal.azure.com" },
                  { name: "Yandex", env: "SEO_AD_BOT_YANDEX_API_KEY", desc: "XML Search API", docs: "yandex.com/dev" },
                  { name: "DuckDuckGo", env: "", desc: "隐私搜索 (内置)", docs: "", status: "内置支持" },
                  { name: "Naver", env: "SEO_AD_BOT_NAVER_API_KEY", desc: "韩国搜索引擎", docs: "developers.naver.com" },
                ].map((engine) => (
                  <article className="config-card" key={engine.name}>
                    <div className="config-header">
                      <strong>{engine.name}</strong>
                      <span className={`status-badge ${engine.status === "内置支持" ? "good" : "warn"}`}>
                        {engine.status || "需要 API Key"}
                      </span>
                    </div>
                    <div className="config-meta">
                      <span>{engine.desc}</span>
                    </div>
                    {engine.env && (
                      <div className="config-env">
                        <code>{engine.env}</code>
                      </div>
                    )}
                    {engine.docs && (
                      <a className="config-link" href={`https://${engine.docs}`} target="_blank" rel="noopener noreferrer">
                        获取 API Key →
                      </a>
                    )}
                  </article>
                ))}
              </div>
            )}
          </div>

          {/* 国内搜索引擎 */}
          <div className="config-section">
            <div className="config-section-header" onClick={() => toggleSection("cn_search")}>
              <h3>🇨🇳 国内搜索引擎</h3>
              <span className="toggle-icon">{expandedSection === "cn_search" ? "−" : "+"}</span>
            </div>
            {expandedSection === "cn_search" && (
              <div className="config-grid">
                {[
                  { name: "百度", env: "SEO_AD_BOT_BAIDU_API_KEY", desc: "百度站长平台 API", docs: "ziyuan.baidu.com" },
                  { name: "搜狗", env: "SEO_AD_BOT_SOGOU_API_KEY", desc: "搜狗站长平台", docs: "sogou.com/webmaster" },
                  { name: "360 搜索", env: "SEO_AD_BOT_360_API_KEY", desc: "360 站长平台", docs: "zhanzhang.so.com" },
                ].map((engine) => (
                  <article className="config-card" key={engine.name}>
                    <div className="config-header">
                      <strong>{engine.name}</strong>
                      <span className="status-badge warn">需要 API Key</span>
                    </div>
                    <div className="config-meta">
                      <span>{engine.desc}</span>
                    </div>
                    <div className="config-env">
                      <code>{engine.env}</code>
                    </div>
                    <a className="config-link" href={`https://${engine.docs}`} target="_blank" rel="noopener noreferrer">
                      获取 API Key →
                    </a>
                  </article>
                ))}
              </div>
            )}
          </div>

          {/* AI 搜索引擎 */}
          <div className="config-section">
            <div className="config-section-header" onClick={() => toggleSection("ai_search")}>
              <h3>🤖 AI 搜索引擎 (GEO)</h3>
              <span className="toggle-icon">{expandedSection === "ai_search" ? "−" : "+"}</span>
            </div>
            {expandedSection === "ai_search" && (
              <>
                <h4 style={{ margin: "12px 0 8px", fontSize: "0.85rem", color: "var(--muted)" }}>🌍 国际 AI</h4>
                <div className="config-grid">
                  {[
                    { name: "ChatGPT", desc: "OpenAI GPT 搜索", status: "内置支持" },
                    { name: "Perplexity", desc: "AI 搜索引擎", status: "内置支持" },
                    { name: "Claude", desc: "Anthropic AI 搜索", status: "内置支持" },
                    { name: "Gemini", desc: "Google AI 搜索", status: "内置支持" },
                    { name: "Grok", desc: "xAI 搜索", status: "内置支持" },
                    { name: "Mistral", desc: "欧洲 AI 搜索", status: "内置支持" },
                    { name: "Llama", desc: "Meta AI 搜索", status: "内置支持" },
                  ].map((engine) => (
                    <article className="config-card" key={engine.name}>
                      <div className="config-header">
                        <strong>{engine.name}</strong>
                        <span className="status-badge good">{engine.status}</span>
                      </div>
                      <div className="config-meta">
                        <span>{engine.desc}</span>
                      </div>
                    </article>
                  ))}
                </div>
                <h4 style={{ margin: "16px 0 8px", fontSize: "0.85rem", color: "var(--muted)" }}>🇨🇳 国内 AI</h4>
                <div className="config-grid">
                  {[
                    { name: "文心一言", desc: "百度 AI 搜索引擎", status: "内置支持" },
                    { name: "通义千问", desc: "阿里 AI 搜索引擎", status: "内置支持" },
                    { name: "讯飞星火", desc: "科大讯飞 AI 搜索", status: "内置支持" },
                    { name: "豆包", desc: "字节跳动 AI 搜索", status: "内置支持" },
                    { name: "Kimi", desc: "月之暗面 AI 搜索", status: "内置支持" },
                    { name: "DeepSeek", desc: "深度求索 AI 搜索", status: "内置支持" },
                  ].map((engine) => (
                    <article className="config-card" key={engine.name}>
                      <div className="config-header">
                        <strong>{engine.name}</strong>
                        <span className="status-badge good">{engine.status}</span>
                      </div>
                      <div className="config-meta">
                        <span>{engine.desc}</span>
                      </div>
                    </article>
                  ))}
                </div>
              </>
            )}
          </div>
        </section>
      )}

      {/* Social Media */}
      {activeTab === "social" && (
        <section className="panel">
          <div className="section-heading">
            <div>
              <div className="eyebrow">社交媒体配置</div>
              <h2>支持的社交媒体平台</h2>
            </div>
          </div>

          {/* 国内社交媒体 */}
          <div className="config-section">
            <div className="config-section-header" onClick={() => toggleSection("cn_social")}>
              <h3>🇨🇳 国内社交媒体</h3>
              <span className="toggle-icon">{expandedSection === "cn_social" ? "−" : "+"}</span>
            </div>
            {expandedSection === "cn_social" && (
              <div className="config-grid">
                {[
                  { name: "小红书", env: "SEO_AD_BOT_XIAOHONGSHU_API_KEY", desc: "生活方式分享平台", docs: "open.xiaohongshu.com" },
                  { name: "抖音", env: "SEO_AD_BOT_DOUYIN_API_KEY", desc: "短视频平台", docs: "open.douyin.com" },
                  { name: "微博", env: "SEO_AD_BOT_WEIBO_API_KEY", desc: "社交媒体平台", docs: "open.weibo.com" },
                  { name: "微信公众号", env: "SEO_AD_BOT_WECHAT_APP_ID", desc: "内容创作平台", docs: "mp.weixin.qq.com" },
                ].map((platform) => (
                  <article className="config-card" key={platform.name}>
                    <div className="config-header">
                      <strong>{platform.name}</strong>
                      <span className="status-badge warn">需要 API Key</span>
                    </div>
                    <div className="config-meta">
                      <span>{platform.desc}</span>
                    </div>
                    <div className="config-env">
                      <code>{platform.env}</code>
                    </div>
                    <a className="config-link" href={`https://${platform.docs}`} target="_blank" rel="noopener noreferrer">
                      获取 API Key →
                    </a>
                  </article>
                ))}
              </div>
            )}
          </div>

          {/* 国际社交媒体 */}
          <div className="config-section">
            <div className="config-section-header" onClick={() => toggleSection("intl_social")}>
              <h3>🌍 国际社交媒体</h3>
              <span className="toggle-icon">{expandedSection === "intl_social" ? "−" : "+"}</span>
            </div>
            {expandedSection === "intl_social" && (
              <div className="config-grid">
                {[
                  { name: "X (Twitter)", env: "SEO_AD_BOT_TWITTER_API_KEY", desc: "微博客平台", docs: "developer.twitter.com" },
                  { name: "Instagram", env: "SEO_AD_BOT_INSTAGRAM_ACCESS_TOKEN", desc: "图片/视频分享", docs: "developers.facebook.com" },
                  { name: "YouTube", env: "SEO_AD_BOT_YOUTUBE_API_KEY", desc: "视频平台", docs: "console.developers.google.com" },
                  { name: "LinkedIn", env: "SEO_AD_BOT_LINKEDIN_ACCESS_TOKEN", desc: "职业社交", docs: "linkedin.com/developers" },
                ].map((platform) => (
                  <article className="config-card" key={platform.name}>
                    <div className="config-header">
                      <strong>{platform.name}</strong>
                      <span className="status-badge warn">需要 API Key</span>
                    </div>
                    <div className="config-meta">
                      <span>{platform.desc}</span>
                    </div>
                    <div className="config-env">
                      <code>{platform.env}</code>
                    </div>
                    <a className="config-link" href={`https://${platform.docs}`} target="_blank" rel="noopener noreferrer">
                      获取 API Key →
                    </a>
                  </article>
                ))}
              </div>
            )}
          </div>
        </section>
      )}

      {/* Ad Platforms */}
      {activeTab === "ads" && (
        <section className="panel">
          <div className="section-heading">
            <div>
              <div className="eyebrow">{t("ads.title")}</div>
              <h2>{t("ads.auto_discover")}</h2>
            </div>
          </div>
          <div className="config-section">
            <div className="config-section-header" onClick={() => toggleSection("ad_platforms")}>
              <h3>💰 广告平台</h3>
              <span className="toggle-icon">{expandedSection === "ad_platforms" ? "−" : "+"}</span>
            </div>
            {expandedSection === "ad_platforms" && (
              <div className="config-grid">
                {[
                  { name: "Google AdSense", type: "adsense", traffic: "1,000+", desc: "最简单的广告接入方式" },
                  { name: "Mediavine", type: "programmatic", traffic: "50,000+", desc: "内容站首选，高 RPM" },
                  { name: "Ezoic", type: "programmatic", traffic: "10,000+", desc: "AI 驱动优化" },
                  { name: "AdThrive", type: "programmatic", traffic: "100,000+", desc: "大型发布商" },
                  { name: "Monumetric", type: "programmatic", traffic: "10,000+", desc: "中型站点" },
                  { name: "PubMatic", type: "programmatic", traffic: "50,000+", desc: "程序化广告" },
                ].map((platform) => (
                  <article className="config-card" key={platform.name}>
                    <div className="config-header">
                      <strong>{platform.name}</strong>
                      <span className="status-badge accent">{platform.type}</span>
                    </div>
                    <div className="config-meta">
                      <span>最低流量: {platform.traffic}/月</span>
                    </div>
                    <div className="config-desc">{platform.desc}</div>
                  </article>
                ))}
              </div>
            )}
          </div>
        </section>
      )}

      {/* Skills */}
      {activeTab === "skills" && (
        <section className="panel">
          <div className="section-heading">
            <div>
              <div className="eyebrow">{t("settings.skills")}</div>
              <h2>{t("settings.registered_skills")}</h2>
            </div>
          </div>
          <div className="config-grid">
            {[
              { name: "SiteCrawler", cat: "crawl", risk: "read_only", desc: "网站抓取" },
              { name: "StyleExtractor", cat: "analyze", risk: "read_only", desc: "风格提取" },
              { name: "SiteAnalyzer", cat: "analyze", risk: "read_only", desc: "站点分析" },
              { name: "InternalLinkBuilder", cat: "analyze", risk: "low", desc: "内部链接" },
              { name: "ContentGenerator", cat: "generate", risk: "medium", desc: "内容生成" },
              { name: "SchemaBuilder", cat: "generate", risk: "low", desc: "结构化数据" },
              { name: "AdWrapperRenderer", cat: "generate", risk: "medium", desc: "广告容器" },
              { name: "AdTelemetryBinder", cat: "generate", risk: "low", desc: "广告埋点" },
              { name: "SitemapUpdater", cat: "deploy", risk: "low", desc: "站点地图" },
              { name: "ContentModulePublisher", cat: "deploy", risk: "high", desc: "内容发布" },
              { name: "GitHubPRCreator", cat: "deploy", risk: "high", desc: "PR 创建" },
              { name: "CMSPublisher", cat: "deploy", risk: "high", desc: "CMS 发布" },
              { name: "MetricsCollector", cat: "monitor", risk: "read_only", desc: "指标收集" },
              { name: "AlertManager", cat: "monitor", risk: "low", desc: "告警管理" },
              { name: "PerfProbeBinder", cat: "monitor", risk: "low", desc: "性能监控" },
            ].map((skill) => (
              <article className="config-card" key={skill.name}>
                <div className="config-header">
                  <strong>{skill.name}</strong>
                  <span className={`status-badge ${skill.risk === "high" ? "danger" : skill.risk === "medium" ? "warn" : "good"}`}>
                    {skill.risk}
                  </span>
                </div>
                <div className="config-meta">
                  <span className="config-type">{skill.cat}</span>
                  <span>{skill.desc}</span>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      {/* General Settings */}
      {activeTab === "general" && (
        <section className="panel">
          <div className="section-heading">
            <div>
              <div className="eyebrow">通用配置</div>
              <h2>系统设置</h2>
            </div>
          </div>
          <div className="settings-grid">
            {[
              { label: "Auto Deploy", type: "checkbox", default: false },
              { label: "Approval Threshold", type: "number", default: 60 },
              { label: "Block Threshold", type: "number", default: 80 },
              { label: "Monitor Window (min)", type: "number", default: 90 },
              { label: "Rollback Window (min)", type: "number", default: 5 },
              { label: "Auto Cruise", type: "checkbox", default: false },
              { label: "Strict Providers", type: "checkbox", default: false },
            ].map((setting) => (
              <div className="setting-item" key={setting.label}>
                <label className="setting-label">{setting.label}</label>
                <div className="setting-control">
                  {setting.type === "checkbox" ? (
                    <input type="checkbox" defaultChecked={setting.default as boolean} />
                  ) : (
                    <input type="number" defaultValue={setting.default as number} min="0" />
                  )}
                </div>
              </div>
            ))}
          </div>

          <div style={{ marginTop: 20 }}>
            <h3 style={{ marginBottom: 12 }}>环境变量配置</h3>
            <div className="settings-grid">
              {[
                { label: "API Key", env: "SEO_AD_BOT_API_KEY", type: "password" },
                { label: "Database URL", env: "DATABASE_URL", type: "text", default: "sqlite:///./var/seo-ad-autopilot.db" },
                { label: "Redis URL", env: "REDIS_URL", type: "text", default: "redis://localhost:6379/0" },
              ].map((setting) => (
                <div className="setting-item" key={setting.env}>
                  <label className="setting-label">{setting.label}</label>
                  <div className="setting-control">
                    <input type={setting.type} defaultValue={setting.default || ""} placeholder={setting.env} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
