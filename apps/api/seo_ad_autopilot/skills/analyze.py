"""Analysis skills - delegates to real website profiler and analyzer."""

from __future__ import annotations

import time
from typing import Any

from .base import Skill, SkillCategory, SkillInput, SkillOutput, SkillRiskLevel


class StyleExtractorSkill(Skill):
    """Style Extractor - extracts UI style tokens from a website using real crawl data."""
    
    @property
    def name(self) -> str:
        return "StyleExtractor"
    
    @property
    def description(self) -> str:
        return "Extract colors, fonts, spacing, and layout tokens from a website"
    
    @property
    def category(self) -> SkillCategory:
        return SkillCategory.ANALYZE
    
    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.READ_ONLY
    
    def execute(self, skill_input: SkillInput) -> SkillOutput:
        start_time = time.time()
        
        url = skill_input.params.get("url", "")
        html = skill_input.params.get("html", "")
        
        if not url and not html:
            return self._create_output(
                success=False,
                error="URL or HTML content is required",
            )
        
        try:
            import re
            
            if not html and url:
                try:
                    from ..crawler import crawl_page_with_diagnostics
                    diagnostics = crawl_page_with_diagnostics(url)
                    html = diagnostics.get("snapshot", {}).get("html", "")
                except Exception:
                    html = ""
            
            if not html:
                return self._create_output(
                    success=False,
                    error=f"Could not fetch HTML from {url}. Ensure the URL is accessible.",
                    execution_time_ms=int((time.time() - start_time) * 1000),
                )
            
            colors = {}
            color_matches = re.findall(r'#[0-9a-fA-F]{3,8}|rgb\([^)]+\)|rgba\([^)]+\)', html)
            for c in color_matches[:20]:
                colors[c] = colors.get(c, 0) + 1
            sorted_colors = sorted(colors.items(), key=lambda x: x[1], reverse=True)
            
            fonts = set()
            font_matches = re.findall(r'font-family:\s*([^;}{]+)', html)
            for f in font_matches[:10]:
                fonts.add(f.strip().strip('"').strip("'"))
            
            font_sizes = set()
            size_matches = re.findall(r'font-size:\s*(\d+(?:\.\d+)?(?:px|rem|em|pt))', html)
            for s in size_matches[:10]:
                font_sizes.add(s)
            
            paddings = set()
            pad_matches = re.findall(r'padding:\s*(\d+(?:px|rem|em))', html)
            for p in pad_matches[:10]:
                paddings.add(p)
            
            max_width_match = re.search(r'max-width:\s*(\d+(?:px|rem|em))', html)
            max_width = max_width_match.group(1) if max_width_match else "unknown"
            
            grid_match = re.search(r'grid-template-columns:\s*repeat\((\d+)', html)
            grid_cols = int(grid_match.group(1)) if grid_match else 12
            
            result = {
                "url": url,
                "colors": {
                    "top_used": [c for c, _ in sorted_colors[:5]],
                    "primary": sorted_colors[0][0] if sorted_colors else "unknown",
                    "secondary": sorted_colors[1][0] if len(sorted_colors) > 1 else "unknown",
                    "accent": sorted_colors[2][0] if len(sorted_colors) > 2 else "unknown",
                },
                "fonts": {
                    "families": list(fonts)[:5] or ["unknown"],
                },
                "spacing": {
                    "font_sizes": list(font_sizes)[:5] or ["unknown"],
                    "paddings": list(paddings)[:5] or ["unknown"],
                },
                "layout": {
                    "max_width": max_width,
                    "grid_columns": grid_cols,
                },
            }
            
            execution_time = int((time.time() - start_time) * 1000)
            
            return self._create_output(
                success=True,
                result=result,
                execution_time_ms=execution_time,
            )
        
        except Exception as e:
            return self._create_output(
                success=False,
                error=f"Style extraction failed: {str(e)}",
                execution_time_ms=int((time.time() - start_time) * 1000),
            )
    
    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to extract styles from"},
                "html": {"type": "string", "description": "Raw HTML content (optional, overrides URL fetch)"},
            },
        }


