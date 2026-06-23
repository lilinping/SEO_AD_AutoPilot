"""Competitor Strategy Analyzer - 竞品策略分析模块

分析竞品网站的 SEO/GEO 策略，生成学习建议。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError


@dataclass
class CompetitorStrategy:
    """竞品策略分析结果"""
    url: str
    title: str
    seo_strategies: list[str]
    geo_strategies: list[str]
    unique_approaches: list[str]
    content_patterns: list[str]
    schema_types: list[str]
    strengths: list[str]
    weaknesses: list[str]
    learning_opportunities: list[str]
    overall_score: float


def analyze_competitor_strategy(url: str) -> Optional[CompetitorStrategy]:
    """分析单个竞品的策略"""
    
    try:
        # 抓取竞品网站
        request = Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        })
        
        with urlopen(request, timeout=10) as response:
            html = response.read().decode("utf-8", errors="ignore")
        
        # 分析 SEO 策略
        seo_strategies = _analyze_seo_strategies(html, url)
        
        # 分析 GEO 策略
        geo_strategies = _analyze_geo_strategies(html)
        
        # 识别独特做法
        unique_approaches = _identify_unique_approaches(html)
        
        # 分析内容模式
        content_patterns = _analyze_content_patterns(html)
        
        # 分析 Schema 类型
        schema_types = _analyze_schema_types(html)
        
        # 识别优势和劣势
        strengths, weaknesses = _identify_strengths_weaknesses(html, seo_strategies, geo_strategies)
        
        # 生成学习建议
        learning_opportunities = _generate_learning_opportunities(
            seo_strategies, geo_strategies, unique_approaches, content_patterns
        )
        
        # 计算综合评分
        overall_score = _calculate_overall_score(seo_strategies, geo_strategies, content_patterns)
        
        return CompetitorStrategy(
            url=url,
            title=_extract_title(html),
            seo_strategies=seo_strategies,
            geo_strategies=geo_strategies,
            unique_approaches=unique_approaches,
            content_patterns=content_patterns,
            schema_types=schema_types,
            strengths=strengths,
            weaknesses=weaknesses,
            learning_opportunities=learning_opportunities,
            overall_score=overall_score,
        )
    
    except Exception as e:
        print(f"[Competitor Analysis] Error analyzing {url}: {e}")
        return None


def _extract_title(html: str) -> str:
    """提取页面标题"""
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else "Unknown"


def _analyze_seo_strategies(html: str, url: str) -> list[str]:
    """分析 SEO 策略"""
    strategies = []
    
    # 检查标题标签
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE)
    if title_match:
        title = title_match.group(1)
        if 30 <= len(title) <= 60:
            strategies.append(f"标题长度优化 ({len(title)} 字符)")
    
    # 检查 Meta 描述
    meta_match = re.search(r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']*)["\']', html, re.IGNORECASE)
    if meta_match:
        meta = meta_match.group(1)
        if 120 <= len(meta) <= 160:
            strategies.append(f"元描述优化 ({len(meta)} 字符)")
    
    # 检查结构化数据
    if "application/ld+json" in html:
        strategies.append("使用 JSON-LD 结构化数据")
    
    # 检查 Open Graph
    if 'property="og:title"' in html or "og:title" in html:
        strategies.append("使用 Open Graph 标签")
    
    # 检查移动端
    if 'viewport' in html:
        strategies.append("移动端适配")
    
    # 检查 HTTPS
    if url.startswith("https://"):
        strategies.append("使用 HTTPS")
    
    return strategies


def _analyze_geo_strategies(html: str) -> list[str]:
    """分析 GEO 策略"""
    strategies = []
    
    # 检查引用信号
    citation_patterns = [
        r"according to",
        r"source:",
        r"study shows",
        r"research indicates",
        r"data from",
    ]
    
    for pattern in citation_patterns:
        if re.search(pattern, html.lower()):
            strategies.append(f"使用引用句式: {pattern}")
            break
    
    # 检查问答格式
    if re.search(r"what is|how to|why|when|where|faq|question", html.lower()):
        strategies.append("包含问答格式内容")
    
    # 检查列表格式
    if re.search(r"<ul|<ol|<li", html, re.IGNORECASE):
        strategies.append("使用列表格式")
    
    # 检查表格
    if "<table" in html:
        strategies.append("使用表格展示数据")
    
    return strategies


def _identify_unique_approaches(html: str) -> list[str]:
    """识别独特做法"""
    approaches = []
    
    # 检查交互元素
    if "interactive" in html.lower() or "calculator" in html.lower():
        approaches.append("包含交互式工具")
    
    # 检查视频内容
    if "<video" in html or "youtube" in html.lower():
        approaches.append("包含视频内容")
    
    # 检查用户生成内容
    if "review" in html.lower() or "comment" in html.lower():
        approaches.append("包含用户生成内容")
    
    # 检查个性化内容
    if "personalized" in html.lower() or "recommend" in html.lower():
        approaches.append("包含个性化推荐")
    
    return approaches


def _analyze_content_patterns(html: str) -> list[str]:
    """分析内容模式"""
    patterns = []
    
    # 检查内容长度
    text_content = re.sub(r"<[^>]+>", " ", html)
    word_count = len(text_content.split())
    
    if word_count > 2000:
        patterns.append("深度长内容")
    elif word_count > 500:
        patterns.append("中等内容")
    else:
        patterns.append("简洁内容")
    
    # 检查内容结构
    h2_count = len(re.findall(r"<h2", html, re.IGNORECASE))
    h3_count = len(re.findall(r"<h3", html, re.IGNORECASE))
    
    if h2_count > 5:
        patterns.append("清晰的标题层级")
    
    # 检查多媒体
    img_count = len(re.findall(r"<img", html, re.IGNORECASE))
    video_count = len(re.findall(r"<video", html, re.IGNORECASE))
    
    if img_count > 5:
        patterns.append("丰富的图片内容")
    if video_count > 0:
        patterns.append("包含视频内容")
    
    return patterns


def _analyze_schema_types(html: str) -> list[str]:
    """分析 Schema 类型"""
    schema_types = []
    
    schema_matches = re.findall(r'"@type"\s*:\s*"([^"]+)"', html)
    for schema_type in schema_matches:
        if schema_type not in schema_types:
            schema_types.append(schema_type)
    
    return schema_types


def _identify_strengths_weaknesses(
    html: str,
    seo_strategies: list[str],
    geo_strategies: list[str],
) -> tuple[list[str], list[str]]:
    """识别优势和劣势"""
    strengths = []
    weaknesses = []
    
    # 优势
    if len(seo_strategies) > 3:
        strengths.append("SEO 策略全面")
    if len(geo_strategies) > 2:
        strengths.append("GEO 策略良好")
    if "使用 JSON-LD 结构化数据" in seo_strategies:
        strengths.append("结构化数据完整")
    if "移动端适配" in seo_strategies:
        strengths.append("移动端友好")
    
    # 劣势
    if len(seo_strategies) < 2:
        weaknesses.append("SEO 策略不足")
    if len(geo_strategies) < 1:
        weaknesses.append("缺少 GEO 优化")
    if "使用 JSON-LD 结构化数据" not in seo_strategies:
        weaknesses.append("缺少结构化数据")
    
    return strengths, weaknesses


def _identify_unique_approaches(html: str) -> list[str]:
    """识别独特做法"""
    approaches = []
    
    # 检查独特的内容格式
    if "interactive" in html.lower() or "calculator" in html.lower():
        approaches.append("交互式工具")
    
    if "<video" in html:
        approaches.append("视频内容")
    
    if "review" in html.lower() or "rating" in html.lower():
        approaches.append("用户评价系统")
    
    return approaches


def _generate_learning_opportunities(
    seo_strategies: list[str],
    geo_strategies: list[str],
    unique_approaches: list[str],
    content_patterns: list[str],
) -> list[str]:
    """生成学习建议"""
    opportunities = []
    
    # 从 SEO 策略学习
    if "使用 JSON-LD 结构化数据" in seo_strategies:
        opportunities.append("学习竞品的结构化数据实现方式")
    
    if "标题长度优化" in seo_strategies:
        opportunities.append("参考竞品的标题优化策略")
    
    # 从 GEO 策略学习
    if "使用引用句式" in geo_strategies:
        opportunities.append("学习竞品的引用方式")
    
    if "包含问答格式内容" in geo_strategies:
        opportunities.append("参考竞品的 FAQ 内容组织")
    
    # 从独特做法学习
    for approach in unique_approaches:
        opportunities.append(f"学习竞品的{approach}")
    
    return opportunities


def _calculate_overall_score(
    seo_strategies: list[str],
    geo_strategies: list[str],
    content_patterns: list[str],
) -> float:
    """计算综合评分"""
    score = 50.0
    
    # SEO 策略加分
    score += len(seo_strategies) * 5
    
    # GEO 策略加分
    score += len(geo_strategies) * 5
    
    # 内容模式加分
    score += len(content_patterns) * 3
    
    return min(score, 100.0)


def analyze_all_competitors(
    competitors: list[dict[str, Any]],
    max_analysis: int = 5,
) -> list[CompetitorStrategy]:
    """分析所有竞品"""
    results = []
    
    for comp in competitors[:max_analysis]:
        strategy = analyze_competitor_strategy(comp["url"])
        if strategy:
            results.append(strategy)
    
    return results


def generate_competitor_insights(
    current_url: str,
    competitor_strategies: list[CompetitorStrategy],
) -> dict[str, Any]:
    """生成竞品洞察"""
    if not competitor_strategies:
        return {
            "total_competitors": 0,
            "avg_score": 0,
            "common_strategies": [],
            "unique_opportunities": [],
            "recommendations": ["未找到竞品，建议手动搜索同行业网站"],
        }
    
    # 统计常见策略
    all_seo_strategies = []
    all_geo_strategies = []
    all_learning = []
    
    for strategy in competitor_strategies:
        all_seo_strategies.extend(strategy.seo_strategies)
        all_geo_strategies.extend(strategy.geo_strategies)
        all_learning.extend(strategy.learning_opportunities)
    
    # 找出常见策略
    from collections import Counter
    common_seo = [s for s, count in Counter(all_seo_strategies).items() if count >= 2]
    common_geo = [s for s, count in Counter(all_geo_strategies).items() if count >= 2]
    
    # 计算平均分
    avg_score = sum(s.overall_score for s in competitor_strategies) / len(competitor_strategies)
    
    # 生成独特机会
    unique_opportunities = []
    for strategy in competitor_strategies:
        for approach in strategy.unique_approaches:
            if approach not in unique_opportunities:
                unique_opportunities.append(approach)
    
    return {
        "total_competitors": len(competitor_strategies),
        "avg_score": round(avg_score, 1),
        "common_seo_strategies": common_seo[:5],
        "common_geo_strategies": common_geo[:5],
        "unique_opportunities": unique_opportunities[:5],
        "top_learning": list(set(all_learning))[:5],
        "competitor_details": [
            {
                "url": s.url,
                "title": s.title,
                "score": s.overall_score,
                "strengths": s.strengths[:3],
            }
            for s in competitor_strategies[:3]
        ],
    }
