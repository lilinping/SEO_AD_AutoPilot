"""Analysis API - BettaFish 风格的详细分析流水线

分析流程:
1. 爬取网站 → 获取真实数据
2. 检测网站类型 → 确定行业和受众
3. 分析页面元素 → CTA/转化路径/停留时长/信息密度/购买决策
4. 根据类型查找最新 SEO/GEO 策略
5. 分析各平台表现
6. 参考竞品做法
7. 生成个性化建议
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .real_analyzer import crawl_website, analyze_page, get_seo_recommendations
from .agents.geo import GEOAgent
from .agents.base import SiteContext
from .ad_platforms.auto_discovery import analyze_site_for_ads
from .platform_analyzers import analyze_all_platforms
from .website_profiler import detect_website_type, analyze_competitors, get_type_specific_strategies
from .page_analyzer import analyze_ctas, analyze_conversion_path, estimate_dwell_time, analyze_content_density, analyze_purchase_intent
from .ad_analyzer import score_ad_slot, analyze_ad_async_config, generate_ad_telemetry, generate_ad_toggle_config, check_ad_policy
from .search_engine_api import search_engine_api
from .competitor_discovery import competitor_discovery
from .competitor_strategy_analyzer import analyze_all_competitors, generate_competitor_insights


# ─── Models ─────────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    url: str = Field(..., description="Website URL to analyze")
    include_seo: bool = Field(default=True)
    include_geo: bool = Field(default=True)
    include_ads: bool = Field(default=True)


class AnalyzeResponse(BaseModel):
    url: str
    title: str
    meta_description: str
    crawl_status: str
    website_profile: dict[str, Any]
    product_analysis: dict[str, Any]
    page_analysis: dict[str, Any]
    ad_slot_analysis: dict[str, Any]
    competitor_insights: list[dict[str, Any]]
    type_strategies: dict[str, Any]
    pipeline: list[dict[str, Any]]
    seo_platforms: list[dict[str, Any]]
    geo_platforms: list[dict[str, Any]]
    agent_outputs: list[dict[str, Any]]
    seo_score: int
    geo_scores: dict[str, float]
    ai_readiness: str
    ad_recommendations: list[dict[str, Any]]
    ad_readiness: dict[str, Any]
    technical: dict[str, Any]
    content: dict[str, Any]
    recommendations: list[dict[str, Any]]


router = APIRouter(prefix="/api", tags=["analysis"])


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_site(request: AnalyzeRequest) -> AnalyzeResponse:
    """BettaFish 风格的详细分析流水线
    
    分析流程:
    1. 爬取网站 → 获取真实数据
    2. 检测网站类型 → 确定行业和受众
    3. 根据类型查找最新 SEO/GEO 策略
    4. 分析各平台表现
    5. 参考竞品做法
    6. 生成个性化建议
    """
    url = request.url
    
    # Validate
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise HTTPException(status_code=400, detail="Invalid URL format")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid URL format")
    
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    
    start_time = datetime.now()
    pipeline = []
    
    # Stage 1: Crawl
    t = datetime.now()
    page_data = crawl_website(url)
    pipeline.append({"stage_id": "crawl", "stage_name": "网页抓取", "status": "completed", "agent": "WebCrawler", "duration_ms": int((datetime.now() - t).total_seconds() * 1000)})
    
    # Build raw data
    raw_data = {
        "url": url, "title": page_data.title, "meta_description": page_data.meta_description,
        "content": " ".join([h for headings in page_data.headings.values() for h in headings]),
        "headings": page_data.headings, "links": [l["href"] for l in page_data.links],
        "images": [i["src"] for i in page_data.images], "schema_data": page_data.schema_data,
        "has_schema": bool(page_data.schema_data), "has_https": page_data.has_https,
        "has_viewport": page_data.has_viewport, "canonical": page_data.canonical,
        "og_title": page_data.og_title, "og_description": page_data.og_description,
        "author": "", "word_count": page_data.word_count, "link_count": len(page_data.links),
    }
    
    # Stage 2: Website Type Detection
    t = datetime.now()
    website_profile = detect_website_type(url, raw_data)
    
    # Stage 2.5: Competitor Discovery (使用搜索引擎 API)
    competitors_found = competitor_discovery.discover_competitors(
        url, website_profile.website_type, website_profile.industry, max_results=5
    )
    
    # 分析竞品策略
    competitor_strategies = analyze_all_competitors(competitors_found, max_analysis=3)
    competitor_insights = generate_competitor_insights(url, competitor_strategies)
    
    # 合并传统竞品分析
    traditional_competitors = analyze_competitors(url, website_profile.website_type, website_profile.industry)
    type_strategies = get_type_specific_strategies(website_profile.website_type, website_profile.industry)
    
    pipeline.append({"stage_id": "profile", "stage_name": "网站类型检测 + 竞品发现", "status": "completed", "agent": "WebsiteProfiler + CompetitorDiscovery", "duration_ms": int((datetime.now() - t).total_seconds() * 1000)})
    
    # Stage 3: Page Element Analysis (CTA/转化路径/停留时长/信息密度/购买决策)
    t = datetime.now()
    ctas = analyze_ctas(raw_data)
    conversion_path = analyze_conversion_path(raw_data, website_profile.website_type)
    dwell_time = estimate_dwell_time(raw_data, website_profile.website_type)
    content_density = analyze_content_density(raw_data)
    purchase_intent = analyze_purchase_intent(raw_data, website_profile.website_type)
    page_analysis = {
        "ctas": [{"text": c.text, "type": c.cta_type, "position": c.position, "score": c.visibility_score} for c in ctas],
        "conversion_path": {
            "steps": conversion_path.steps,
            "estimated_time_seconds": conversion_path.estimated_time_seconds,
            "friction_points": conversion_path.friction_points,
            "optimization_suggestions": conversion_path.optimization_suggestions,
        },
        "dwell_time": dwell_time,
        "content_density": {
            "word_count": content_density.word_count,
            "heading_count": content_density.heading_count,
            "link_count": content_density.link_count,
            "image_count": content_density.image_count,
            "density_score": content_density.density_score,
            "readability_score": content_density.readability_score,
        },
        "purchase_intent": {
            "has_pricing": purchase_intent.has_pricing,
            "has_cta_buy": purchase_intent.has_cta_buy,
            "has_reviews": purchase_intent.has_reviews,
            "has_comparison": purchase_intent.has_comparison,
            "has_faq": purchase_intent.has_faq,
            "intent_level": purchase_intent.intent_level,
            "intent_score": purchase_intent.intent_score,
        },
    }
    pipeline.append({"stage_id": "page_analysis", "stage_name": "页面元素分析", "status": "completed", "agent": "PageAnalyzer", "duration_ms": int((datetime.now() - t).total_seconds() * 1000)})
    
    # Stage 4: SEO
    t = datetime.now()
    seo_analysis = analyze_page(page_data)
    seo_recs = get_seo_recommendations(seo_analysis)
    pipeline.append({"stage_id": "seo", "stage_name": "SEO 分析", "status": "completed", "agent": "SEOAnalyzer", "duration_ms": int((datetime.now() - t).total_seconds() * 1000)})
    
    # Stage 5: Platform Analysis (根据网站类型) + 真实搜索引擎 API
    t = datetime.now()
    seo_platforms, geo_platforms = analyze_all_platforms(url, raw_data, {"website_type": website_profile.website_type, "industry": website_profile.industry})
    
    # 集成真实搜索引擎 API
    search_analysis = search_engine_api.analyze_seo_presence(url)
    seo_recommendations_from_api = search_engine_api.generate_seo_recommendations(url, search_analysis)
    
    # 将真实搜索结果添加到平台分析中
    if search_analysis["google"]["configured"]:
        seo_platforms[0]["details"]["real_api_results"] = search_analysis["google"]["results_count"]
        seo_platforms[0]["details"]["api_status"] = "configured"
    else:
        seo_platforms[0]["details"]["api_status"] = "not_configured"
    
    if search_analysis["bing"]["configured"]:
        seo_platforms[1]["details"]["real_api_results"] = search_analysis["bing"]["results_count"]
        seo_platforms[1]["details"]["api_status"] = "configured"
    else:
        seo_platforms[1]["details"]["api_status"] = "not_configured"
    
    pipeline.append({"stage_id": "platforms", "stage_name": "平台分析", "status": "completed", "agent": "Multi-Platform", "duration_ms": int((datetime.now() - t).total_seconds() * 1000)})
    
    # Stage 6: GEO Agent
    t = datetime.now()
    geo_agent = GEOAgent()
    context = SiteContext(url=url, raw_data=raw_data)
    geo_output = geo_agent.analyze(context)
    geo_data = geo_output.content
    pipeline.append({"stage_id": "geo", "stage_name": "GEO 深度分析", "status": "completed", "agent": "GEOAgent", "duration_ms": int((datetime.now() - t).total_seconds() * 1000)})
    
    # Stage 7: Ads
    t = datetime.now()
    site_data = {"monthly_visits": 10000, "has_blog": "/blog" in url or "/news" in url, "content_type": "content" if "/blog" in url or "/news" in url else "general", "word_count": page_data.word_count}
    ad_analysis = analyze_site_for_ads(url, site_data)
    
    # 广告位四维评分
    ad_slot_scores = {
        "hero": score_ad_slot(raw_data, "hero").__dict__,
        "header": score_ad_slot(raw_data, "header").__dict__,
        "content": score_ad_slot(raw_data, "content").__dict__,
        "sidebar": score_ad_slot(raw_data, "sidebar").__dict__,
        "footer": score_ad_slot(raw_data, "footer").__dict__,
    }
    
    # 广告异步加载配置
    ad_async = analyze_ad_async_config(raw_data)
    
    # 广告埋点配置
    ad_telemetry = generate_ad_telemetry()
    
    # 广告开关配置
    ad_toggle = generate_ad_toggle_config()
    
    # 政策适配检查
    policy_check = check_ad_policy(raw_data)
    
    ad_slot_analysis = {
        "slot_scores": ad_slot_scores,
        "async_config": ad_async.__dict__,
        "telemetry": ad_telemetry.__dict__,
        "toggle_config": ad_toggle.__dict__,
        "policy_check": policy_check.__dict__,
    }
    
    pipeline.append({"stage_id": "ads", "stage_name": "广告分析", "status": "completed", "agent": "AdPlatform", "duration_ms": int((datetime.now() - t).total_seconds() * 1000)})
    
    # Stage 8: Report
    t = datetime.now()
    all_recs = []
    for rec in seo_recs:
        all_recs.append({"type": "seo", "priority": rec.get("priority", "medium"), "title": rec.get("title", ""), "description": rec.get("description", ""), "impact": rec.get("impact", ""), "actions": []})
    for rec in geo_data.get("recommendations", []):
        all_recs.append({"type": "geo", "priority": rec.get("priority", "medium"), "title": rec.get("title", ""), "description": rec.get("description", ""), "impact": rec.get("impact", ""), "actions": rec.get("actions", [])})
    # 添加真实搜索引擎 API 的建议
    for rec in seo_recommendations_from_api:
        all_recs.append({"type": "search_api", "priority": rec.get("priority", "info"), "title": rec.get("title", ""), "description": rec.get("description", ""), "impact": "", "actions": rec.get("actions", [])})
    pipeline.append({"stage_id": "report", "stage_name": "报告生成", "status": "completed", "agent": "Coordinator", "duration_ms": int((datetime.now() - t).total_seconds() * 1000)})
    
    agent_outputs = [
        {"agent_name": "WebCrawler", "agent_role": "crawler", "score": 100 if page_data.status_code == 200 else 0, "findings": [f"Status: {page_data.status_code}", f"Words: {page_data.word_count}"], "recommendations": []},
        {"agent_name": "WebsiteProfiler", "agent_role": "profiler", "score": website_profile.maturity_score, "findings": [f"Type: {website_profile.website_type}", f"Industry: {website_profile.industry}", f"Language: {website_profile.primary_language}"], "recommendations": []},
        {"agent_name": "PageAnalyzer", "agent_role": "page_analyzer", "score": content_density.density_score, "findings": [f"CTAs: {len(ctas)}", f"Dwell: {dwell_time['estimated_minutes']}min", f"Intent: {purchase_intent.intent_level}"], "recommendations": []},
        {"agent_name": "SEOAnalyzer", "agent_role": "seo", "score": seo_analysis.get("seo_score", 0), "findings": [f"Score: {seo_analysis.get('seo_score', 0)}/100"], "recommendations": [r.get("title", "") for r in seo_recs]},
        {"agent_name": "GEOAgent", "agent_role": "geo", "score": geo_data["geo_scores"]["overall"], "findings": [f"Citation: {geo_data['geo_scores']['citation']}", f"Entity: {geo_data['geo_scores']['entity']}"], "recommendations": [r.get("title", "") for r in geo_data.get("recommendations", [])]},
        {"agent_name": "AdPlatform", "agent_role": "ads", "score": ad_analysis.get("ad_readiness", {}).get("score", 0), "findings": [f"Grade: {ad_analysis.get('ad_readiness', {}).get('grade', 'D')}"], "recommendations": []},
    ]
    
    return AnalyzeResponse(
        url=url, title=page_data.title, meta_description=page_data.meta_description,
        crawl_status="success" if page_data.status_code == 200 else "error",
        website_profile={
            "type": website_profile.website_type,
            "industry": website_profile.industry,
            "content_focus": website_profile.content_focus,
            "audience": website_profile.audience,
            "language": website_profile.primary_language,
            "maturity_score": website_profile.maturity_score,
            "signals": website_profile.signals,
        },
        product_analysis=website_profile.product_info,
        page_analysis=page_analysis,
        ad_slot_analysis=ad_slot_analysis,
        competitor_insights=[
            {"url": c.competitor_url, "strengths": c.strengths, "weaknesses": c.weaknesses, "opportunities": c.opportunities, "seo_score": c.seo_score, "geo_score": c.geo_score}
            for c in traditional_competitors
        ],
        competitor_discovery=competitor_insights,
        type_strategies=type_strategies,
        pipeline=pipeline, seo_platforms=seo_platforms, geo_platforms=geo_platforms,
        agent_outputs=agent_outputs, seo_score=seo_analysis.get("seo_score", 0),
        geo_scores=geo_data["geo_scores"], ai_readiness=geo_data["ai_search_readiness"],
        ad_recommendations=ad_analysis.get("recommendations", []),
        ad_readiness=ad_analysis.get("ad_readiness", {"grade": "D", "score": 0}),
        technical=seo_analysis.get("technical", {}), content=seo_analysis.get("content", {}),
        recommendations=all_recs,
    )
