"use client";

import { useState } from "react";
import Link from "next/link";
import { useI18n } from "@/lib/i18n";

// ── Plan definitions ─────────────────────────────────────────────────────────

type PlanTier = "free" | "pro" | "team" | "enterprise";

interface PlanFeature {
  label: string;
  free: string | boolean;
  pro: string | boolean;
  team: string | boolean;
  enterprise: string | boolean;
}

const PLANS: {
  id: PlanTier;
  name: string;
  monthlyPrice: number | null;
  yearlyPrice: number | null;
  badge?: string;
  cta: string;
  ctaHref: string;
  highlight: boolean;
}[] = [
  {
    id: "free",
    name: "免费版",
    monthlyPrice: 0,
    yearlyPrice: 0,
    cta: "立即开始",
    ctaHref: "/analyze",
    highlight: false,
  },
  {
    id: "pro",
    name: "专业版",
    monthlyPrice: 29,
    yearlyPrice: 23,
    badge: "推荐",
    cta: "升级至专业版",
    ctaHref: "/api/billing/checkout?plan=pro",
    highlight: true,
  },
  {
    id: "team",
    name: "团队版",
    monthlyPrice: 79,
    yearlyPrice: 63,
    cta: "升级至团队版",
    ctaHref: "/api/billing/checkout?plan=team",
    highlight: false,
  },
  {
    id: "enterprise",
    name: "企业版",
    monthlyPrice: null,
    yearlyPrice: null,
    cta: "联系销售",
    ctaHref: "mailto:sales@seo-ad-autopilot.com",
    highlight: false,
  },
];

const FEATURES: PlanFeature[] = [
  // Usage limits
  {
    label: "站点数量",
    free: "1 个站点",
    pro: "10 个站点",
    team: "50 个站点",
    enterprise: "不限",
  },
  {
    label: "每月分析次数",
    free: "20 次/月",
    pro: "500 次/月",
    team: "2,000 次/月",
    enterprise: "不限",
  },
  {
    label: "内容生成配额",
    free: "10 篇/月",
    pro: "200 篇/月",
    team: "1,000 篇/月",
    enterprise: "不限",
  },
  {
    label: "API 请求配额",
    free: "1,000 次/天",
    pro: "20,000 次/天",
    team: "100,000 次/天",
    enterprise: "自定义",
  },
  {
    label: "关键词追踪",
    free: "50 个",
    pro: "1,000 个",
    team: "5,000 个",
    enterprise: "不限",
  },
  // Core features
  {
    label: "SEO + GEO 分析",
    free: true,
    pro: true,
    team: true,
    enterprise: true,
  },
  {
    label: "多搜索引擎支持",
    free: "3 个引擎",
    pro: "全部引擎",
    team: "全部引擎",
    enterprise: "全部引擎",
  },
  {
    label: "AI 内容生成",
    free: false,
    pro: true,
    team: true,
    enterprise: true,
  },
  {
    label: "电商分析",
    free: false,
    pro: true,
    team: true,
    enterprise: true,
  },
  {
    label: "竞品分析",
    free: false,
    pro: true,
    team: true,
    enterprise: true,
  },
  // Advanced features
  {
    label: "审批工作流",
    free: false,
    pro: false,
    team: true,
    enterprise: true,
  },
  {
    label: "团队协作席位",
    free: "1 名成员",
    pro: "3 名成员",
    team: "20 名成员",
    enterprise: "不限",
  },
  {
    label: "自定义部署规则",
    free: false,
    pro: false,
    team: true,
    enterprise: true,
  },
  {
    label: "Webhook + API 接入",
    free: false,
    pro: true,
    team: true,
    enterprise: true,
  },
  {
    label: "白标 / 自定义域名",
    free: false,
    pro: false,
    team: false,
    enterprise: true,
  },
  // Support & SLA
  {
    label: "支持渠道",
    free: "社区论坛",
    pro: "邮件支持",
    team: "优先邮件 + 工单",
    enterprise: "专属客户成功经理",
  },
  {
    label: "SLA 保障",
    free: false,
    pro: false,
    team: "99.5% uptime",
    enterprise: "99.9% uptime",
  },
  {
    label: "审计日志",
    free: false,
    pro: false,
    team: "90 天",
    enterprise: "完整保留",
  },
  {
    label: "SSO / SAML",
    free: false,
    pro: false,
    team: false,
    enterprise: true,
  },
];

// ── Cell renderer ─────────────────────────────────────────────────────────────

