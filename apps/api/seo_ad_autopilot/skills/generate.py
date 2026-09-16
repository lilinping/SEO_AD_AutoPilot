"""Content generation skills — async execute() with LLMCostRouter integration.

Phase 1 P1 changes (GAP-005 / SKL-002 / ContentGeneratorSkill):
- execute() upgraded to async
- LLMCostRouter integration for real LLM calls (prompt-cached)
- Supports: content_type, topic, target_keywords, word_count, tone, locale
- Dual output: markdown + html
- Falls back to structured template when LLM env vars are absent
"""

from __future__ import annotations

import time
from typing import Any, Optional

from .base import Skill, SkillCategory, SkillInput, SkillOutput, SkillRiskLevel


# ── Helpers ───────────────────────────────────────────────────────────────────

def _markdown_to_html(md: str) -> str:
    """Minimal Markdown → HTML conversion (no external deps required)."""
    import re
    html = md
    # Headings
    html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
    html = re.sub(r"^## (.+)$",  r"<h2>\1</h2>", html, flags=re.MULTILINE)
    html = re.sub(r"^# (.+)$",   r"<h1>\1</h1>", html, flags=re.MULTILINE)
    # Bold / italic
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\*(.+?)\*",     r"<em>\1</em>", html)
    # Bullet lists
    html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)
    html = re.sub(r"(<li>.*?</li>\n?)+", r"<ul>\g<0></ul>", html, flags=re.DOTALL)
    # Paragraphs (blank-line delimited)
    paragraphs = re.split(r"\n{2,}", html)
    wrapped = []
    for p in paragraphs:
        p = p.strip()
        if p and not p.startswith("<"):
            p = f"<p>{p}</p>"
        wrapped.append(p)
    return "\n".join(wrapped)


async def _llm_generate(
    prompt: str,
    task_type: str,
    max_tokens: int = 2000,
    project_id: str = "default",
) -> Optional[str]:
    """Call LLM via LLMCostRouter.  Returns None if LLM is unavailable."""
    try:
        from ..utils.llm_router import LLMCostRouter

        router = LLMCostRouter(project_id=project_id)
        model_name = router.route(task_type)
        cache_key = LLMCostRouter.make_cache_key(prompt, task_type)

        # Check prompt cache first
        cached = router.get_cached(cache_key)
        if cached is not None:
            return cached

        # Attempt real LLM call via openai/anthropic SDK (if configured)
        text = await _dispatch_llm(model_name, prompt, max_tokens)
        if text:
            # Estimate token counts (rough heuristic: 1 token ≈ 4 chars)
            in_tokens  = len(prompt) // 4
            out_tokens = len(text)   // 4
            router.cache(cache_key, text, model_name, task_type, in_tokens, out_tokens)
        return text

    except Exception:  # noqa: BLE001
        return None


async def _dispatch_llm(model_name: str, prompt: str, max_tokens: int) -> Optional[str]:
    """Dispatch to the appropriate provider SDK based on model name."""
    import os

    # ── OpenAI / GPT-4 ──────────────────────────────────────────────────────
    if any(x in model_name for x in ("gpt-4", "gpt-3", "o1", "o3")):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=api_key)
            resp = await client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.7,
            )
            return resp.choices[0].message.content
        except Exception:
            return None

    # ── Anthropic / Claude ───────────────────────────────────────────────────
    if "claude" in model_name:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return None
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=api_key)
            msg = await client.messages.create(
                model=model_name,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text if msg.content else None
        except Exception:
            return None

    # ── Google Gemini ────────────────────────────────────────────────────────
    if "gemini" in model_name:
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            return None
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            resp = model.generate_content(prompt)
            return resp.text
        except Exception:
            return None

    # ── DeepSeek ─────────────────────────────────────────────────────────────
    if "deepseek" in model_name:
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            return None
        try:
            import openai
            client = openai.AsyncOpenAI(
                api_key=api_key,
                base_url="https://api.deepseek.com/v1",
            )
            resp = await client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.7,
            )
            return resp.choices[0].message.content
        except Exception:
            return None

    return None


# ── Prompt builders ───────────────────────────────────────────────────────────

