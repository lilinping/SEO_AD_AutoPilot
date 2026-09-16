"""AIO Optimizer Agent  —  AI Overview / Generative Engine Optimization.

补全功能说明 (P0 缺口):
- AI 引用率评分  (ChatGPT / Perplexity / Google AI Overviews)
- LLM.txt / ai.txt 生成指引
- E-E-A-T 信号强化评分
- 实体映射到 Knowledge Graph
- 问答格式内容结构化建议
"""

from __future__ import annotations

import re
from typing import Any

from .base import Agent, AgentOutput, AgentRole, DebateOpinion, DebateStance, SiteContext

# ── 兼容性处理：AgentRole.AIO_OPTIMIZER 在 base.py patch 前用字符串 fallback ──
try:
    _AIO_ROLE = AgentRole.AIO_OPTIMIZER          # type: ignore[attr-defined]
except AttributeError:
    _AIO_ROLE = "aio_optimizer"                  # type: ignore[assignment]


class AIOOptimizerAgent(Agent):
    """AIO Optimizer Agent — 确保内容在 AI 搜索引擎中可被引用和可见.

    2026 背景:
    - Google AI Overviews 出现在 >50% 的搜索结果中 (BrightEdge 2026)
    - ChatGPT / Perplexity / Claude 已成主流研究入口
    - LLM.txt 和 ai.txt 是新兴的 AI 爬虫标准
    - E-E-A-T 信号直接影响 AI 引用资格
    """

    # 评分阈值 (对齐 BrightEdge 2026 基准)
    CITATION_OK     = 50.0
    EEAT_OK         = 55.0
    ANSWER_OK       = 50.0
    ENTITY_OK       = 45.0
    OVERALL_GOOD    = 65.0

    def __init__(self) -> None:
        super().__init__()
        self._role = _AIO_ROLE  # type: ignore[assignment]

    # ── Debate ──────────────────────────────────────────────────────────

    def offer_opinion(
        self,
        topic: str,
        proposal: dict[str, Any],
        context: SiteContext,
        previous_opinions: list = None,
    ) -> DebateOpinion:
        """对内容/SEO 提案给出 AIO 视角意见."""
        kw = ["aio", "ai overview", "citation", "llm", "entity", "eeat",
              "generative", "perplexity", "chatgpt", "answer"]
        if not any(k in str(proposal).lower() for k in kw):
            return DebateOpinion(
                agent_role=self._role,
                stance=DebateStance.ABSTAIN,
                reasoning="Proposal not directly related to AIO/GEO optimization",
            )
        overall = proposal.get("aio_scores", {}).get("overall", 0)
        if overall >= self.OVERALL_GOOD:
            return DebateOpinion(
                agent_role=self._role,
                stance=DebateStance.AGREE,
                reasoning=f"AIO readiness {overall}/100 meets AI search threshold",
                evidence=["AIO overall score satisfies 65-point minimum"],
                confidence=0.83,
            )
        return DebateOpinion(
            agent_role=self._role,
            stance=DebateStance.DISAGREE,
            reasoning=f"AIO score {overall}/100 too low — risk of AI Overview exclusion",
            evidence=["Score below 65-point threshold"],
            confidence=0.80,
        )

    # ── Core Analysis ────────────────────────────────────────────────────

    def analyze(self, context: SiteContext) -> AgentOutput:
        """全量 AIO 就绪度分析."""
        rd  = context.raw_data
        url = context.url

        citation = self._score_citation(rd)
        eeat     = self._score_eeat(rd)
        answer   = self._score_answer_format(rd)
        entity   = self._score_entity(rd)
        crawl    = self._check_llm_crawlability(rd)

        overall = round(
            citation * 0.25 + eeat * 0.25 + answer * 0.30 + entity * 0.20, 1
        )

        priority = (
            "critical" if overall < 35 else
            "high"     if overall < 50 else
            "medium"   if overall < self.OVERALL_GOOD else
            "low"
        )

        label = (
            "AI-Optimized"       if overall >= 75 else
            "Partially Optimized" if overall >= 50 else
            "Needs Optimization"
        )

        content = {
            "url": url,
            "aio_scores": {
                "citation_eligibility": round(citation, 1),
                "eeat_signals":         round(eeat, 1),
                "answer_format":        round(answer, 1),
                "entity_clarity":       round(entity, 1),
                "llm_crawlability":     round(crawl["score"], 1),
                "overall":              overall,
            },
            "llm_crawlability":  crawl,
            "recommendations":   self._recommendations(citation, eeat, answer, entity, crawl),
            "optimization_plan": self._build_plan(citation, eeat, answer, entity, crawl, rd, url),
            "priority":          priority,
            "readiness_label":   label,
        }

        return self._create_output(
            content=content,
            confidence=0.87,
            risk_score=0.05,
            reasoning=f"AIO analysis complete — overall {overall}/100 ({priority})",
        )

    # ── Scoring Methods ──────────────────────────────────────────────────

    def _score_citation(self, rd: dict[str, Any]) -> float:
        """评分：内容被 AI 引擎引用的可能性."""
        score   = 20.0
        content = rd.get("content", "")
        schemas = rd.get("schema_data", [])

        # 数据/统计信号
        if re.search(r"\d+(\.\d+)?%", content):              score += 8
        if re.search(r"\$[\d,]+", content):                   score += 5
        if re.search(r"\b(19|20)\d{2}\b", content):           score += 4
        if re.search(
            r"according to|research shows|study finds|data indicates|survey reveals",
            content, re.I
        ):                                                     score += 10
        if re.search(r"source\s*:|reference\s*:|citation\s*:", content, re.I):
            score += 8

        # Schema 类型
        for s in schemas:
            t = s.get("@type", "")
            if t in {"Article", "NewsArticle", "BlogPosting", "TechArticle"}:
                score += 10
            if t in {"FAQPage", "QAPage", "HowTo"}:
                score += 12
            if t == "Dataset":
                score += 8

        # 权威外链
        auth = [".gov", ".edu", "pubmed.ncbi", "arxiv.org", "nih.gov", "who.int"]
        auth_count = sum(1 for l in rd.get("links", []) if any(d in l for d in auth))
        score += min(15, auth_count * 5)

        return min(100.0, score)

    def _score_eeat(self, rd: dict[str, Any]) -> float:
        """评分：E-E-A-T 信号 (体验/专业/权威/可信)."""
        score   = 15.0
        schemas = rd.get("schema_data", [])
        content = rd.get("content", "")

        # 作者信号
        if rd.get("author"):     score += 15
        person = next((s for s in schemas if s.get("@type") == "Person"), None)
        if person:
            if person.get("sameAs"):     score += 12
            if person.get("jobTitle"):   score += 8
            if person.get("alumniOf") or person.get("worksFor"): score += 6

        # 机构权威信号
        org = next((s for s in schemas if s.get("@type") == "Organization"), None)
        if org:
            score += 10
            if org.get("logo"):    score += 5
            if org.get("sameAs"):  score += 8

        # 第一手体验语言
        if re.search(
            r"i tested|in my experience|i found|we reviewed|hands.on|i've used",
            content, re.I
        ):
            score += 8

        # 新鲜度
        if rd.get("publish_date"):  score += 5
        if rd.get("modified_date"): score += 8

        # 信任信号
        if rd.get("about_page_link"):   score += 4
        if rd.get("privacy_policy_link"): score += 3

        return min(100.0, score)

    def _score_answer_format(self, rd: dict[str, Any]) -> float:
        """评分：内容是否适合 AI 引擎直接提取答案."""
        score   = 20.0
        schemas = rd.get("schema_data", [])
        content = rd.get("content", "")
        headings = rd.get("headings", [])

        # FAQ / QA / HowTo Schema
        for s in schemas:
            t = s.get("@type", "")
            if t == "FAQPage": score += 20
            if t == "QAPage":  score += 15
            if t == "HowTo":   score += 12

        # 问句标题
        q_headings = [h for h in headings if h.strip().endswith("?")]
        score += min(15, len(q_headings) * 3)

        # 列表结构
        list_items = len(re.findall(r"^\s*[-•*]\s+|\d+\.\s+", content, re.M))
        score += min(15, list_items * 1.5)

        # 首段直接回答
        words = len(content[:400].split())
        if words >= 30: score += 10
        if words >= 50: score += 5

        # 表格
        if rd.get("tables_count", 0) > 0: score += 8

        return min(100.0, score)

    def _score_entity(self, rd: dict[str, Any]) -> float:
        """评分：实体清晰度 (Knowledge Graph 对齐)."""
        score   = 20.0
        schemas = rd.get("schema_data", [])
        kg_types = {"Organization", "Person", "Product", "Place", "Event", "Brand", "LocalBusiness"}

        for s in schemas:
            if s.get("@type") in kg_types:
                score += 15
                if s.get("sameAs"):    score += 10   # Wikipedia/Wikidata 是最强信号
                if s.get("url"):       score += 5
                if s.get("description"): score += 5

        if rd.get("og_title"):        score += 8
        if rd.get("og_description"):  score += 5
        if rd.get("canonical"):       score += 7
        if rd.get("title") and len(rd["title"]) > 10: score += 10

        return min(100.0, score)

    def _check_llm_crawlability(self, rd: dict[str, Any]) -> dict[str, Any]:
        """检查 AI 爬虫访问权限 + LLM.txt / ai.txt 存在性."""
        robots = rd.get("robots_txt", "")
        score  = 60.0
        issues: list[str] = []
        blocked: list[str] = []

        # 2026 主流 AI 爬虫
        ai_bots = [
            "GPTBot", "ClaudeBot", "anthropic-ai",
            "PerplexityBot", "Google-Extended",
            "Bytespider", "Applebot-Extended", "CCBot",
        ]
        for bot in ai_bots:
            if f"User-agent: {bot}" in robots:
                section = robots.split(f"User-agent: {bot}")[1].split("User-agent:")[0]
                if "Disallow: /" in section:
                    blocked.append(bot)
                    score -= 12

        llm_txt = rd.get("llm_txt_found", False)
        ai_txt  = rd.get("ai_txt_found",  False)

        if llm_txt:
            score += 20
        else:
            issues.append("Missing /llm.txt — create to guide AI crawlers on content scope")

        if ai_txt:
            score += 10
        else:
            issues.append("Missing /ai.txt — add to signal AI training data preferences")

        if blocked:
            issues.append(
                f"Blocking AI crawlers in robots.txt: {', '.join(blocked)}. "
                "Consider selective unblocking to improve AI citation eligibility."
            )

        return {
            "score":           round(max(0.0, min(100.0, score)), 1),
            "llm_txt_exists":  llm_txt,
            "ai_txt_exists":   ai_txt,
            "blocked_bots":    blocked,
            "issues":          issues,
        }

    # ── Recommendations & Plan ────────────────────────────────────────────

    def _recommendations(
        self,
        citation: float, eeat: float, answer: float, entity: float,
        crawl: dict,
    ) -> list[dict[str, Any]]:
        recs: list[dict[str, Any]] = []

        if crawl.get("blocked_bots"):
            recs.append({
                "priority": "critical",
                "type":     "crawlability",
                "action":   f"Remove robots.txt blocks for: {crawl['blocked_bots']}",
                "impact":   "Immediate AI citation eligibility restoration",
            })

        if not crawl.get("llm_txt_exists"):
            recs.append({
                "priority": "high",
                "type":     "llm_txt",
                "action":   "Create /llm.txt to guide AI crawlers",
                "impact":   "+15–20 crawlability score; better AI indexation control",
            })

        if citation < self.CITATION_OK:
            recs.append({
                "priority": "high",
                "type":     "citation_signals",
                "action":   "Add verifiable statistics, data citations, authority external links",
                "impact":   f"+{int(self.CITATION_OK - citation + 10)} citation score points",
            })

        if eeat < self.EEAT_OK:
            recs.append({
                "priority": "high",
                "type":     "eeat",
                "action":   "Add author bio with credentials + Organization schema with sameAs Wikipedia",
                "impact":   f"+{int(self.EEAT_OK - eeat + 10)} E-E-A-T score points",
            })

        if answer < self.ANSWER_OK:
            recs.append({
                "priority": "high",
                "type":     "answer_format",
                "action":   "Add FAQPage schema, question-style H2 headings, concise direct answers",
                "impact":   f"+{int(self.ANSWER_OK - answer + 10)} answer format score points",
            })

        if entity < self.ENTITY_OK:
            recs.append({
                "priority": "medium",
                "type":     "entity_mapping",
                "action":   "Add Organization/Person schema with sameAs Wikidata/Wikipedia links",
                "impact":   f"+{int(self.ENTITY_OK - entity + 8)} entity score points",
            })

        return recs

    def _build_plan(
        self,
        citation: float, eeat: float, answer: float, entity: float,
        crawl: dict, rd: dict[str, Any], url: str,
    ) -> dict[str, Any]:
        actions: list[dict[str, Any]] = []
        n = 1

        if not crawl.get("llm_txt_exists"):
            actions.append({
                "skill":       "LLMTxtGeneratorSkill",
                "params":      {"url": url, "brand": rd.get("og_title", "")},
                "impact":      "+15–20 AIO crawlability",
                "priority":    n,
                "deploy_path": "/llm.txt",
            })
            n += 1

        if entity < self.ENTITY_OK:
            actions.append({
                "skill":    "EntityMapperSkill",
                "params":   {"url": url, "schema_types": ["Organization", "Person"]},
                "impact":   "+10–20 entity clarity",
                "priority": n,
            })
            n += 1

        if eeat < self.EEAT_OK or answer < self.ANSWER_OK:
            actions.append({
                "skill":    "EEATEnhancerSkill",
                "params":   {"url": url},
                "impact":   "+15–25 combined E-E-A-T + answer format",
                "priority": n,
            })
            n += 1

        actions.append({
            "skill":    "AIOCitationTrackerSkill",
            "params":   {"url": url, "brand": rd.get("og_title", url),
                         "target_queries": rd.get("target_keywords", [])[:5]},
            "impact":   "Establish citation baseline in ChatGPT / Perplexity / Google AIO",
            "priority": n,
        })

        gap = max(0, self.OVERALL_GOOD - (citation + eeat + answer + entity) / 4)
        return {
            "actions":               actions,
            "estimated_score_lift":  f"+{min(40, int(gap))} overall AIO score",
            "estimated_weeks":       2 + len([a for a in actions if a.get("deploy_path")]),
        }
