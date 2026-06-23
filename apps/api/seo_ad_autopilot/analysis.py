from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, Optional
from urllib.parse import urlparse

from .crawler import crawl_page
from .connectors import DeploymentGateway
from .models import (
    ApprovalRequest,
    ApprovalStatus,
    BusinessClassifierRule,
    ConnectionHealth,
    ConnectorStatus,
    IngestionReport,
    SourceEvidence,
    DeploymentMode,
    DeploymentRecord,
    MetricSnapshot,
    Opportunity,
    OpportunitySet,
    PagePerformanceBudget,
    PageSnapshot,
    Plan,
    PlanStep,
    PreviewArtifact,
    ProjectSummary,
    RegressionCaseResult,
    RegressionReport,
    ProjectConnection,
    RollbackBundle,
    SiteClass,
    SiteIntake,
    SiteProfile,
    SourceMetricSummary,
    TaskSummary,
    UXReview,
    WorkflowBundle,
    WorkflowStage,
    new_id,
    utcnow,
)
from .skill_registry import SkillRegistry


@dataclass
class SiteClassification:
    vertical: SiteClass
    brand_voice: str
    trust_signals: list[str]


class Sniffer:
    def __init__(self, rules: Optional[list[BusinessClassifierRule]] = None) -> None:
        self.rules = rules or self._default_rules()

    @staticmethod
    def _default_rules() -> list[BusinessClassifierRule]:
        return [
            BusinessClassifierRule(
                rule_id="rule_ecommerce",
                name="Commerce intent",
                description="Signals indicate ecommerce intent.",
                vertical=SiteClass.ecommerce,
                triggers=["shop", "store", "cart", "checkout", "product"],
                confidence=0.92,
            ),
            BusinessClassifierRule(
                rule_id="rule_content",
                name="Editorial intent",
                description="Signals indicate content intent.",
                vertical=SiteClass.content,
                triggers=["blog", "news", "mag", "media", "article", "content"],
                confidence=0.9,
            ),
            BusinessClassifierRule(
                rule_id="rule_saas",
                name="Product-led SaaS",
                description="Signals indicate SaaS intent.",
                vertical=SiteClass.saas,
                triggers=["saas", "dashboard", "platform", "tool", "app"],
                confidence=0.88,
            ),
            BusinessClassifierRule(
                rule_id="rule_tool",
                name="Utility tool",
                description="Signals indicate utility intent.",
                vertical=SiteClass.tool,
                triggers=["tool", "calculator", "generator", "template"],
                confidence=0.84,
            ),
            BusinessClassifierRule(
                rule_id="rule_local",
                name="Local service",
                description="Signals indicate local service intent.",
                vertical=SiteClass.local,
                triggers=["local", "service", "agency", "near me"],
                confidence=0.8,
            ),
            BusinessClassifierRule(
                rule_id="rule_ymyl",
                name="Trust sensitive",
                description="Signals indicate YMYL intent.",
                vertical=SiteClass.ymyl,
                triggers=["clinic", "health", "finance", "loan", "law", "medical"],
                confidence=0.97,
            ),
        ]

    def classify(self, intake: SiteIntake) -> SiteClassification:
        url = intake.url.lower()
        text = " ".join(
            [
                url,
                intake.site_name or "",
                " ".join(intake.keywords),
                " ".join(intake.competitors),
                intake.notes or "",
            ]
        ).lower()
        for rule in self.rules:
            if not rule.enabled:
                continue
            if any(trigger in text for trigger in rule.triggers):
                brand_voice = {
                    SiteClass.ecommerce: "conversion-driven",
                    SiteClass.content: "editorial",
                    SiteClass.saas: "product-led",
                    SiteClass.tool: "utility-led",
                    SiteClass.local: "service-led",
                    SiteClass.ymyl: "trust-sensitive",
                    SiteClass.brand: "brand-led",
                }[rule.vertical]
                trust_signals = {
                    SiteClass.ecommerce: ["product_catalog", "checkout_path"],
                    SiteClass.content: ["publish_velocity", "author_pages"],
                    SiteClass.saas: ["pricing_page", "feature_depth"],
                    SiteClass.tool: ["utility_route", "usage_examples"],
                    SiteClass.local: ["location_signals", "contact_visibility"],
                    SiteClass.ymyl: ["expertise", "review_policy"],
                    SiteClass.brand: ["brand_mentions", "navigation_depth"],
                }[rule.vertical]
                return SiteClassification(rule.vertical, brand_voice, trust_signals)
        return SiteClassification(SiteClass.brand, "brand-led", ["brand_mentions", "navigation_depth"])

    def build_pages(self, intake: SiteIntake, classification: SiteClassification) -> list[PageSnapshot]:
        base_url = intake.url.rstrip("/")
        enable_browser_crawl = os.getenv("SEO_AD_BOT_ENABLE_BROWSER_CRAWL", "false").lower() in {"1", "true", "yes"}
        real_homepage = (
            crawl_page(
                intake.url,
                fallback_title=intake.site_name or urlparse(intake.url).netloc.replace("www.", "").title(),
                fallback_description="Live crawl unavailable, using synthetic page model.",
            )
            if enable_browser_crawl
            else None
        )
        if classification.vertical == SiteClass.ecommerce:
            templates = [
                (base_url, "Catalog Momentum", "Shop the collections that matter most.", 780, 18, 4, 28, 1, ["Product", "BreadcrumbList"]),
                (f"{base_url}/collections", "Collection Index", "Browse curated collections with intent-first filters.", 640, 26, 7, 34, 2, ["ItemList"]),
                (f"{base_url}/product/launch-kit", "Launch Kit", "A featured product built to convert on mobile.", 520, 14, 3, 22, 1, ["Product", "Offer"]),
            ]
        elif classification.vertical == SiteClass.content:
            templates = [
                (base_url, "Editorial Signal", "High-intent articles with clear authority cues.", 1320, 24, 6, 18, 2, ["Organization", "WebSite"]),
                (f"{base_url}/insights", "Insights Hub", "Topic clusters and evergreen briefings.", 1580, 31, 8, 24, 3, ["CollectionPage"]),
                (f"{base_url}/insights/seo-autopilot", "SEO AutoPilot", "A deep article with snippet-ready sections.", 1720, 38, 10, 26, 3, ["Article", "FAQPage"]),
            ]
        elif classification.vertical in {SiteClass.saas, SiteClass.tool}:
            templates = [
                (base_url, "Product Clarity", "Outcome-led messaging above the fold.", 980, 22, 5, 24, 2, ["SoftwareApplication"]),
                (f"{base_url}/pricing", "Pricing", "Transparent plans and upgrade triggers.", 730, 18, 4, 20, 2, ["OfferCatalog"]),
                (f"{base_url}/use-cases", "Use Cases", "Intent-specific journeys for distinct segments.", 1140, 27, 7, 22, 2, ["ItemList"]),
            ]
        elif classification.vertical == SiteClass.ymyl:
            templates = [
                (base_url, "Trust Landing", "High-trust landing page with strong policy framing.", 890, 16, 4, 20, 2, ["Organization"]),
                (f"{base_url}/about", "About", "Credentials, policy, and review process.", 700, 14, 3, 18, 1, ["AboutPage"]),
                (f"{base_url}/resources", "Resources", "Reference material without aggressive monetization.", 1040, 22, 6, 20, 2, ["Article"]),
            ]
        else:
            templates = [
                (base_url, "Brand Core", "A compact, trust-rich landing page.", 860, 18, 4, 20, 1, ["Organization"]),
                (f"{base_url}/overview", "Overview", "What the company does and why it matters.", 780, 20, 4, 18, 2, ["WebPage"]),
                (f"{base_url}/stories", "Stories", "Case studies and proof points.", 980, 22, 6, 22, 2, ["Article"]),
            ]
        pages: list[PageSnapshot] = []
        for index, item in enumerate(templates):
            page_url, title, description, words, internal_links, external_links, images, missing_alt, structured_data = item
            cta_count = 1 if index == 0 else 2
            if classification.vertical == SiteClass.content and index == 2:
                cta_count = 1
            if classification.vertical == SiteClass.ymyl:
                cta_count = 1
            if index == 0 and real_homepage is not None:
                pages.append(real_homepage)
            else:
                pages.append(
                    PageSnapshot(
                        url=page_url,
                        title=title,
                        description=description,
                        headings=[title, "Why it matters", "How it works", "What changes"],
                        word_count=words,
                        internal_links=internal_links,
                        external_links=external_links,
                        images=images,
                        missing_alt_count=missing_alt,
                        structured_data=list(structured_data),
                        cta_count=cta_count,
                        performance_budget=PagePerformanceBudget(
                            lcp_ms=2200 + (index * 160),
                            cls=0.04 + (index * 0.01),
                            inp_ms=130 + (index * 20),
                        ),
                    )
                )
        return pages