class SiteAnalyzerSkill(Skill):
    """Site Analyzer - analyzes site structure using real crawl data."""
    
    @property
    def name(self) -> str:
        return "SiteAnalyzer"
    
    @property
    def description(self) -> str:
        return "Analyze site structure, content, and technical SEO"
    
    @property
    def category(self) -> SkillCategory:
        return SkillCategory.ANALYZE
    
    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.READ_ONLY
    
    def execute(self, skill_input: SkillInput) -> SkillOutput:
        start_time = time.time()
        
        url = skill_input.params.get("url", "")
        if not url:
            return self._create_output(
                success=False,
                error="URL is required",
            )
        
        try:
            import re
            from urllib.parse import urlparse
            
            try:
                from ..crawler import crawl_page_with_diagnostics
                diagnostics = crawl_page_with_diagnostics(url)
                snapshot = diagnostics.get("snapshot", {})
                html = snapshot.get("html", "")
                title = snapshot.get("title", "")
                description = snapshot.get("description", "")
                headings = snapshot.get("headings", [])
                links = snapshot.get("links", [])
                images = snapshot.get("images", [])
            except Exception:
                html = ""
                title = ""
                description = ""
                headings = []
                links = []
                images = []
            
            issues = []
            
            if not title:
                issues.append({"type": "critical", "message": "Missing page title"})
            elif len(title) > 60:
                issues.append({"type": "warning", "message": f"Title too long ({len(title)} chars, recommended <60)"})
            
            if not description:
                issues.append({"type": "critical", "message": "Missing meta description"})
            elif len(description) > 160:
                issues.append({"type": "warning", "message": f"Meta description too long ({len(description)} chars)"})
            
            if not headings:
                issues.append({"type": "warning", "message": "No headings found"})
            elif not any(h.startswith("H1") for h in headings):
                issues.append({"type": "critical", "message": "Missing H1 heading"})
            
            internal_links = [l for l in links if urlparse(l).netloc == urlparse(url).netloc or l.startswith("/")]
            external_links = [l for l in links if l.startswith("http") and urlparse(l).netloc != urlparse(url).netloc]
            
            if len(internal_links) < 3:
                issues.append({"type": "warning", "message": f"Few internal links ({len(internal_links)})"})
            
            images_without_alt = 0
            if html:
                img_tags = re.findall(r'<img[^>]*>', html, re.IGNORECASE)
                for img in img_tags:
                    if 'alt=' not in img.lower() or 'alt=""' in img.lower():
                        images_without_alt += 1
                if images_without_alt > 0:
                    issues.append({"type": "warning", "message": f"{images_without_alt} images without alt text"})
            
            schema_types = re.findall(r'"@type"\s*:\s*"([^"]+)"', html) if html else []
            
            score = 100
            for issue in issues:
                if issue["type"] == "critical":
                    score -= 20
                elif issue["type"] == "warning":
                    score -= 10
            score = max(0, min(100, score))
            
            result = {
                "url": url,
                "title": title,
                "description": description,
                "headings_count": len(headings),
                "headings": headings[:10],
                "links": {
                    "internal": len(internal_links),
                    "external": len(external_links),
                    "total": len(links),
                },
                "images": {
                    "total": len(images),
                    "without_alt": images_without_alt,
                },
                "schema_types": list(set(schema_types)),
                "technical_health": {
                    "score": score,
                    "issues": issues,
                },
                "seo_health": {
                    "score": score,
                    "issues": issues,
                },
            }
            
            execution_time = int((time.time() - start_time) * 1000)
            
            return self._create_output(
                success=True,
                result=result,
                execution_time_ms=execution_time,
            )
        
        except Exception as e:
            return self._create_output(
                success=False,
                error=f"Site analysis failed: {str(e)}",
                execution_time_ms=int((time.time() - start_time) * 1000),
            )
    
    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to analyze"},
            },
            "required": ["url"],
        }
