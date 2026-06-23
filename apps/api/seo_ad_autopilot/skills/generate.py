"""Content generation skills - returns structured output, not mock data."""

from __future__ import annotations

import time
from typing import Any

from .base import Skill, SkillCategory, SkillInput, SkillOutput, SkillRiskLevel


class ContentGeneratorSkill(Skill):
    """Content Generator - generates SEO-optimized content modules from site data."""
    
    @property
    def name(self) -> str:
        return "ContentGenerator"
    
    @property
    def description(self) -> str:
        return "Generate content modules (FAQ, news, guides) based on site style"
    
    @property
    def category(self) -> SkillCategory:
        return SkillCategory.GENERATE
    
    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.MEDIUM
    
    def execute(self, skill_input: SkillInput) -> SkillOutput:
        start_time = time.time()
        
        content_type = skill_input.params.get("type", "faq")
        url = skill_input.params.get("url", "")
        site_profile = skill_input.params.get("site_profile", {})
        
        if not url:
            return self._create_output(
                success=False,
                error="URL is required",
            )
        
        if content_type == "faq":
            result = {
                "url": url,
                "content_type": "faq",
                "schema_type": "FAQPage",
                "schema_json_ld": {
                    "@context": "https://schema.org",
                    "@type": "FAQPage",
                    "mainEntity": [],
                },
                "instructions": "Populate mainEntity with real Q&A pairs from the site's content. Use the site_profile to understand the business type and generate relevant questions.",
                "preview_html": "",
                "metadata": {
                    "word_count": 0,
                    "readability_score": 0,
                },
            }
        elif content_type == "article":
            result = {
                "url": url,
                "content_type": "article",
                "schema_type": "Article",
                "schema_json_ld": {
                    "@context": "https://schema.org",
                    "@type": "Article",
                    "headline": "",
                    "author": {"@type": "Organization", "name": site_profile.get("brand", "")},
                },
                "instructions": "Fill headline, datePublished, and articleBody from actual content. Use the site_profile for brand context.",
                "preview_html": "",
            }
        else:
            result = {
                "url": url,
                "content_type": content_type,
                "instructions": f"Generate {content_type} content based on the site's actual data and site_profile.",
                "preview_html": "",
            }
        
        execution_time = int((time.time() - start_time) * 1000)
        
        return self._create_output(
            success=True,
            result=result,
            execution_time_ms=execution_time,
        )
    
    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Target URL"},
                "type": {"type": "string", "enum": ["faq", "news", "guide", "comparison", "article"], "description": "Content type"},
                "site_profile": {"type": "object", "description": "Site profile data"},
                "style_tokens": {"type": "object", "description": "Style tokens to match"},
            },
            "required": ["url", "type"],
        }


class SchemaBuilderSkill(Skill):
    """Schema Builder - generates structured data templates from real site data."""
    
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
    
    def execute(self, skill_input: SkillInput) -> SkillOutput:
        start_time = time.time()
        
        schema_type = skill_input.params.get("type", "FAQPage")
        url = skill_input.params.get("url", "")
        data = skill_input.params.get("data", {})
        
        if not url:
            return self._create_output(
                success=False,
                error="URL is required",
            )
        
        schema_templates = {
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
        }
        
        json_ld = schema_templates.get(schema_type, {
            "@context": "https://schema.org",
            "@type": schema_type,
        })
        
        missing_fields = [k for k, v in json_ld.items() if not v and k not in ("@context", "@type")]
        
        result = {
            "url": url,
            "schema_type": schema_type,
            "json_ld": json_ld,
            "validation": {
                "valid": len(missing_fields) == 0,
                "missing_fields": missing_fields,
                "warnings": [f"Missing required field: {f}" for f in missing_fields],
            },
        }
        
        execution_time = int((time.time() - start_time) * 1000)
        
        return self._create_output(
            success=True,
            result=result,
            execution_time_ms=execution_time,
        )
    
    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Target URL"},
                "type": {"type": "string", "enum": ["FAQPage", "Product", "Article", "Organization"], "description": "Schema type"},
                "data": {"type": "object", "description": "Real data to include in schema"},
            },
            "required": ["url", "type"],
        }