class Query:
    def discover(
        self,
        classification: SiteClassification,
        pages: list[PageSnapshot],
        intake: SiteIntake,
        market_evidence: Optional[list[SourceEvidence]] = None,
    ) -> OpportunitySet:
        seo: list[Opportunity] = [
            Opportunity(
                id=new_id("seo"),
                category="seo",
                title="Meta and snippet tuning",
                description="Rewrite titles and descriptions to align with search intent and snippet eligibility.",
                impact_score=86 if classification.vertical == SiteClass.content else 74,
                effort_score=3,
                risk_score=18,
                skill_ids=["seo/content-opportunity-finder", "seo/schema-builder"],
                preview_target="hero-meta",
                evidence=[pages[0].title, pages[0].description],
            ),
            Opportunity(
                id=new_id("seo"),
                category="seo",
                title="Structured data expansion",
                description="Add schema to support richer SERP interpretations and product/article context.",
                impact_score=82,
                effort_score=4,
                risk_score=24,
                skill_ids=["seo/schema-builder", "seo/technical-seo-patcher"],
                preview_target="schema-block",
                evidence=[", ".join(pages[0].structured_data)],
            ),
            Opportunity(
                id=new_id("seo"),
                category="seo",
                title="Internal link reinforcement",
                description="Insert topic-aware internal links to improve discovery and authority flow.",
                impact_score=79,
                effort_score=3,
                risk_score=16,
                skill_ids=["seo/internal-link-builder", "seo/adaptive-component-generator"],
                preview_target="link-rail",
                evidence=[str(pages[0].internal_links), str(pages[-1].internal_links)],
            ),
        ]
        for opportunity in self._market_seo_opportunities(market_evidence or []):
            seo.append(opportunity)
        technical: list[Opportunity] = [
            Opportunity(
                id=new_id("tech"),
                category="technical",
                title="Canonical and crawl hygiene patch",
                description="Normalize canonical signals and reduce crawl ambiguity on indexed pages.",
                impact_score=84,
                effort_score=4,
                risk_score=28,
                skill_ids=["seo/technical-seo-patcher"],
                preview_target="head-hygiene",
                evidence=[pages[0].url],
            ),
            Opportunity(
                id=new_id("tech"),
                category="technical",
                title="Performance budget guardrail",
                description="Shape LCP, CLS, and INP budgets so new modules stay within the release envelope.",
                impact_score=76,
                effort_score=5,
                risk_score=20,
                skill_ids=["observe/monitoring-binder"],
                preview_target="budget-panel",
                evidence=[str(pages[0].performance_budget.model_dump())],
            ),
        ]
        ux: list[Opportunity] = [
            Opportunity(
                id=new_id("ux"),
                category="ux",
                title="Above-the-fold clarity pass",
                description="Keep the primary CTA visible while improving content hierarchy and readability.",
                impact_score=81,
                effort_score=3,
                risk_score=14,
                skill_ids=["seo/adaptive-component-generator"],
                preview_target="hero-band",
                evidence=[str(pages[0].cta_count)],
            ),
            Opportunity(
                id=new_id("ux"),
                category="ux",
                title="Preview-safe comparison module",
                description="Add a side-by-side comparison block that preserves the original conversion path.",
                impact_score=74,
                effort_score=4,
                risk_score=10,
                skill_ids=["seo/adaptive-component-generator"],
                preview_target="comparison-grid",
                evidence=["preview-first"],
            ),
        ]
        ad: list[Opportunity]
        if classification.vertical == SiteClass.ymyl or not intake.brand_whitelist:
            ad = [
                Opportunity(
                    id=new_id("ad"),
                    category="ad",
                    title="Do not recommend ads",
                    description="Trust-sensitive pages should remain focused on editorial or support intent before monetization.",
                    impact_score=33,
                    effort_score=1,
                    risk_score=92,
                    skill_ids=["ad/ad-slot-auditor"],
                    preview_target="no-ad-rail",
                    evidence=[classification.vertical.value, "brand whitelist missing" if not intake.brand_whitelist else "policy gate"],
                )
            ]
        else:
            ad = [
                Opportunity(
                    id=new_id("ad"),
                    category="ad",
                    title="Native sponsorship rail",
                    description="Introduce a contextual sponsorship rail that stays away from primary CTAs.",
                    impact_score=83,
                    effort_score=4,
                    risk_score=29,
                    skill_ids=["ad/ad-slot-auditor", "ad/provider-integrator", "ad/ad-wrapper-renderer"],
                    preview_target="sponsor-rail",
                    evidence=[pages[1].url, pages[0].title],
                ),
                Opportunity(
                    id=new_id("ad"),
                    category="ad",
                    title="Telemetry-ready ad wrapper",
                    description="Bind lightweight telemetry so ad performance can be monitored without reflow churn.",
                    impact_score=78,
                    effort_score=3,
                    risk_score=22,
                    skill_ids=["ad/ad-telemetry-binder"],
                    preview_target="telemetry-block",
                    evidence=["monitoring"],
                ),
            ]
        return OpportunitySet(seo=seo, ad=ad, technical=technical, ux=ux)

    def _market_seo_opportunities(self, market_evidence: list[SourceEvidence]) -> list[Opportunity]:
        connected = [item for item in market_evidence if item.status == ConnectorStatus.connected]
        if not connected:
            return []

        by_provider = {item.provider.value: item for item in connected}
        opportunities: list[Opportunity] = []

        trend = by_provider.get("trend")
        if trend is not None:
            signals = self._market_signal_strings(trend)
            opportunities.append(
                Opportunity(
                    id=new_id("seo"),
                    category="seo",
                    title="Trend-led topic cluster sprint",
                    description="Convert live trend evidence into near-term topic clusters and landing pages before demand cools.",
                    impact_score=88,
                    effort_score=4,
                    risk_score=22,
                    skill_ids=["seo/content-opportunity-finder", "seo/adaptive-component-generator"],
                    preview_target="trend-cluster",
                    evidence=signals or [trend.source_ref or "trend-source"],
                )
            )

        news = by_provider.get("news")
        if news is not None:
            signals = self._market_signal_strings(news)
            opportunities.append(
                Opportunity(
                    id=new_id("seo"),
                    category="seo",
                    title="Freshness capture from live news signals",
                    description="Turn recent news evidence into freshness-safe updates, commentary modules, and reactive content briefs.",
                    impact_score=84,
                    effort_score=3,
                    risk_score=20,
                    skill_ids=["seo/content-opportunity-finder", "seo/technical-seo-patcher"],
                    preview_target="news-brief",
                    evidence=signals or [news.source_ref or "news-source"],
                )
            )

        qa = by_provider.get("qa")
        if qa is not None:
            signals = self._market_signal_strings(qa)
            opportunities.append(
                Opportunity(
                    id=new_id("seo"),
                    category="seo",
                    title="Question-led FAQ and snippet expansion",
                    description="Use live question evidence to generate answer blocks, FAQ modules, and snippet-targeted sections.",
                    impact_score=86,
                    effort_score=3,
                    risk_score=18,
                    skill_ids=["seo/content-opportunity-finder", "seo/schema-builder"],
                    preview_target="faq-cluster",
                    evidence=signals or [qa.source_ref or "qa-source"],
                )
            )
        return opportunities

    def _market_signal_strings(self, evidence: SourceEvidence) -> list[str]:
        sample = evidence.details.get("sample")
        if isinstance(sample, dict):
            keys = ("topics", "queries", "questions", "headlines", "items", "keywords")
            for key in keys:
                value = sample.get(key)
                if isinstance(value, list):
                    extracted = [str(item).strip() for item in value if str(item).strip()]
                    if extracted:
                        return extracted[:4]
        source_bits = [evidence.source_ref or "", evidence.summary]
        return [item for item in source_bits if item][:4]