def _build_faq_prompt(
    topic: str,
    keywords: list[str],
    tone: str,
    word_count: int,
    locale: str,
) -> str:
    lang = "Chinese (Simplified)" if locale.startswith("zh") else "English"
    kw_str = ", ".join(keywords[:10]) if keywords else "general"
    return (
        f"You are an expert SEO content writer. Write a comprehensive FAQ section in {lang}.\n"
        f"Topic: {topic}\n"
        f"Target keywords: {kw_str}\n"
        f"Tone: {tone}\n"
        f"Target length: approximately {word_count} words\n\n"
        f"Format requirements:\n"
        f"- Start with a brief introduction paragraph\n"
        f"- Include 6-10 Q&A pairs\n"
        f"- Each question should start with 'Q:' and answer with 'A:'\n"
        f"- Naturally incorporate the target keywords\n"
        f"- Use clear, concise language\n"
        f"- Format as clean Markdown\n\n"
        f"Output the FAQ content only, no meta-commentary."
    )


def _build_article_prompt(
    topic: str,
    keywords: list[str],
    tone: str,
    word_count: int,
    locale: str,
) -> str:
    lang = "Chinese (Simplified)" if locale.startswith("zh") else "English"
    kw_str = ", ".join(keywords[:10]) if keywords else "general"
    return (
        f"You are an expert SEO content writer. Write a high-quality long-form article in {lang}.\n"
        f"Topic: {topic}\n"
        f"Target keywords: {kw_str}\n"
        f"Tone: {tone}\n"
        f"Target length: approximately {word_count} words\n\n"
        f"Structure requirements:\n"
        f"- Compelling H1 title that includes the primary keyword\n"
        f"- Brief introduction (hook + keyword mention)\n"
        f"- 4-6 H2 sections with substantive content\n"
        f"- Include relevant sub-sections (H3) where appropriate\n"
        f"- Conclusion with key takeaways\n"
        f"- Naturally distribute target keywords throughout\n"
        f"- Format as clean Markdown\n\n"
        f"Output the article only, no meta-commentary."
    )


def _build_howto_prompt(
    topic: str,
    keywords: list[str],
    tone: str,
    word_count: int,
    locale: str,
) -> str:
    lang = "Chinese (Simplified)" if locale.startswith("zh") else "English"
    kw_str = ", ".join(keywords[:10]) if keywords else "general"
    return (
        f"You are an expert SEO content writer. Write a detailed how-to guide in {lang}.\n"
        f"Topic: How to {topic}\n"
        f"Target keywords: {kw_str}\n"
        f"Tone: {tone}\n"
        f"Target length: approximately {word_count} words\n\n"
        f"Structure requirements:\n"
        f"- H1: 'How to [Topic]'\n"
        f"- Brief overview of what the reader will achieve\n"
        f"- Prerequisites / What you'll need\n"
        f"- Step-by-step instructions (numbered, H3 headings per step)\n"
        f"- Each step: clear action + explanation\n"
        f"- Tips & troubleshooting section\n"
        f"- Summary / next steps\n"
        f"- Format as clean Markdown\n\n"
        f"Output the guide only, no meta-commentary."
    )


# ── Template fallbacks ────────────────────────────────────────────────────────

def _template_faq(topic: str, keywords: list[str], word_count: int) -> str:
    kw = keywords[0] if keywords else topic
    return f"""# Frequently Asked Questions: {topic}

Clear answers to the most common questions about {topic}.

## Q: What is {topic}?
A: {topic} refers to the practice and methodology of {kw}. It encompasses a range of strategies and best practices designed to improve outcomes.

## Q: Why does {topic} matter?
A: Understanding {topic} is essential for staying competitive. Businesses that invest in {kw} consistently outperform those that don't.

## Q: How do I get started with {topic}?
A: Begin by auditing your current situation, researching your target keywords, and developing a structured plan that aligns with your goals.

## Q: What are the key components of {topic}?
A: The key components include strategy development, technical implementation, content creation, and ongoing performance monitoring.

## Q: How long does it take to see results from {topic}?
A: Results typically appear within 3–6 months for organic strategies. Paid channels can show results within days.

## Q: What tools are recommended for {topic}?
A: Popular tools include Google Search Console, Ahrefs, SEMrush, and DataForSEO for data-driven decision making.
"""


