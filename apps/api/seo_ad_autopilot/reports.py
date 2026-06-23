"""Report generation system.

Inspired by BettaFish's ReportEngine:
- Multi-template support
- Structured report generation
- Export to multiple formats (HTML, JSON, Markdown)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from datetime import datetime


class ReportFormat(str, Enum):
    """Report output format."""
    HTML = "html"
    JSON = "json"
    MARKDOWN = "markdown"
    PDF = "pdf"


class ReportTemplate(str, Enum):
    """Report template types."""
    SEO_ANALYSIS = "seo_analysis"
    GEO_ANALYSIS = "geo_analysis"
    AD_AUDIT = "ad_audit"
    FULL_SITE_AUDIT = "full_site_audit"
    COMPETITOR_ANALYSIS = "competitor_analysis"


@dataclass
class ReportSection:
    """A section in the report."""
    title: str
    content: str
    data: dict[str, Any] = field(default_factory=dict)
    subsections: list["ReportSection"] = field(default_factory=list)


@dataclass
class Report:
    """Generated report."""
    report_id: str
    template: ReportTemplate
    url: str
    title: str
    sections: list[ReportSection] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    generated_at: datetime = field(default_factory=datetime.now)


class ReportGenerator:
    """Generate reports from analysis results."""
    
    def __init__(self):
        self._templates: dict[ReportTemplate, dict[str, Any]] = {
            ReportTemplate.SEO_ANALYSIS: {
                "title": "SEO Analysis Report",
                "sections": ["site_overview", "technical_seo", "content_analysis", "recommendations"],
            },
            ReportTemplate.GEO_ANALYSIS: {
                "title": "GEO Analysis Report",
                "sections": ["ai_readiness", "citation_analysis", "entity_optimization", "recommendations"],
            },
            ReportTemplate.AD_AUDIT: {
                "title": "Ad Readiness Report",
                "sections": ["site_profile", "platform_recommendations", "ad_slots", "implementation_guide"],
            },
            ReportTemplate.FULL_SITE_AUDIT: {
                "title": "Full Site Audit Report",
                "sections": ["executive_summary", "seo_analysis", "geo_analysis", "ad_analysis", "recommendations"],
            },
        }
    
    def generate(
        self,
        url: str,
        template: ReportTemplate,
        analysis_data: dict[str, Any],
        format: ReportFormat = ReportFormat.HTML,
    ) -> Report:
        """Generate a report from analysis data."""
        report_id = f"report_{uuid.uuid4().hex[:8]}"
        template_config = self._templates.get(template, {})
        
        # Build sections
        sections = self._build_sections(template, analysis_data)
        
        report = Report(
            report_id=report_id,
            template=template,
            url=url,
            title=template_config.get("title", "Analysis Report"),
            sections=sections,
            metadata={
                "generated_by": "SEO-AD AutoPilot",
                "version": "1.0.0",
            },
        )
        
        return report
    
    def _build_sections(
        self,
        template: ReportTemplate,
        data: dict[str, Any],
    ) -> list[ReportSection]:
        """Build report sections based on template."""
        sections = []
        
        if template == ReportTemplate.SEO_ANALYSIS:
            sections = self._build_seo_sections(data)
        elif template == ReportTemplate.GEO_ANALYSIS:
            sections = self._build_geo_sections(data)
        elif template == ReportTemplate.AD_AUDIT:
            sections = self._build_ad_sections(data)
        elif template == ReportTemplate.FULL_SITE_AUDIT:
            sections = self._build_full_audit_sections(data)
        
        return sections
    
    def _build_seo_sections(self, data: dict[str, Any]) -> list[ReportSection]:
        """Build SEO analysis sections."""
        return [
            ReportSection(
                title="Site Overview",
                content="Overview of the analyzed website.",
                data=data.get("site_profile", {}),
            ),
            ReportSection(
                title="Technical SEO",
                content="Technical SEO analysis results.",
                data=data.get("technical_seo", {}),
            ),
            ReportSection(
                title="Content Analysis",
                content="Content quality and structure analysis.",
                data=data.get("content_analysis", {}),
            ),
            ReportSection(
                title="Recommendations",
                content="Actionable SEO recommendations.",
                data={"recommendations": data.get("recommendations", [])},
            ),
        ]
    
    def _build_geo_sections(self, data: dict[str, Any]) -> list[ReportSection]:
        """Build GEO analysis sections."""
        return [
            ReportSection(
                title="AI Readiness Score",
                content="Overall GEO readiness assessment.",
                data=data.get("geo_scores", {}),
            ),
            ReportSection(
                title="Citation Analysis",
                content="How well the site is cited by AI engines.",
                data={"citation_score": data.get("geo_scores", {}).get("citation", 0)},
            ),
            ReportSection(
                title="Entity Optimization",
                content="Entity recognition and optimization status.",
                data={"entity_score": data.get("geo_scores", {}).get("entity", 0)},
            ),
            ReportSection(
                title="GEO Recommendations",
                content="Recommendations for improving AI search visibility.",
                data={"recommendations": data.get("recommendations", [])},
            ),
        ]
    
    def _build_ad_sections(self, data: dict[str, Any]) -> list[ReportSection]:
        """Build ad audit sections."""
        return [
            ReportSection(
                title="Site Profile",
                content="Site characteristics for ad matching.",
                data=data.get("site_profile", {}),
            ),
            ReportSection(
                title="Platform Recommendations",
                content="Recommended ad platforms based on site profile.",
                data={"platforms": data.get("ad_recommendations", [])},
            ),
            ReportSection(
                title="Ad Readiness",
                content="Overall ad readiness assessment.",
                data=data.get("ad_readiness", {}),
            ),
        ]
    
    def _build_full_audit_sections(self, data: dict[str, Any]) -> list[ReportSection]:
        """Build full audit sections."""
        return [
            ReportSection(
                title="Executive Summary",
                content="High-level summary of findings.",
                data={
                    "url": data.get("url", ""),
                    "geo_score": data.get("geo_scores", {}).get("overall", 0),
                    "ad_grade": data.get("ad_readiness", {}).get("grade", "N/A"),
                },
            ),
            *self._build_seo_sections(data),
            *self._build_geo_sections(data),
            *self._build_ad_sections(data),
        ]
    
    def export_html(self, report: Report) -> str:
        """Export report to HTML."""
        html_parts = [
            f"<!DOCTYPE html>",
            f"<html><head><title>{report.title}</title>",
            f"<style>body{{font-family:sans-serif;max-width:800px;margin:0 auto;padding:20px;}}</style>",
            f"</head><body>",
            f"<h1>{report.title}</h1>",
            f"<p><strong>URL:</strong> {report.url}</p>",
            f"<p><strong>Generated:</strong> {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}</p>",
            f"<hr>",
        ]
        
        for section in report.sections:
            html_parts.append(f"<h2>{section.title}</h2>")
            html_parts.append(f"<p>{section.content}</p>")
            if section.data:
                html_parts.append(f"<pre>{str(section.data)[:500]}</pre>")
        
        html_parts.append("</body></html>")
        return "\n".join(html_parts)
    
    def export_markdown(self, report: Report) -> str:
        """Export report to Markdown."""
        md_parts = [
            f"# {report.title}",
            f"",
            f"**URL:** {report.url}",
            f"**Generated:** {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            "---",
            "",
        ]
        
        for section in report.sections:
            md_parts.append(f"## {section.title}")
            md_parts.append(f"")
            md_parts.append(section.content)
            md_parts.append(f"")
        
        return "\n".join(md_parts)
    
    def export_json(self, report: Report) -> str:
        """Export report to JSON."""
        import json
        return json.dumps({
            "report_id": report.report_id,
            "template": report.template.value,
            "url": report.url,
            "title": report.title,
            "sections": [
                {"title": s.title, "content": s.content, "data": s.data}
                for s in report.sections
            ],
            "metadata": report.metadata,
            "generated_at": report.generated_at.isoformat(),
        }, indent=2)
    
    def export_pdf_html(self, report: Report) -> str:
        """Export report as PDF-ready HTML (can be converted to PDF with wkhtmltopdf or similar)."""
        html_parts = [
            "<!DOCTYPE html>",
            "<html><head>",
            f"<title>{report.title}</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }",
            "h1 { color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }",
            "h2 { color: #555; margin-top: 30px; }",
            ".meta { color: #666; font-size: 14px; margin-bottom: 20px; }",
            ".section { margin-bottom: 25px; padding: 15px; background: #f9f9f9; border-radius: 5px; }",
            ".score { font-size: 24px; font-weight: bold; color: #007bff; }",
            ".recommendation { margin: 5px 0; padding: 5px 10px; background: #e8f5e9; border-left: 3px solid #4caf50; }",
            ".warning { background: #fff3e0; border-left-color: #ff9800; }",
            ".error { background: #ffebee; border-left-color: #f44336; }",
            "@media print { body { margin: 20px; } }",
            "</style>",
            "</head><body>",
            f"<h1>{report.title}</h1>",
            f'<div class="meta">',
            f"<p><strong>URL:</strong> {report.url}</p>",
            f"<p><strong>Generated:</strong> {report.generated_at.strftime('%Y-%m-%d %H:%M:%S')}</p>",
            f"<p><strong>Report ID:</strong> {report.report_id}</p>",
            f"</div>",
            "<hr>",
        ]
        
        for section in report.sections:
            html_parts.append(f'<div class="section">')
            html_parts.append(f"<h2>{section.title}</h2>")
            html_parts.append(f"<p>{section.content}</p>")
            
            if section.data:
                if isinstance(section.data, dict):
                    for key, value in section.data.items():
                        if isinstance(value, (int, float)):
                            html_parts.append(f'<p><strong>{key}:</strong> <span class="score">{value}</span></p>')
                        elif isinstance(value, list):
                            html_parts.append(f"<p><strong>{key}:</strong></p>")
                            for item in value[:5]:
                                html_parts.append(f'<div class="recommendation">{item}</div>')
                        else:
                            html_parts.append(f"<p><strong>{key}:</strong> {str(value)[:200]}</p>")
            
            html_parts.append("</div>")
        
        html_parts.append("</body></html>")
        return "\n".join(html_parts)
    
    def export_all_formats(self, report: Report) -> dict[str, str]:
        """Export report to all formats."""
        return {
            "html": self.export_html(report),
            "markdown": self.export_markdown(report),
            "json": self.export_json(report),
            "pdf_html": self.export_pdf_html(report),
        }