class Strategist:
    def __init__(self) -> None:
        self.deployment_gateway = DeploymentGateway()

    def plan(
        self,
        intake: SiteIntake,
        profile: SiteProfile,
        opportunities: OpportunitySet,
        registry: SkillRegistry,
    ) -> tuple[Plan, UXReview]:
        selected = self._select_opportunities(opportunities)
        steps = self._build_steps(selected, intake, profile, registry)
        risk_score = self._calculate_risk(profile, selected, intake)
        deployment_mode = self._resolve_deployment_mode(intake)
        auto_deploy_allowed = risk_score < 80
        requires_manual_approval = any(step.approval_required for step in steps) or risk_score >= 60
        rationale = [
            f"Vertical detected as {profile.vertical.value}.",
            f"Selected {len(steps)} skill-backed steps across SEO, AD, deploy, and observe.",
            f"Risk score {risk_score} places the task in the {'manual' if requires_manual_approval else 'automated'} lane.",
        ]
        plan = Plan(
            plan_id=new_id("plan"),
            site_id=profile.site_id,
            deployment_mode=deployment_mode,
            risk_score=risk_score,
            release_strategy=self._release_strategy_for_mode(deployment_mode),
            steps=steps,
            rationale=rationale,
            requires_manual_approval=requires_manual_approval,
            auto_deploy_allowed=auto_deploy_allowed,
        )
        ux_review = self._review_ux(profile, selected, risk_score)
        return plan, ux_review

    def _select_opportunities(self, opportunities: OpportunitySet) -> list[Opportunity]:
        buckets = opportunities.seo + opportunities.technical + opportunities.ux + opportunities.ad
        return sorted(buckets, key=lambda item: (-item.impact_score, item.effort_score))[:6]

    def _build_steps(
        self,
        opportunities: list[Opportunity],
        intake: SiteIntake,
        profile: SiteProfile,
        registry: SkillRegistry,
    ) -> list[PlanStep]:
        steps: list[PlanStep] = []
        base_sequence = [
            ("read/site-sniffer", "Read profile", False),
            ("read/page-snapshotter", "Read page snapshots", False),
        ]
        for skill_id, action, destructive in base_sequence:
            skill = registry.get(skill_id)
            if skill:
                steps.append(
                    PlanStep(
                        id=new_id("step"),
                        skill_id=skill.skill_id,
                        action=action,
                        target=profile.url,
                        expected_output=f"Structured evidence from {skill.name}.",
                        approval_required=skill.required_approval,
                        destructive=destructive,
                        rollback_supported=skill.rollback_supported,
                    )
                )
        for opportunity in opportunities:
            for skill_id in opportunity.skill_ids:
                skill = registry.get(skill_id)
                if not skill:
                    continue
                steps.append(
                    PlanStep(
                        id=new_id("step"),
                        skill_id=skill.skill_id,
                        action=opportunity.title,
                        target=opportunity.preview_target,
                        expected_output=f"{skill.name} will support {opportunity.category} change.",
                        approval_required=skill.required_approval,
                        destructive=skill.is_destructive,
                        rollback_supported=skill.rollback_supported,
                    )
                )
        release_skill = self._release_skill_for_mode(self._resolve_deployment_mode(intake))
        release_meta = registry.get(release_skill)
        if release_meta:
            steps.append(
                PlanStep(
                    id=new_id("step"),
                    skill_id=release_meta.skill_id,
                    action="Package release artifact",
                    target=self._resolve_deployment_mode(intake).value,
                    expected_output=f"Release artifact for {release_meta.name}.",
                    approval_required=release_meta.required_approval,
                    destructive=release_meta.is_destructive,
                    rollback_supported=release_meta.rollback_supported,
                )
            )
        for observe_skill in ("observe/monitoring-binder", "observe/alert-router"):
            skill = registry.get(observe_skill)
            if skill:
                steps.append(
                    PlanStep(
                        id=new_id("step"),
                        skill_id=skill.skill_id,
                        action=f"Bind {skill.name.lower()}",
                        target=profile.site_id,
                        expected_output=f"{skill.name} configured for post-deploy monitoring.",
                        approval_required=skill.required_approval,
                        destructive=skill.is_destructive,
                        rollback_supported=skill.rollback_supported,
                    )
                )
        return steps

    def _calculate_risk(self, profile: SiteProfile, opportunities: list[Opportunity], intake: SiteIntake) -> int:
        base = {
            SiteClass.ecommerce: 44,
            SiteClass.content: 51,
            SiteClass.saas: 47,
            SiteClass.tool: 43,
            SiteClass.local: 58,
            SiteClass.brand: 38,
            SiteClass.ymyl: 82,
        }[profile.vertical]
        base += 8 if not intake.repo_url and not intake.cms_name else 0
        base += 12 if any(item.category == "ad" and "Do not recommend" in item.title for item in opportunities) else 0
        base += min(14, sum(item.risk_score for item in opportunities[:4]) // 12)
        return max(0, min(100, base))

    def _review_ux(self, profile: SiteProfile, opportunities: list[Opportunity], risk_score: int) -> UXReview:
        issues: list[str] = []
        recommendations: list[str] = []
        if any(item.category == "ad" and "Do not recommend" in item.title for item in opportunities):
            issues.append("Monetization should be deferred until trust signals improve.")
            recommendations.append("Keep the page free of ads and focus on editorial or support intent.")
        if profile.pages and profile.pages[0].cta_count < 2:
            issues.append("Primary CTA density is low on the lead page.")
            recommendations.append("Add one supporting action but keep the current primary path intact.")
        if risk_score >= 70:
            issues.append("Manual approval is required before any write path can be released.")
            recommendations.append("Use preview-only and PR artifacts as the first release boundary.")
        score = max(35, 100 - len(issues) * 14 - max(0, risk_score - 55) // 2)
        notes = [f"Reviewed {len(profile.pages)} pages and {len(opportunities)} selected opportunities."]
        return UXReview(score=score, issues=issues, notes=notes, recommendations=recommendations)

    def _resolve_deployment_mode(self, intake: SiteIntake) -> DeploymentMode:
        if intake.repo_url:
            return DeploymentMode.github_pr
        if intake.cms_name:
            return DeploymentMode.cms_draft
        if "script" in intake.notes.lower():
            return DeploymentMode.universal_script
        return DeploymentMode.static_export

    def _release_strategy_for_mode(self, mode: DeploymentMode) -> str:
        return {
            DeploymentMode.github_pr: "Create a PR with preview evidence and approve before merge.",
            DeploymentMode.cms_draft: "Persist to CMS draft, then approve before publishing.",
            DeploymentMode.universal_script: "Prepare a guarded script with rollback hooks.",
            DeploymentMode.static_export: "Export a static bundle with a rollback snapshot.",
        }[mode]

    def _release_skill_for_mode(self, mode: DeploymentMode) -> str:
        return {
            DeploymentMode.github_pr: "deploy/github-pr-creator",
            DeploymentMode.cms_draft: "deploy/cms-plugin-applier",
            DeploymentMode.universal_script: "deploy/universal-script-injector",
            DeploymentMode.static_export: "deploy/github-pr-creator",
        }[mode]

    def build_profile(
        self,
        intake: SiteIntake,
        classification: SiteClassification,
        site_id: Optional[str] = None,
        ingestion_report: Optional[IngestionReport] = None,
    ) -> SiteProfile:
        pages = Sniffer().build_pages(intake, classification)
        page_count = max(6, len(pages) * 4 + len(intake.sitemap_urls))
        evidence = [
            f"host={urlparse(intake.url).netloc}",
            f"keywords={len(intake.keywords)}",
            f"competitors={len(intake.competitors)}",
        ]
        if ingestion_report:
            evidence.extend(
                [
                    f"{item.provider.value}:{item.status.value}"
                    for item in ingestion_report.evidence
                ]
            )
            page_count += min(8, sum(1 for item in ingestion_report.evidence if item.provider.value == "sitemap"))
        base_risk = {
            SiteClass.ecommerce: 44,
            SiteClass.content: 52,
            SiteClass.saas: 49,
            SiteClass.tool: 45,
            SiteClass.local: 58,
            SiteClass.brand: 40,
            SiteClass.ymyl: 82,
        }[classification.vertical]
        if not intake.brand_whitelist:
            base_risk += 4
        if not intake.repo_url and not intake.cms_name:
            base_risk += 4
        return SiteProfile(
            site_id=site_id or new_id("site"),
            name=intake.site_name or urlparse(intake.url).netloc.replace("www.", "").title(),
            url=intake.url,
            vertical=classification.vertical,
            language=intake.language,
            locale=intake.locale,
            brand_voice=classification.brand_voice,
            page_count_estimate=page_count,
            trust_signals=classification.trust_signals,
            pages=pages,
            evidence=evidence,
            risk_score=min(100, base_risk),
        )

    def build_preview(self, profile: SiteProfile, plan: Plan, opportunities: OpportunitySet) -> PreviewArtifact:
        featured = profile.pages[0]
        before_html = f"""
<main class="page-shell">
  <section class="hero">
    <h1>{featured.title}</h1>
    <p>{featured.description}</p>
    <a class="cta" href="#primary">Read more</a>
  </section>
</main>
""".strip()
        after_sections = [
            "  <section class=\"hero hero--expanded\">",
            f"    <div class=\"eyebrow\">{profile.vertical.value.upper()}</div>",
            f"    <h1>{featured.title} with sharper intent framing</h1>",
            f"    <p>{featured.description} with proof-led structure and clearer navigation.</p>",
            "    <a class=\"cta cta--primary\" href=\"#primary\">Continue</a>",
            "  </section>",
        ]
        if opportunities.ad:
            after_sections.append("  <aside class=\"native-ad-rail\">Contextual sponsorship rail</aside>")
        after_sections.extend(
            [
                "  <section class=\"trust-band\">",
                "    <div class=\"trust-card\">Internal link graph reinforced</div>",
                "    <div class=\"trust-card\">Structured data hardened</div>",
                "  </section>",
                "</main>",
            ]
        )
        after_html = "\n".join(["<main class=\"page-shell preview\">"] + after_sections)
        dom_insertions = [
            "hero: preserve the primary CTA and add an eyebrow label",
            "body: insert trust-band modules with internal link reinforcement",
        ]
        if opportunities.ad and "Do not recommend" not in opportunities.ad[0].title:
            dom_insertions.append("sidebar: add a contextual sponsorship rail away from the CTA")
        css_diff = "\n".join(
            [
                ".hero--expanded { display:grid; gap: 16px; padding: 32px; }",
                ".trust-band { display:grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }",
                ".native-ad-rail { border-left: 2px solid rgba(189, 126, 0, 0.45); padding-left: 14px; }",
                ".cta--primary { background: linear-gradient(135deg, #f1c96b, #bb7e00); color: #161411; }",
            ]
        )
        budget = {
            "baselineLcpMs": featured.performance_budget.lcp_ms,
            "estimatedLcpMs": featured.performance_budget.lcp_ms + 180,
            "budgetDeltaMs": 180,
        }
        diff_summary = f"Preview adds {len(dom_insertions)} DOM changes and keeps the primary CTA intact."
        return PreviewArtifact(
            preview_id=new_id("preview"),
            before_html=before_html,
            after_html=after_html,
            dom_insertions=dom_insertions,
            css_diff=css_diff,
            performance_budget=budget,
            diff_summary=diff_summary,
        )

    def build_deployment(
        self,
        task_id: str,
        plan: Plan,
        preview: PreviewArtifact,
        intake: SiteIntake,
        profile: SiteProfile,
        connections: list[ProjectConnection],
    ) -> DeploymentRecord:
        return self.deployment_gateway.build_deployment(
            task_id,
            plan,
            preview.preview_id,
            intake,
            profile.site_id,
            connections,
        )

    def build_metrics(
        self,
        project_id: str,
        task_id: str,
        profile: SiteProfile,
        plan: Plan,
        ingestion_report: Optional[IngestionReport] = None,
    ) -> MetricSnapshot:
        seo_score = min(100, 62 + len(profile.pages) * 3 + (4 if profile.vertical == SiteClass.content else 0))
        ad_fit = 35 if profile.vertical == SiteClass.ymyl else 82 if profile.vertical in {SiteClass.content, SiteClass.saas, SiteClass.tool} else 74
        traffic_delta = 8 if plan.risk_score < 70 else 2
        conversion_delta = 4 if plan.risk_score < 70 else 1
        source_status: dict[str, ConnectorStatus] = {}
        source_metrics_summary: list[SourceMetricSummary] = []
        external_metrics: dict[str, Any] = {}
        evidence: list[str] = []
        if ingestion_report and ingestion_report.evidence:
            for item in ingestion_report.evidence:
                source_status[item.provider.value] = item.status
                if item.provider.value == "search_console":
                    external_metrics["searchConsole"] = item.details
                    clicks = int(item.details.get("clicks", 0) or 0)
                    impressions = int(item.details.get("impressions", 0) or 0)
                    query_themes = item.details.get("queryThemes", [])
                    property_ref = item.details.get("property")
                    tertiary_metric = None
                    if query_themes:
                        tertiary_metric = f"Themes {', '.join(str(theme) for theme in query_themes[:3])}"
                    elif property_ref:
                        tertiary_metric = f"Property {property_ref}"
                    source_metrics_summary.append(
                        SourceMetricSummary(
                            source="search_console",
                            status=item.status,
                            primary_metric=f"Clicks {clicks}",
                            secondary_metric=f"Impressions {impressions}",
                            tertiary_metric=tertiary_metric,
                            auth_source=item.auth_source,
                            fallback_reason=item.fallback_reason,
                        )
                    )
                    if item.status == ConnectorStatus.connected:
                        seo_score = min(100, seo_score + min(12, clicks // 50 + impressions // 500))
                        evidence.append(f"search_console connected clicks={clicks} impressions={impressions}")
                elif item.provider.value == "ga4":
                    external_metrics["ga4"] = item.details
                    sessions = int(item.details.get("sessions", 0) or 0)
                    conversions = int(item.details.get("conversions", 0) or 0)
                    engagement_rate = float(item.details.get("engagementRate", 0) or 0)
                    source_metrics_summary.append(
                        SourceMetricSummary(
                            source="ga4",
                            status=item.status,
                            primary_metric=f"Sessions {sessions}",
                            secondary_metric=f"Conversions {conversions}",
                            tertiary_metric=f"Engagement {engagement_rate:.2f}",
                            auth_source=item.auth_source,
                            fallback_reason=item.fallback_reason,
                        )
                    )
                    if item.status == ConnectorStatus.connected:
                        traffic_delta = max(2, min(20, sessions // 300 or 2))
                        conversion_delta = max(1, min(12, conversions // 5 or 1))
                        ad_fit = min(100, ad_fit + (2 if engagement_rate >= 0.65 else 0))
                        evidence.append(
                            f"ga4 connected sessions={sessions} conversions={conversions} engagementRate={engagement_rate}"
                        )
                elif item.provider.value == "ad_network":
                    external_metrics["adNetwork"] = {
                        "status": item.status.value,
                        "provenance": list(item.provenance),
                        "fetchedAt": item.fetched_at.isoformat(),
                        "authSource": item.auth_source,
                        "fallbackReason": item.fallback_reason,
                        "failureCode": item.failure_code,
                        "retryable": bool(item.retryable),
                        "latencyMs": item.latency_ms,
                        "estimatedRevenueDaily": float(item.details.get("estimatedRevenueDaily", 0) or 0),
                        "rpm": float(item.details.get("rpm", 0) or 0),
                        "fillRate": float(item.details.get("fillRate", 0) or 0),
                        "impressions": int(float(item.details.get("impressions", 0) or 0)),
                        "providerRef": item.details.get("providerRef"),
                        "inventoryStatus": item.details.get("inventoryStatus"),
                        "raw": item.details,
                    }
                    revenue_daily = float(item.details.get("estimatedRevenueDaily", 0) or 0)
                    fill_rate = float(item.details.get("fillRate", 0) or 0)
                    rpm = float(item.details.get("rpm", 0) or 0)
                    impressions = int(float(item.details.get("impressions", 0) or 0))
                    source_metrics_summary.append(
                        SourceMetricSummary(
                            source="ad_network",
                            status=item.status,
                            primary_metric=f"Revenue/day {revenue_daily:.1f}",
                            secondary_metric=f"Fill rate {fill_rate:.2f}",
                            tertiary_metric=f"RPM {rpm:.2f} · Impressions {impressions}",
                            auth_source=item.auth_source,
                            fallback_reason=item.fallback_reason,
                        )
                    )
                    if item.status == ConnectorStatus.connected:
                        ad_fit = min(100, ad_fit + min(8, int(revenue_daily // 12) + (1 if fill_rate >= 0.6 else 0)))
                        conversion_delta = max(conversion_delta, min(10, int(revenue_daily // 15) + 1))
                        evidence.append(
                            f"ad_network connected revenueDaily={revenue_daily} rpm={rpm} fillRate={fill_rate} impressions={impressions}"
                        )
        if not source_status:
            source_status = {
                "search_console": ConnectorStatus.synthetic,
                "ga4": ConnectorStatus.synthetic,
                "ad_network": ConnectorStatus.synthetic,
            }
            external_metrics = {
                "searchConsole": {"clicks": 120, "impressions": 980, "queryThemes": [profile.name.lower()]},
                "ga4": {"sessions": 3400, "conversions": 42, "engagementRate": 0.71},
                "adNetwork": {
                    "status": ConnectorStatus.synthetic.value,
                    "provenance": ["synthetic"],
                    "estimatedRevenueDaily": 26.0,
                    "rpm": 3.8,
                    "fillRate": 0.52,
                    "impressions": 7200,
                },
            }
            source_metrics_summary = [
                SourceMetricSummary(
                    source="search_console",
                    status=ConnectorStatus.synthetic,
                    primary_metric="Clicks 120",
                    secondary_metric="Impressions 980",
                    tertiary_metric=f"Themes {profile.name.lower()}",
                    auth_source="fallback",
                    fallback_reason="Synthetic metric baseline",
                ),
                SourceMetricSummary(
                    source="ga4",
                    status=ConnectorStatus.synthetic,
                    primary_metric="Sessions 3400",
                    secondary_metric="Conversions 42",
                    tertiary_metric="Engagement 0.71",
                    auth_source="fallback",
                    fallback_reason="Synthetic metric baseline",
                ),
                SourceMetricSummary(
                    source="ad_network",
                    status=ConnectorStatus.synthetic,
                    primary_metric="Revenue/day 26.0",
                    secondary_metric="Fill rate 0.52",
                    tertiary_metric="RPM 3.80 · Impressions 7200",
                    auth_source="fallback",
                    fallback_reason="Synthetic metric baseline",
                ),
            ]
            evidence.append("synthetic metric baseline")
            traffic_delta = 5 if plan.risk_score < 70 else 2
            conversion_delta = 2 if plan.risk_score < 70 else 1
        else:
            traffic_delta = max(traffic_delta, 8 if plan.risk_score < 70 else 2)
            conversion_delta = max(conversion_delta, 4 if plan.risk_score < 70 else 1)
        return MetricSnapshot(
            snapshot_id=new_id("metric"),
            project_id=project_id,
            task_id=task_id,
            seo_score=seo_score,
            ad_fit_score=ad_fit,
            core_web_vitals={
                "lcpMs": profile.pages[0].performance_budget.lcp_ms + 120,
                "cls": int(profile.pages[0].performance_budget.cls * 100),
                "inpMs": profile.pages[0].performance_budget.inp_ms + 10,
            },
            traffic_delta=traffic_delta,
            conversion_delta=conversion_delta,
            source_status=source_status,
            source_metrics_summary=source_metrics_summary,
            external_metrics=external_metrics,
            evidence=evidence,
        )

    def build_rollback(self, deployment: DeploymentRecord, plan: Plan) -> RollbackBundle:
        commands = {
            DeploymentMode.github_pr: ["git revert HEAD", "open revert PR", "restore generated preview snapshot"],
            DeploymentMode.cms_draft: ["restore previous CMS draft", "rebuild draft cache", "republish previous version"],
            DeploymentMode.universal_script: ["disable injected script", "restore previous injection manifest", "purge script cache"],
            DeploymentMode.static_export: ["swap static bundle", "invalidate edge cache", "revert release artifact"],
        }[deployment.mode]
        return RollbackBundle(
            rollback_id=new_id("rollback"),
            deployment_id=deployment.deployment_id,
            commands=commands,
            safe_window_minutes=5,
            reason="monitoring threshold crossed or manual rollback requested",
            expected_effect="Restore the previous stable release and remove the latest growth artifact.",
        )


class Coordinator:
    def __init__(self, registry: SkillRegistry):
        self.registry = registry
        self.sniffer = Sniffer()
        self.query = Query()
        self.strategist = Strategist()

    def run(
        self,
        task_id: str,
        intake: SiteIntake,
        site_id: Optional[str] = None,
        ingestion_report: Optional[IngestionReport] = None,
        connections: Optional[list[ProjectConnection]] = None,
    ) -> WorkflowBundle:
        classification = self.sniffer.classify(intake)
        profile = self.strategist.build_profile(intake, classification, site_id=site_id, ingestion_report=ingestion_report)
        market_evidence = list(ingestion_report.evidence) if ingestion_report is not None else []
        opportunities = self.query.discover(classification, profile.pages, intake, market_evidence=market_evidence)
        plan, ux_review = self.strategist.plan(intake, profile, opportunities, self.registry)
        preview = self.strategist.build_preview(profile, plan, opportunities)
        approval = ApprovalRequest(
            approval_id=new_id("approval"),
            task_id=task_id,
            status=ApprovalStatus.pending,
            required_approvers=["growth-owner", "brand-guardian"],
            policy_snapshot={
                "approval_required_threshold": 60,
                "block_auto_deploy_threshold": 80,
                "auto_deploy_enabled": True,
            },
            risk_summary=f"{plan.risk_score} risk score with {len(plan.steps)} planned steps.",
            decision_hint="Preview is ready. Approve manually if the write path must proceed.",
        )
        deployment = self.strategist.build_deployment(task_id, plan, preview, intake, profile, connections or [])
        metric_snapshot = None
        rollback_bundle = None
        recommendation = "Auto deploy eligible" if not plan.requires_manual_approval else "Manual approval required"
        project = ProjectSummary(
            project_id=profile.site_id,
            name=profile.name,
            url=profile.url,
            site_class=profile.vertical,
            latest_stage=WorkflowStage.awaiting_approval,
            risk_score=plan.risk_score,
            deployment_mode=plan.deployment_mode,
            recommendation=recommendation,
            updated_at=utcnow(),
        )
        task = TaskSummary(
            task_id=task_id,
            project_id=profile.site_id,
            status=WorkflowStage.awaiting_approval,
            risk_score=plan.risk_score,
            approval_status=ApprovalStatus.pending,
            site_class=profile.vertical,
            updated_at=utcnow(),
        )
        return WorkflowBundle(
            project=project,
            task=task,
            site_profile=profile,
            ingestion_report=ingestion_report,
            opportunity_set=opportunities,
            plan=plan,
            ux_review=ux_review,
            approval_request=approval,
            preview=preview,
            deployment=deployment,
            metric_snapshot=metric_snapshot,
            rollback_bundle=rollback_bundle,
        )

    def build_regression_report(self, samples: list["RegressionSample"], connector_status: dict[str, ConnectionHealth] | None = None) -> RegressionReport:
        sample_set = samples
        cases: list[RegressionCaseResult] = []
        seo_preview_count = 0
        ad_recommendation_count = 0
        no_ad_count = 0
        pass_count = 0
        fail_count = 0
        connector_status = connector_status or {}
        for sample in sample_set:
            intake = sample.intake
            classification = self.sniffer.classify(intake)
            profile = self.strategist.build_profile(intake, classification, site_id=sample.sample_id)
            opportunities = self.query.discover(classification, profile.pages, intake, market_evidence=[])
            plan, _ = self.strategist.plan(intake, profile, opportunities, self.registry)
            ad_opportunity = opportunities.ad[0] if opportunities.ad else None
            ad_allowed = bool(ad_opportunity and "Do not recommend" not in ad_opportunity.title)
            seo_preview_ready = bool(profile.pages and opportunities.seo and plan.steps)
            risk_band = "high" if plan.risk_score >= 70 else "medium" if plan.risk_score >= 40 else "low"
            if seo_preview_ready:
                seo_preview_count += 1
            if ad_opportunity:
                ad_recommendation_count += 1
            if not ad_allowed:
                no_ad_count += 1
            health = connector_status.get(sample.sample_id, ConnectionHealth.unknown)
            passed = (
                seo_preview_ready == sample.expected_seo_preview
                and ad_allowed == sample.expected_ad_allowed
                and risk_band == sample.expected_risk_band
                and health != ConnectionHealth.unavailable
            )
            if passed:
                pass_count += 1
            else:
                fail_count += 1
            cases.append(
                RegressionCaseResult(
                    sample_id=sample.sample_id,
                    name=sample.name,
                    site_class=classification.vertical,
                    risk_score=plan.risk_score,
                    deployment_mode=plan.deployment_mode,
                    connection_health=health,
                    seo_preview_ready=seo_preview_ready,
                    ad_recommendation=ad_opportunity.title if ad_opportunity else "No ad recommendation generated",
                    ad_allowed=ad_allowed,
                    passed=passed,
                    notes=[
                        f"pages={len(profile.pages)}",
                        f"seo={len(opportunities.seo)}",
                        f"ad={len(opportunities.ad)}",
                        f"expected_seo={sample.expected_seo_preview}",
                        f"expected_ad={sample.expected_ad_allowed}",
                        f"risk_band={risk_band}/{sample.expected_risk_band}",
                    ],
                )
            )
        return RegressionReport(
            report_id=new_id("regress"),
            sample_count=len(cases),
            seo_preview_count=seo_preview_count,
            ad_recommendation_count=ad_recommendation_count,
            no_ad_count=no_ad_count,
            pass_count=pass_count,
            fail_count=fail_count,
            cases=cases,
            notes=[
                "Regression checks use the seeded demo sites and deterministic preview pipeline.",
                "The report verifies preview generation, ad-eligibility gating, and classification stability.",
            ],
        )