function FeatureCell({ value }: { value: string | boolean }) {
  if (value === true) {
    return (
      <span style={{ color: "var(--good)", fontWeight: 600, fontSize: "1rem" }}>
        ✓
      </span>
    );
  }
  if (value === false) {
    return (
      <span style={{ color: "var(--muted-soft)", fontSize: "1rem" }}>—</span>
    );
  }
  return (
    <span style={{ color: "var(--text)", fontSize: "0.82rem" }}>{value}</span>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function PricingPage() {
  const { t } = useI18n();
  const [billing, setBilling] = useState<"monthly" | "yearly">("monthly");
  const [activePlan, setActivePlan] = useState<PlanTier | null>(null);

  return (
    <div className="page" style={{ maxWidth: 1100 }}>
      {/* ── Hero ── */}
      <section className="hero">
        <div className="eyebrow">定价与计费</div>
        <h1 style={{ fontSize: "clamp(1.4rem, 2.5vw, 2rem)" }}>
          选择最适合您业务的方案
        </h1>
        <p className="hero-copy">
          从个人站长到大型团队，灵活的订阅方案助您轻松扩展 SEO·GEO·广告自动化能力。
          年付享 <strong style={{ color: "var(--accent)" }}>20% 折扣</strong>。
        </p>

        {/* Billing toggle */}
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            marginTop: 8,
            padding: "4px 6px",
            borderRadius: 999,
            border: "1px solid var(--panel-border)",
            background: "rgba(255,255,255,0.04)",
          }}
        >
          {(["monthly", "yearly"] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => setBilling(mode)}
              style={{
                padding: "5px 16px",
                borderRadius: 999,
                border: "none",
                cursor: "pointer",
                fontSize: "0.82rem",
                fontWeight: billing === mode ? 600 : 400,
                background:
                  billing === mode
                    ? "var(--accent)"
                    : "transparent",
                color:
                  billing === mode ? "#0c0f13" : "var(--muted)",
                transition: "all 0.18s",
              }}
            >
              {mode === "monthly" ? "按月付款" : "按年付款"}
              {mode === "yearly" && (
                <span
                  style={{
                    marginLeft: 6,
                    fontSize: "0.72rem",
                    color: billing === "yearly" ? "#0c0f13" : "var(--good)",
                    fontWeight: 700,
                  }}
                >
                  省 20%
                </span>
              )}
            </button>
          ))}
        </div>
      </section>

      {/* ── Plan cards ── */}
      <section
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: 14,
        }}
      >
        {PLANS.map((plan) => {
          const price =
            billing === "monthly" ? plan.monthlyPrice : plan.yearlyPrice;
          const isHighlight = plan.highlight;
          const isActive = activePlan === plan.id;

          return (
            <article
              key={plan.id}
              style={{
                position: "relative",
                padding: "22px 20px 20px",
                borderRadius: 14,
                border: `1px solid ${
                  isHighlight
                    ? "var(--accent)"
                    : isActive
                    ? "var(--panel-border-strong)"
                    : "var(--panel-border)"
                }`,
                background: isHighlight
                  ? "linear-gradient(180deg, rgba(241,201,107,0.08), rgba(241,201,107,0.03)), rgba(16,19,24,0.94)"
                  : "var(--panel)",
                boxShadow: isHighlight ? "0 0 32px rgba(241,201,107,0.12)" : "none",
                cursor: "pointer",
                transition: "border-color 0.18s, box-shadow 0.18s",
              }}
              onClick={() => setActivePlan(plan.id === activePlan ? null : plan.id)}
            >
              {/* Badge */}
              {plan.badge && (
                <div
                  style={{
                    position: "absolute",
                    top: -12,
                    left: "50%",
                    transform: "translateX(-50%)",
                    padding: "3px 12px",
                    borderRadius: 999,
                    background: "var(--accent)",
                    color: "#0c0f13",
                    fontSize: "0.72rem",
                    fontWeight: 700,
                    letterSpacing: "0.06em",
                    whiteSpace: "nowrap",
                  }}
                >
                  {plan.badge}
                </div>
              )}

              {/* Plan name */}
              <div
                style={{
                  fontSize: "1rem",
                  fontWeight: 700,
                  fontFamily: "var(--display-font)",
                  color: isHighlight ? "var(--accent)" : "var(--text)",
                  marginBottom: 4,
                }}
              >
                {plan.name}
              </div>

              {/* Price */}
              <div style={{ marginBottom: 18 }}>
                {price === null ? (
                  <div
                    style={{
                      fontSize: "1.5rem",
                      fontWeight: 700,
                      color: "var(--text)",
                    }}
                  >
                    定制报价
                  </div>
                ) : (
                  <div style={{ display: "flex", alignItems: "baseline", gap: 4 }}>
                    <span
                      style={{
                        fontSize: "2rem",
                        fontWeight: 800,
                        color: "var(--text)",
                        lineHeight: 1,
                      }}
                    >
                      ${price}
                    </span>
                    <span style={{ color: "var(--muted)", fontSize: "0.8rem" }}>
                      / 月
                    </span>
                  </div>
                )}
                {billing === "yearly" && price !== null && price > 0 && (
                  <div style={{ color: "var(--muted)", fontSize: "0.75rem", marginTop: 2 }}>
                    按年付款 ${price * 12} / 年
                  </div>
                )}
              </div>

              {/* CTA */}
              <a
                href={plan.ctaHref}
                onClick={(e) => e.stopPropagation()}
                style={{
                  display: "block",
                  textAlign: "center",
                  padding: "9px 0",
                  borderRadius: 8,
                  border: `1px solid ${isHighlight ? "var(--accent)" : "var(--panel-border-strong)"}`,
                  background: isHighlight ? "var(--accent)" : "transparent",
                  color: isHighlight ? "#0c0f13" : "var(--text)",
                  fontSize: "0.84rem",
                  fontWeight: 600,
                  textDecoration: "none",
                  transition: "opacity 0.15s",
                }}
              >
                {plan.cta}
              </a>
            </article>
          );
        })}
      </section>

      {/* ── Feature comparison table ── */}
      <section className="panel" style={{ overflowX: "auto", padding: "0 0 4px" }}>
        <div style={{ padding: "16px 20px 10px" }}>
          <div className="eyebrow">功能对比</div>
          <h2 style={{ margin: "4px 0 0", fontFamily: "var(--display-font)", fontSize: "1rem" }}>
            全功能权益矩阵
          </h2>
        </div>

        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            fontSize: "0.82rem",
            minWidth: 600,
          }}
        >
          <thead>
            <tr style={{ borderBottom: "1px solid var(--panel-border)" }}>
              <th
                style={{
                  padding: "10px 20px",
                  textAlign: "left",
                  color: "var(--muted)",
                  fontWeight: 500,
                  width: "34%",
                }}
              >
                功能项
              </th>
              {PLANS.map((plan) => (
                <th
                  key={plan.id}
                  style={{
                    padding: "10px 12px",
                    textAlign: "center",
                    color: plan.highlight ? "var(--accent)" : "var(--text)",
                    fontWeight: plan.highlight ? 700 : 600,
                    fontFamily: "var(--display-font)",
                    fontSize: "0.88rem",
                    background: plan.highlight
                      ? "rgba(241,201,107,0.06)"
                      : "transparent",
                  }}
                >
                  {plan.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {FEATURES.map((feature, idx) => (
              <tr
                key={feature.label}
                style={{
                  borderBottom: "1px solid var(--panel-border)",
                  background:
                    idx % 2 === 0
                      ? "transparent"
                      : "rgba(255,255,255,0.012)",
                }}
              >
                <td
                  style={{
                    padding: "9px 20px",
                    color: "var(--muted)",
                    fontWeight: 400,
                  }}
                >
                  {feature.label}
                </td>
                {PLANS.map((plan) => (
                  <td
                    key={plan.id}
                    style={{
                      padding: "9px 12px",
                      textAlign: "center",
                      background: plan.highlight
                        ? "rgba(241,201,107,0.04)"
                        : "transparent",
                    }}
                  >
                    <FeatureCell value={feature[plan.id]} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* ── FAQ ── */}
      <section className="panel">
        <div className="section-heading">
          <div>
            <div className="eyebrow">常见问题</div>
            <h2>FAQ</h2>
          </div>
        </div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
            gap: 16,
            marginTop: 4,
          }}
        >
          {[
            {
              q: "超额后会发生什么？",
              a: "超出月度配额后，API 将返回 402 或 429 状态码并提示升级。已生成的内容和数据不受影响。",
            },
            {
              q: "可以随时降级吗？",
              a: "可以。降级在当前计费周期结束后生效，已付费额度不退还但可使用至到期。",
            },
            {
              q: "支持哪些支付方式？",
              a: "通过 Stripe 支持 VISA、MasterCard、American Express、支付宝及微信支付。",
            },
            {
              q: "企业版有哪些额外支持？",
              a: "专属客户成功经理、SLA 保障、私有化部署选项、自定义合同与发票。",
            },
          ].map((item) => (
            <div
              key={item.q}
              style={{
                padding: "14px 16px",
                borderRadius: 10,
                border: "1px solid var(--panel-border)",
                background: "rgba(255,255,255,0.02)",
              }}
            >
              <h3
                style={{
                  margin: "0 0 8px",
                  fontSize: "0.9rem",
                  fontFamily: "var(--display-font)",
                  color: "var(--text)",
                }}
              >
                {item.q}
              </h3>
              <p style={{ margin: 0, color: "var(--muted)", fontSize: "0.82rem", lineHeight: 1.6 }}>
                {item.a}
              </p>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
