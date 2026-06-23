"""Real website analyzer - crawls and analyzes actual website content.

This module performs real website analysis:
- Fetches actual HTML content
- Parses meta tags, headings, links, images
- Analyzes page structure and content
- Provides real recommendations based on actual data
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import urlparse, urljoin
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


@dataclass
class PageData:
    """Real page data from crawling."""
    url: str
    title: str = ""
    meta_description: str = ""
    meta_keywords: str = ""
    canonical: str = ""
    og_title: str = ""
    og_description: str = ""
    og_image: str = ""
    headings: dict[str, list[str]] = field(default_factory=dict)
    links: list[dict[str, str]] = field(default_factory=list)
    images: list[dict[str, str]] = field(default_factory=list)
    schema_data: list[dict[str, Any]] = field(default_factory=list)
    content_length: int = 0
    word_count: int = 0
    has_https: bool = False
    has_viewport: bool = False
    has_favicon: bool = False
    status_code: int = 0
    error: Optional[str] = None


def crawl_website(url: str) -> PageData:
    """Crawl a website and extract real data."""
    page = PageData(url=url)
    
    # Ensure URL has scheme
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    
    page.has_https = url.startswith("https://")
    
    try:
        # Fetch the page
        request = Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
        
        with urlopen(request, timeout=10) as response:
            page.status_code = response.status
            html = response.read().decode("utf-8", errors="ignore")
            
            # Parse HTML
            _parse_html(page, html)
    
    except HTTPError as e:
        page.status_code = e.code
        page.error = f"HTTP Error: {e.code}"
    except URLError as e:
        page.error = f"Connection Error: {str(e.reason)}"
    except Exception as e:
        page.error = f"Error: {str(e)}"
    
    return page


def _parse_html(page: PageData, html: str) -> None:
    """Parse HTML content and extract data."""
    html_lower = html.lower()
    
    # Extract title
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if title_match:
        page.title = title_match.group(1).strip()
    
    # Extract meta description
    desc_match = re.search(r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']*)["\']', html, re.IGNORECASE)
    if not desc_match:
        desc_match = re.search(r'<meta\s+content=["\']([^"\']*)["\']\s+name=["\']description["\']', html, re.IGNORECASE)
    if desc_match:
        page.meta_description = desc_match.group(1).strip()
    
    # Extract meta keywords
    keywords_match = re.search(r'<meta\s+name=["\']keywords["\']\s+content=["\']([^"\']*)["\']', html, re.IGNORECASE)
    if keywords_match:
        page.meta_keywords = keywords_match.group(1).strip()
    
    # Extract canonical
    canonical_match = re.search(r'<link\s+rel=["\']canonical["\']\s+href=["\']([^"\']*)["\']', html, re.IGNORECASE)
    if canonical_match:
        page.canonical = canonical_match.group(1).strip()
    
    # Extract Open Graph tags
    og_title_match = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']*)["\']', html, re.IGNORECASE)
    if og_title_match:
        page.og_title = og_title_match.group(1).strip()
    
    og_desc_match = re.search(r'<meta\s+property=["\']og:description["\']\s+content=["\']([^"\']*)["\']', html, re.IGNORECASE)
    if og_desc_match:
        page.og_description = og_desc_match.group(1).strip()
    
    og_image_match = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']*)["\']', html, re.IGNORECASE)
    if og_image_match:
        page.og_image = og_image_match.group(1).strip()
    
    # Extract headings
    for level in range(1, 7):
        heading_matches = re.findall(f"<h{level}[^>]*>(.*?)</h{level}>", html, re.IGNORECASE | re.DOTALL)
        if heading_matches:
            # Clean HTML tags from headings
            cleaned = [re.sub(r"<[^>]+>", "", h).strip() for h in heading_matches]
            page.headings[f"h{level}"] = cleaned
    
    # Extract links
    link_matches = re.findall(r'<a\s+[^>]*href=["\']([^"\']*)["\'][^>]*>(.*?)</a>', html, re.IGNORECASE | re.DOTALL)
    for href, text in link_matches[:50]:  # Limit to 50 links
        if href.startswith(("http://", "https://", "/")):
            text_clean = re.sub(r"<[^>]+>", "", text).strip()
            if text_clean:
                page.links.append({"href": href, "text": text_clean[:100]})
    
    # Extract images
    img_matches = re.findall(r'<img\s+[^>]*src=["\']([^"\']*)["\'][^>]*>', html, re.IGNORECASE)
    for src in img_matches[:20]:  # Limit to 20 images
        page.images.append({"src": src})
    
    # Extract schema data
    schema_matches = re.findall(r'<script\s+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.IGNORECASE | re.DOTALL)
    for schema in schema_matches:
        try:
            import json
            data = json.loads(schema)
            page.schema_data.append(data)
        except:
            pass
    
    # Check viewport
    page.has_viewport = 'viewport' in html_lower
    
    # Check favicon
    page.has_favicon = 'rel="icon"' in html_lower or 'rel="shortcut icon"' in html_lower
    
    # Calculate content metrics
    text_content = re.sub(r"<[^>]+>", " ", html)
    text_content = re.sub(r"\s+", " ", text_content)
    page.content_length = len(text_content)
    page.word_count = len(text_content.split())


def analyze_page(page: PageData) -> dict[str, Any]:
    """Analyze page data and provide insights."""
    analysis = {
        "url": page.url,
        "status": "success" if page.status_code == 200 else "error",
        "status_code": page.status_code,
        "error": page.error,
    }
    
    # Title analysis
    analysis["title"] = {
        "value": page.title,
        "length": len(page.title),
        "status": "good" if 30 <= len(page.title) <= 60 else ("too_long" if len(page.title) > 60 else "too_short"),
        "recommendation": _get_title_recommendation(page.title),
    }
    
    # Meta description analysis
    analysis["meta_description"] = {
        "value": page.meta_description,
        "length": len(page.meta_description),
        "status": "good" if 120 <= len(page.meta_description) <= 160 else ("too_long" if len(page.meta_description) > 160 else "missing"),
        "recommendation": _get_meta_recommendation(page.meta_description),
    }
    
    # Headings analysis
    h1_count = len(page.headings.get("h1", []))
    analysis["headings"] = {
        "h1_count": h1_count,
        "h1_status": "good" if h1_count == 1 else ("multiple" if h1_count > 1 else "missing"),
        "total_headings": sum(len(v) for v in page.headings.values()),
        "structure": page.headings,
    }
    
    # Links analysis
    internal_links = [l for l in page.links if not l["href"].startswith("http")]
    external_links = [l for l in page.links if l["href"].startswith("http")]
    analysis["links"] = {
        "total": len(page.links),
        "internal": len(internal_links),
        "external": len(external_links),
        "has_internal_links": len(internal_links) > 0,
    }
    
    # Images analysis
    images_with_alt = 0  # Would need to check alt attributes
    analysis["images"] = {
        "total": len(page.images),
        "with_alt": images_with_alt,
    }
    
    # Schema analysis
    analysis["schema"] = {
        "has_schema": len(page.schema_data) > 0,
        "types": [s.get("@type", "unknown") for s in page.schema_data],
    }
    
    # Technical SEO
    analysis["technical"] = {
        "has_https": page.has_https,
        "has_viewport": page.has_viewport,
        "has_favicon": page.has_favicon,
        "has_canonical": bool(page.canonical),
        "has_og_tags": bool(page.og_title or page.og_description),
    }
    
    # Content analysis
    analysis["content"] = {
        "word_count": page.word_count,
        "content_length": page.content_length,
        "status": "good" if page.word_count > 300 else ("thin" if page.word_count > 0 else "empty"),
    }
    
    # Overall SEO score
    score = 50  # Base score
    if page.title and 30 <= len(page.title) <= 60:
        score += 10
    if page.meta_description and 120 <= len(page.meta_description) <= 160:
        score += 10
    if h1_count == 1:
        score += 5
    if page.has_https:
        score += 5
    if page.has_viewport:
        score += 5
    if page.schema_data:
        score += 10
    if page.word_count > 300:
        score += 5
    
    analysis["seo_score"] = min(score, 100)
    
    return analysis


def _get_title_recommendation(title: str) -> str:
    """Get recommendation for title."""
    if not title:
        return "添加唯一的、描述性的标题标签 (30-60 字符)"
    elif len(title) > 60:
        return f"标题过长 ({len(title)} 字符)，建议缩短到 60 字符以内"
    elif len(title) < 30:
        return f"标题过短 ({len(title)} 字符)，建议增加到 30 字符以上"
    return "标题长度合适"


def _get_meta_recommendation(meta: str) -> str:
    """Get recommendation for meta description."""
    if not meta:
        return "添加吸引人的元描述 (120-160 字符)"
    elif len(meta) > 160:
        return f"元描述过长 ({len(meta)} 字符)，建议缩短到 160 字符以内"
    elif len(meta) < 120:
        return f"元描述过短 ({len(meta)} 字符)，建议增加到 120 字符以上"
    return "元描述长度合适"


def get_seo_recommendations(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    """Generate SEO recommendations based on analysis."""
    recommendations = []
    
    # Title recommendations
    title_analysis = analysis.get("title", {})
    if title_analysis.get("status") != "good":
        recommendations.append({
            "type": "title",
            "priority": "high",
            "title": "优化标题标签",
            "description": title_analysis.get("recommendation", ""),
            "impact": "提高搜索结果点击率",
        })
    
    # Meta description recommendations
    meta_analysis = analysis.get("meta_description", {})
    if meta_analysis.get("status") != "good":
        recommendations.append({
            "type": "meta",
            "priority": "high",
            "title": "优化元描述",
            "description": meta_analysis.get("recommendation", ""),
            "impact": "提高搜索结果点击率",
        })
    
    # Heading recommendations
    headings = analysis.get("headings", {})
    if headings.get("h1_status") == "missing":
        recommendations.append({
            "type": "heading",
            "priority": "high",
            "title": "添加 H1 标题",
            "description": "页面缺少 H1 标题标签",
            "impact": "帮助搜索引擎理解页面主题",
        })
    elif headings.get("h1_status") == "multiple":
        recommendations.append({
            "type": "heading",
            "priority": "medium",
            "title": "使用唯一的 H1 标题",
            "description": f"页面有 {headings['h1_count']} 个 H1 标签，建议只保留 1 个",
            "impact": "明确页面主要主题",
        })
    
    # Technical recommendations
    technical = analysis.get("technical", {})
    if not technical.get("has_https"):
        recommendations.append({
            "type": "security",
            "priority": "high",
            "title": "启用 HTTPS",
            "description": "网站未使用 HTTPS，这会影响搜索排名和用户信任",
            "impact": "提高搜索排名和用户信任度",
        })
    
    if not technical.get("has_viewport"):
        recommendations.append({
            "type": "mobile",
            "priority": "high",
            "title": "添加移动端视口标签",
            "description": "缺少 viewport meta 标签，影响移动端显示",
            "impact": "改善移动端用户体验",
        })
    
    if not technical.get("has_canonical"):
        recommendations.append({
            "type": "canonical",
            "priority": "medium",
            "title": "添加规范链接",
            "description": "缺少 canonical 标签，可能导致重复内容问题",
            "impact": "避免搜索引擎惩罚重复内容",
        })
    
    if not technical.get("has_og_tags"):
        recommendations.append({
            "type": "social",
            "priority": "low",
            "title": "添加 Open Graph 标签",
            "description": "缺少 OG 标签，影响社交媒体分享效果",
            "impact": "改善社交媒体分享展示",
        })
    
    # Schema recommendations
    schema = analysis.get("schema", {})
    if not schema.get("has_schema"):
        recommendations.append({
            "type": "schema",
            "priority": "medium",
            "title": "添加结构化数据",
            "description": "页面缺少 Schema.org 结构化数据",
            "impact": "获得搜索结果富文本展示",
        })
    
    # Content recommendations
    content = analysis.get("content", {})
    if content.get("status") == "thin":
        recommendations.append({
            "type": "content",
            "priority": "medium",
            "title": "增加内容深度",
            "description": f"页面内容较少 ({content['word_count']} 词)，建议增加有价值的内容",
            "impact": "提高页面权威性和搜索排名",
        })
    
    return recommendations