def _template_article(topic: str, keywords: list[str], word_count: int) -> str:
    kw = keywords[0] if keywords else topic
    return f"""# The Complete Guide to {topic}

In today's competitive landscape, mastering {topic} is no longer optional — it's essential. This guide covers everything you need to know about {kw}.

## Understanding {topic}

{topic} is a multifaceted discipline that combines technical expertise with strategic thinking. Whether you're a seasoned professional or just getting started, a solid foundation in {kw} principles will accelerate your results.

## Key Strategies for {topic}

### Research and Planning
Before implementing any {topic} strategy, thorough research is essential. Identify your target audience, analyse competitor approaches, and establish clear KPIs.

### Implementation Best Practices
Effective implementation of {kw} requires a systematic approach. Start with quick wins, measure results, and iterate based on data.

### Measuring Success
Track key metrics including organic traffic, conversion rates, and return on investment. Regular reporting ensures alignment with business objectives.

## Common Mistakes to Avoid

Many practitioners stumble on the same pitfalls. Avoid these common mistakes to maximise your {topic} outcomes.

## Conclusion

Mastering {topic} is an ongoing journey. By applying these principles consistently and staying updated on industry developments, you'll achieve sustainable competitive advantage.
"""


def _template_howto(topic: str, keywords: list[str], word_count: int) -> str:
    kw = keywords[0] if keywords else topic
    return f"""# How To {topic}

This step-by-step guide walks you through everything you need to {topic.lower()} successfully.

## What You Will Need

- A working internet connection
- Access to the relevant platform or tool
- Approximately 30 minutes of focused time

## Step-by-Step Instructions

### Step 1: Preparation
Before you begin, gather all necessary information about {kw}. Review existing documentation and set clear objectives.

### Step 2: Initial Setup
Configure your environment and ensure all prerequisites are in place. Double-check settings before proceeding.

### Step 3: Core Implementation
Follow the primary workflow carefully. Pay attention to {kw}-specific requirements at this stage.

### Step 4: Validation
Verify that each component is working correctly. Test edge cases and document any unexpected behaviour.

### Step 5: Optimisation
Fine-tune your implementation based on initial results. Refer to best practices for {topic.lower()} to improve performance.

## Tips & Troubleshooting

- If you encounter issues, check the official documentation first
- Common errors are usually related to configuration — double-check your settings
- Community forums are an excellent resource for {kw}-specific questions

## Summary

You have successfully completed the {topic.lower()} process. Monitor your results regularly and revisit these steps as needed.
"""


# ── Main Skill classes ────────────────────────────────────────────────────────

