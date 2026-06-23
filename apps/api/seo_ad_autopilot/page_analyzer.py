"""页面元素分析模块 - CTA识别/转化路径/停留时长/信息密度/购买决策"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CTAElement:
    """CTA (Call-to-Action) 元素"""
    text: str
    selector: str
    cta_type: str  # primary, secondary, tertiary
    position: str  # header, hero, content, footer
    visibility_score: float  # 0-100


@dataclass
class ConversionPath:
    """转化路径"""
    steps: list[str]
    estimated_time_seconds: int
    friction_points: list[str]
    optimization_suggestions: list[str]


@dataclass
class ContentDensity:
    """信息密度"""
    word_count: int
    heading_count: int
    link_count: int
    image_count: int
    density_score: float  # 0-100
    readability_score: float  # 0-100


@dataclass
class PurchaseIntent:
    """购买意图信号"""
    has_pricing: bool
    has_cta_buy: bool
    has_reviews: bool
    has_comparison: bool
    has_faq: bool
    intent_level: str  # high, medium, low, none
    intent_score: float  # 0-100


# ─── CTA 识别 ─────────────────────────────────────────────────────────────

CTA_KEYWORDS = {
    "primary": ["buy", "purchase", "order", "subscribe", "sign up", "get started", "start free trial"],
    "secondary": ["learn more", "view details", "see more", "explore", "discover"],
    "tertiary": ["contact us", "support", "help", "faq", "about"],
}

CTA_SELECTORS = {
    "button": ["button", "[type='submit']", "input[type='submit']"],
    "link": ["a.button", "a.cta", ".btn", "[role='button']"],
    "form": ["form"],
}


def analyze_ctas(raw_data: dict) -> list[CTAElement]:
    """识别页面中的 CTA 元素"""
    ctas = []
    
    content = raw_data.get("content", "")
    headings = raw_data.get("headings", {})
    
    # 从标题中识别 CTA
    all_headings = []
    for level_headings in headings.values():
        all_headings.extend(level_headings)
    
    for heading in all_headings:
        heading_lower = heading.lower()
        for cta_type, keywords in CTA_KEYWORDS.items():
            for keyword in keywords:
                if keyword in heading_lower:
                    ctas.append(CTAElement(
                        text=heading,
                        selector=f"h2:contains('{heading[:30]}')",
                        cta_type=cta_type,
                        position="content",
                        visibility_score=70,
                    ))
                    break
    
    # 从链接中识别 CTA
    links = raw_data.get("links", [])
    for link in links:
        text = link.get("text", "").lower() if isinstance(link, dict) else str(link).lower()
        href = link.get("href", "") if isinstance(link, dict) else str(link)
        
        for cta_type, keywords in CTA_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    ctas.append(CTAElement(
                        text=text,
                        selector=f"a[href='{href}']",
                        cta_type=cta_type,
                        position="link",
                        visibility_score=60,
                    ))
                    break
    
    return ctas[:10]  # 最多返回 10 个 CTA


# ─── 转化路径分析 ─────────────────────────────────────────────────────────

def analyze_conversion_path(raw_data: dict, website_type: str) -> ConversionPath:
    """分析转化路径"""
    steps = []
    friction_points = []
    optimization_suggestions = []
    estimated_time = 0
    
    # 首页
    steps.append("首页")
    estimated_time += 5
    
    # 根据网站类型确定路径
    if website_type == "ecommerce":
        steps.extend(["浏览产品", "查看详情", "加入购物车", "结算支付"])
        estimated_time += 120
        friction_points.append("购物车放弃率可能较高")
        optimization_suggestions.append("简化结算流程")
        optimization_suggestions.append("添加信任徽章")
    elif website_type == "saas":
        steps.extend(["了解产品", "查看定价", "注册试用", "升级付费"])
        estimated_time += 300
        friction_points.append("注册流程可能较长")
        optimization_suggestions.append("提供免费试用")
    elif website_type == "blog":
        steps.extend(["阅读文章", "订阅 newsletter", "查看相关文章"])
        estimated_time += 180
        optimization_suggestions.append("添加 newsletter 订阅表单")
    else:
        steps.extend(["浏览内容", "联系我们"])
        estimated_time += 60
    
    return ConversionPath(
        steps=steps,
        estimated_time_seconds=estimated_time,
        friction_points=friction_points,
        optimization_suggestions=optimization_suggestions,
    )


# ─── 停留时长估算 ─────────────────────────────────────────────────────────

def estimate_dwell_time(raw_data: dict, website_type: str) -> dict[str, Any]:
    """估算用户停留时长"""
    word_count = raw_data.get("word_count", 0)
    image_count = len(raw_data.get("images", []))
    video_count = raw_data.get("video_count", 0)
    
    # 基础停留时间：阅读速度约 200-300 词/分钟
    reading_time_seconds = (word_count / 250) * 60
    
    # 图片/视频增加停留时间
    media_time = image_count * 3 + video_count * 30
    
    # 根据网站类型调整
    type_multiplier = {
        "ecommerce": 0.8,  # 电商用户浏览较快
        "blog": 1.5,  # 博客用户阅读较深
        "saas": 1.2,  # SaaS 用户中等
        "tool": 1.0,  # 工具站中等
        "media": 1.8,  # 媒体站停留较长
    }
    
    multiplier = type_multiplier.get(website_type, 1.0)
    estimated_seconds = (reading_time_seconds + media_time) * multiplier
    
    return {
        "estimated_seconds": int(estimated_seconds),
        "estimated_minutes": round(estimated_seconds / 60, 1),
        "reading_time_seconds": int(reading_time_seconds),
        "media_time_seconds": int(media_time),
        "word_count": word_count,
        "image_count": image_count,
    }


# ─── 信息密度评分 ─────────────────────────────────────────────────────────

def analyze_content_density(raw_data: dict) -> ContentDensity:
    """分析信息密度"""
    word_count = raw_data.get("word_count", 0)
    headings = raw_data.get("headings", {})
    heading_count = sum(len(v) for v in headings.values())
    link_count = len(raw_data.get("links", []))
    image_count = len(raw_data.get("images", []))
    
    # 密度评分：基于内容量和结构
    density_score = 50.0
    
    if word_count > 1000:
        density_score += 20
    elif word_count > 500:
        density_score += 10
    
    if heading_count > 5:
        density_score += 10
    
    if link_count > 10:
        density_score += 10
    
    if image_count > 3:
        density_score += 10
    
    # 可读性评分
    readability_score = 50.0
    
    if 200 < word_count < 3000:
        readability_score += 20
    
    if heading_count > 0:
        readability_score += 15
    
    if link_count > 0:
        readability_score += 10
    
    if image_count > 0:
        readability_score += 5
    
    return ContentDensity(
        word_count=word_count,
        heading_count=heading_count,
        link_count=link_count,
        image_count=image_count,
        density_score=min(density_score, 100),
        readability_score=min(readability_score, 100),
    )


# ─── 购买决策分析 ─────────────────────────────────────────────────────────

def analyze_purchase_intent(raw_data: dict, website_type: str) -> PurchaseIntent:
    """分析购买意图信号"""
    content = " ".join(raw_data.get("headings", {}).get("h1", []))
    content += " " + " ".join(raw_data.get("headings", {}).get("h2", []))
    links = raw_data.get("links", [])
    
    has_pricing = any(s in content.lower() for s in ["price", "pricing", "cost", "$", "€", "¥"])
    has_cta_buy = any(s in content.lower() for s in ["buy", "purchase", "order", "add to cart"])
    has_reviews = any(s in content.lower() for s in ["review", "rating", "testimonial"])
    has_comparison = any(s in content.lower() for s in ["comparison", "vs", "compare", "对比"])
    has_faq = any(s in content.lower() for s in ["faq", "question", "answer", "常见问题"])
    
    # 计算意图分数
    intent_score = 0
    if has_pricing:
        intent_score += 25
    if has_cta_buy:
        intent_score += 30
    if has_reviews:
        intent_score += 15
    if has_comparison:
        intent_score += 15
    if has_faq:
        intent_score += 15
    
    # 根据网站类型调整
    if website_type == "ecommerce":
        intent_score += 10
    
    # 确定意图级别
    if intent_score >= 70:
        intent_level = "high"
    elif intent_score >= 40:
        intent_level = "medium"
    elif intent_score >= 20:
        intent_level = "low"
    else:
        intent_level = "none"
    
    return PurchaseIntent(
        has_pricing=has_pricing,
        has_cta_buy=has_cta_buy,
        has_reviews=has_reviews,
        has_comparison=has_comparison,
        has_faq=has_faq,
        intent_level=intent_level,
        intent_score=min(intent_score, 100),
    )