class ContentGeneratorSkill(Skill):
    """Content Generator — async LLM-powered SEO content generation.

    Supports: faq / article / howto / listicle / comparison
    Parameters (via SkillInput.params):
        topic          str   – content topic (required unless url is given)
        content_type   str   – faq | article | howto | listicle | comparison
        keywords       list  – target keywords for natural embedding
        tone           str   – professional | authoritative | conversational | technical
        word_count     int   – target word count (default 800)
        locale         str   – en | zh-CN | etc.
        stream         bool  – reserved for future streaming support
    """

    @property
    def name(self) -> str:
        return "ContentGenerator"

    @property
    def description(self) -> str:
        return "Generate SEO-optimised content (FAQ/Article/HowTo) via LLM with keyword integration"

    @property
    def category(self) -> SkillCategory:
        return SkillCategory.GENERATE

    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.MEDIUM

    async def execute(self, skill_input: SkillInput) -> SkillOutput:   # type: ignore[override]
        start_time = time.time()

        params       = skill_input.params
        content_type = params.get("content_type", params.get("type", "article"))
        topic        = params.get("topic") or params.get("url") or "general topic"
        keywords     = params.get("keywords") or params.get("target_keywords") or []
        tone         = params.get("tone", "professional")
        word_count   = int(params.get("word_count", 800))
        locale       = params.get("locale", "en")

        # ── Build prompt ─────────────────────────────────────────────────────
        if content_type == "faq":
            prompt = _build_faq_prompt(topic, keywords, tone, word_count, locale)
            task_type = "content_generation"
            fallback_fn = lambda: _template_faq(topic, keywords, word_count)
        elif content_type == "howto":
            prompt = _build_howto_prompt(topic, keywords, tone, word_count, locale)
            task_type = "content_generation"
            fallback_fn = lambda: _template_howto(topic, keywords, word_count)
        else:  # article (default), listicle, comparison
            prompt = _build_article_prompt(topic, keywords, tone, word_count, locale)
            task_type = "content_generation"
            fallback_fn = lambda: _template_article(topic, keywords, word_count)

        # ── Attempt LLM call ─────────────────────────────────────────────────
        markdown_content = await _llm_generate(
            prompt=prompt,
            task_type=task_type,
            max_tokens=max(word_count * 2, 1500),
        )
        llm_used = markdown_content is not None
        if not llm_used:
            markdown_content = fallback_fn()

        html_content = _markdown_to_html(markdown_content)

        result = {
            "content_type": content_type,
            "topic": topic,
            "keywords": keywords,
            "locale": locale,
            "word_count_target": word_count,
            "word_count_actual": len(markdown_content.split()),
            "tone": tone,
            "markdown": markdown_content,
            "html": html_content,
            "llm_used": llm_used,
            "model": "template_fallback" if not llm_used else "llm_router_routed",
        }

        return self._create_output(
            success=True,
            result=result,
            execution_time_ms=int((time.time() - start_time) * 1000),
        )

    # ── Legacy sync wrapper (backwards-compatible) ────────────────────────────

    def execute_sync(self, skill_input: SkillInput) -> SkillOutput:
        """Synchronous wrapper for non-async callers."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    return pool.submit(asyncio.run, self.execute(skill_input)).result(timeout=60)
            return loop.run_until_complete(self.execute(skill_input))
        except RuntimeError:
            return asyncio.run(self.execute(skill_input))

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "topic":        {"type": "string",  "description": "Content topic"},
                "content_type": {"type": "string",  "enum": ["faq", "article", "howto", "listicle", "comparison"]},
                "keywords":     {"type": "array",   "items": {"type": "string"}, "description": "Target keywords"},
                "tone":         {"type": "string",  "enum": ["professional", "authoritative", "conversational", "technical"]},
                "word_count":   {"type": "integer", "minimum": 100, "maximum": 5000},
                "locale":       {"type": "string",  "description": "BCP-47 locale, e.g. en, zh-CN"},
            },
            "required": ["topic"],
        }


class SchemaBuilderSkill(Skill):
    """Schema Builder – generates structured data templates from site data."""

    @property
    def name(self) -> str:
        return "SchemaBuilder"

    @property
    def description(self) -> str:
        return "Generate JSON-LD structured data (FAQ, Product, Article, etc.)"

    @property
    def category(self) -> SkillCategory:
        return SkillCategory.GENERATE

    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.LOW

    async def execute(self, skill_input: SkillInput) -> SkillOutput:  # type: ignore[override]
        start_time = time.time()
        schema_type = skill_input.params.get("content_type", skill_input.params.get("type", "FAQPage"))
        url         = skill_input.params.get("url", "")
        data        = skill_input.params.get("data", {})

        schema_templates: dict[str, dict] = {
            "FAQPage": {
                "@context": "https://schema.org",
                "@type": "FAQPage",
                "mainEntity": data.get("mainEntity", []),
            },
            "Product": {
                "@context": "https://schema.org",
                "@type": "Product",
                "name": data.get("name", ""),
                "description": data.get("description", ""),
                "image": data.get("image", ""),
                "brand": {"@type": "Brand", "name": data.get("brand", "")},
                "offers": {
                    "@type": "Offer",
                    "price": data.get("price", ""),
                    "priceCurrency": data.get("currency", "USD"),
                },
            },
            "Article": {
                "@context": "https://schema.org",
                "@type": "Article",
                "headline": data.get("headline", ""),
                "author": data.get("author", {}),
                "datePublished": data.get("datePublished", ""),
            },
            "Organization": {
                "@context": "https://schema.org",
                "@type": "Organization",
                "name": data.get("name", ""),
                "url": data.get("url", url),
                "logo": data.get("logo", ""),
            },
            "HowTo": {
                "@context": "https://schema.org",
                "@type": "HowTo",
                "name": data.get("name", ""),
                "description": data.get("description", ""),
                "step": data.get("steps", []),
            },
            "LocalBusiness": {
                "@context": "https://schema.org",
                "@type": "LocalBusiness",
                "name": data.get("name", ""),
                "address": data.get("address", {}),
                "telephone": data.get("telephone", ""),
                "url": data.get("url", url),
            },
        }

        json_ld = schema_templates.get(
            schema_type,
            {"@context": "https://schema.org", "@type": schema_type},
        )

        result = {
            "url": url,
            "schema_type": schema_type,
            "json_ld": json_ld,
            "script_tag": f'<script type="application/ld+json">\n{__import__("json").dumps(json_ld, indent=2, ensure_ascii=False)}\n</script>',
        }

        return self._create_output(
            success=True,
            result=result,
            execution_time_ms=int((time.time() - start_time) * 1000),
        )

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url":          {"type": "string"},
                "content_type": {"type": "string", "enum": ["FAQPage", "Product", "Article", "Organization", "HowTo", "LocalBusiness"]},
                "data":         {"type": "object"},
            },
            "required": ["url"],
        }
