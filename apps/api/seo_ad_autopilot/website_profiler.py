"""Website Type Detection and Competitor Analysis.

根据网站特征自动检测类型，并查找该类型的最佳SEO/GEO策略。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse


@dataclass
class WebsiteProfile:
    """网站类型画像"""
    url: str
    website_type: str  # ecommerce, blog, saas, tool, media, local, corporate
    industry: str  # tech, finance, health, education, retail, etc.
    content_focus: str  # product, news, tutorial, comparison, etc.
    audience: str  # developer, consumer, business, etc.
    primary_language: str  # en, zh, etc.
    maturity_score: float  # 0-100
    signals: list[str] = field(default_factory=list)
    # 新增：产品分析
    product_info: dict[str, Any] = field(default_factory=dict)


# ─── 网站类型检测规则 ─────────────────────────────────────────────────────

ECOMMERCE_SIGNALS = [
    "shop", "store", "buy", "cart", "checkout", "price", "product",
    "add to cart", "purchase", "order", "payment", "shipping",
]

BLOG_SIGNALS = [
    "blog", "article", "post", "news", "press", "media",
    "author", "published", "updated", "comments",
]

SAAS_SIGNALS = [
    "pricing", "plans", "features", "demo", "trial", "signup",
    "dashboard", "platform", "software", "subscription",
]

TOOL_SIGNALS = [
    "calculator", "generator", "converter", "checker", "tool",
    "template", "analyzer", "optimizer", "scanner",
]

MEDIA_SIGNALS = [
    "video", "podcast", "episode", "watch", "listen",
    "stream", "channel", "subscribe",
]

LOCAL_SIGNALS = [
    "near me", "location", "address", "hours", "contact",
    "phone", "map", "directions", "appointment",
]

CORPORATE_SIGNALS = [
    "about us", "company", "team", "careers", "investor",
    "press release", "annual report", "governance",
]

# ─── 行业检测规则 ─────────────────────────────────────────────────────────

INDUSTRY_KEYWORDS = {
    "tech": ["software", "api", "developer", "cloud", "ai", "machine learning", "saas"],
    "finance": ["bank", "invest", "trading", "crypto", "fintech", "payment", "loan"],
    "health": ["health", "medical", "doctor", "patient", "treatment", "wellness"],
    "education": ["learn", "course", "tutorial", "training", "certification", "university"],
    "retail": ["shop", "store", "product", "brand", "fashion", "beauty"],
    "food": ["recipe", "restaurant", "food", "cooking", "delivery", "menu"],
    "travel": ["hotel", "flight", "booking", "travel", "destination", "tour"],
    "real_estate": ["property", "real estate", "listing", "agent", "mortgage"],
}


def detect_website_type(url: str, raw_data: dict) -> WebsiteProfile:
    """检测网站类型和行业"""
    domain = urlparse(url).netloc.lower()
    title = raw_data.get("title", "").lower()
    content = " ".join(raw_data.get("headings", {}).get("h1", [])).lower()
    content += " " + " ".join(raw_data.get("headings", {}).get("h2", [])).lower()
    links = [l.lower() for l in raw_data.get("links", [])]
    
    # 检测网站类型
    scores = {
        "ecommerce": 0,
        "blog": 0,
        "saas": 0,
        "tool": 0,
        "media": 0,
        "local": 0,
        "corporate": 0,
    }
    
    for signal in ECOMMERCE_SIGNALS:
        if signal in content or signal in title:
            scores["ecommerce"] += 2
        if any(signal in l for l in links):
            scores["ecommerce"] += 1
    
    for signal in BLOG_SIGNALS:
        if signal in content or signal in title:
            scores["blog"] += 2
        if any(signal in l for l in links):
            scores["blog"] += 1
    
    for signal in SAAS_SIGNALS:
        if signal in content or signal in title:
            scores["saas"] += 2
    
    for signal in TOOL_SIGNALS:
        if signal in content or signal in title:
            scores["tool"] += 2
    
    for signal in MEDIA_SIGNALS:
        if signal in content or signal in title:
            scores["media"] += 2
    
    for signal in LOCAL_SIGNALS:
        if signal in content or signal in title:
            scores["local"] += 2
    
    for signal in CORPORATE_SIGNALS:
        if signal in content or signal in title:
            scores["corporate"] += 2
    
    # 确定网站类型
    website_type = max(scores, key=scores.get)
    if scores[website_type] == 0:
        website_type = "corporate"
    
    # 检测行业
    industry = "general"
    for ind, keywords in INDUSTRY_KEYWORDS.items():
        for kw in keywords:
            if kw in content or kw in title:
                industry = ind
                break
    
    # 检测内容焦点
    content_focus = "general"
    if scores["ecommerce"] > scores["blog"]:
        content_focus = "product"
    elif scores["blog"] > scores["ecommerce"]:
        content_focus = "article"
    elif scores["tool"] > 0:
        content_focus = "utility"
    
    # 检测受众
    audience = "general"
    if any(s in content for s in ["developer", "api", "code", "programming"]):
        audience = "developer"
    elif any(s in content for s in ["business", "enterprise", "company"]):
        audience = "business"
    elif any(s in content for s in ["learn", "tutorial", "guide"]):
        audience = "learner"
    
    # 检测语言
    primary_language = "en"
    if re.search(r"[\u4e00-\u9fff]", raw_data.get("content", "")):
        primary_language = "zh"
    elif re.search(r"[\u3040-\u309f\u30a0-\u30ff]", raw_data.get("content", "")):
        primary_language = "ja"
    elif re.search(r"[\uac00-\ud7af]", raw_data.get("content", "")):
        primary_language = "ko"
    
    # 计算成熟度
    maturity_score = _calculate_maturity(raw_data, scores)
    
    # 生成信号列表
    signals = []
    if scores["ecommerce"] > 2:
        signals.append("电商网站")
    if scores["blog"] > 2:
        signals.append("博客/内容网站")
    if scores["saas"] > 2:
        signals.append("SaaS/软件服务")
    if scores["tool"] > 2:
        signals.append("工具网站")
    if scores["media"] > 2:
        signals.append("媒体网站")
    if scores["local"] > 2:
        signals.append("本地服务")
    if scores["corporate"] > 2:
        signals.append("企业官网")
    
    # 新增：产品分析
    product_info = _analyze_products(url, raw_data, website_type)
    
    return WebsiteProfile(
        url=url,
        website_type=website_type,
        industry=industry,
        content_focus=content_focus,
        audience=audience,
        primary_language=primary_language,
        maturity_score=maturity_score,
        signals=signals,
        product_info=product_info,
    )


def _analyze_products(url: str, raw_data: dict, website_type: str) -> dict[str, Any]:
    """分析网站的产品信息"""
    title = raw_data.get("title", "")
    meta = raw_data.get("meta_description", "")
    content = " ".join(raw_data.get("headings", {}).get("h1", []))
    content += " " + " ".join(raw_data.get("headings", {}).get("h2", []))
    links = raw_data.get("links", [])
    schema_data = raw_data.get("schema_data", [])
    
    product_info = {
        "has_products": False,
        "product_count": 0,
        "product_categories": [],
        "product_features": [],
        "pricing_info": [],
        "related_services": [],
        "product_schema": False,
        "has_reviews": False,
        "has_comparison": False,
        "has_buying_guide": False,
    }
    
    # 检测是否有产品
    product_signals = ["product", "item", "price", "buy", "shop", "catalog", "store", "purchase"]
    has_product_signals = any(s in (content + " " + title + " " + meta).lower() for s in product_signals)
    
    # 检测 Schema.org 产品数据
    for schema in schema_data:
        schema_type = schema.get("@type", "")
        if schema_type in ["Product", "Offer", "ItemList"]:
            product_info["product_schema"] = True
            product_info["has_products"] = True
        if schema_type == "Review":
            product_info["has_reviews"] = True
    
    if website_type == "ecommerce" or has_product_signals:
        product_info["has_products"] = True
        
        # 检测产品类别
        all_content = (content + " " + title + " " + meta).lower()
        
        category_signals = {
            "software": ["software", "app", "tool", "platform", "saas", "subscription"],
            "hardware": ["device", "gadget", "equipment", "tool", "instrument", "hardware"],
            "digital": ["ebook", "course", "template", "plugin", "theme", "digital"],
            "service": ["service", "consulting", "support", "training", "maintenance"],
            "subscription": ["subscription", "plan", "tier", "pricing", "monthly", "annual"],
            "physical": ["shipping", "delivery", "warehouse", "inventory", "stock"],
        }
        
        for category, signals in category_signals.items():
            if any(s in all_content for s in signals):
                product_info["product_categories"].append(category)
        
        # 检测产品特性
        feature_signals = {
            "feature": "功能特性",
            "benefit": "用户收益",
            "comparison": "产品对比",
            "review": "用户评价",
            "demo": "产品演示",
            "specification": "产品规格",
            "warranty": "保修服务",
        }
        for signal, desc in feature_signals.items():
            if signal in all_content:
                product_info["product_features"].append(desc)
        
        # 检测定价信息
        pricing_signals = ["price", "pricing", "cost", "$", "€", "¥", "free", "premium", "plan"]
        if any(s in all_content for s in pricing_signals):
            product_info["pricing_info"].append("pricing_detected")
            if "free" in all_content:
                product_info["pricing_info"].append("free_tier_available")
            if "premium" in all_content:
                product_info["pricing_info"].append("premium_tier_available")
        
        # 检测相关服务
        service_signals = {
            "support": "客户支持",
            "documentation": "文档服务",
            "tutorial": "教程服务",
            "api": "API 接口",
            "integration": "集成服务",
            "training": "培训服务",
        }
        for signal, desc in service_signals.items():
            if signal in all_content:
                product_info["related_services"].append(desc)
        
        # 检测是否有对比内容
        if "comparison" in all_content or "vs" in all_content or "对比" in all_content:
            product_info["has_comparison"] = True
        
        # 检测是否有购买指南
        if "guide" in all_content or "指南" in all_content or "how to choose" in all_content:
            product_info["has_buying_guide"] = True
    
    return product_info


def _calculate_maturity(raw_data: dict, type_scores: dict) -> float:
    """计算网站成熟度"""
    score = 30.0
    
    # 内容量
    word_count = raw_data.get("word_count", 0)
    if word_count > 2000:
        score += 15
    elif word_count > 1000:
        score += 10
    elif word_count > 500:
        score += 5
    
    # 结构化数据
    if raw_data.get("has_schema"):
        score += 10
    
    # HTTPS
    if raw_data.get("has_https"):
        score += 5
    
    # 移动端
    if raw_data.get("has_viewport"):
        score += 5
    
    # 标题层级
    headings = raw_data.get("headings", {})
    if len(headings.get("h2", [])) >= 3:
        score += 10
    
    # 链接数量
    links = raw_data.get("links", [])
    if len(links) > 20:
        score += 10
    
    return min(score, 100)


# ─── 竞品分析 ─────────────────────────────────────────────────────────────

@dataclass
class CompetitorInsight:
    """竞品分析洞察"""
    competitor_url: str
    strengths: list[str]
    weaknesses: list[str]
    opportunities: list[str]
    seo_score: float
    geo_score: float


def analyze_competitors(url: str, website_type: str, industry: str) -> list[CompetitorInsight]:
    """分析竞品的 SEO/GEO 策略"""
    
    # 根据网站类型和行业获取竞品洞察
    insights = []
    
    if website_type == "ecommerce":
        insights.append(CompetitorInsight(
            competitor_url="竞品电商网站",
            strengths=["丰富的商品描述", "用户评价系统", "产品 Schema 结构化数据"],
            weaknesses=["内容单一", "缺少博客/指南"],
            opportunities=["创建购买指南", "添加产品对比内容", "建立 FAQ 页面"],
            seo_score=75,
            geo_score=65,
        ))
    elif website_type == "blog":
        insights.append(CompetitorInsight(
            competitor_url="竞品博客网站",
            strengths=["深度长内容", "清晰的作者信息", "丰富的内部链接"],
            weaknesses=["更新频率低", "缺少多媒体"],
            opportunities=["增加视频内容", "创建系列文章", "添加交互元素"],
            seo_score=80,
            geo_score=70,
        ))
    elif website_type == "saas":
        insights.append(CompetitorInsight(
            competitor_url="竞品 SaaS 网站",
            strengths=["清晰的定价页面", "丰富的功能文档", "客户案例"],
            weaknesses=["缺少博客内容", "缺少教程"],
            opportunities=["创建教程内容", "添加客户案例", "建立帮助中心"],
            seo_score=70,
            geo_score=60,
        ))
    elif website_type == "tool":
        insights.append(CompetitorInsight(
            competitor_url="竞品工具网站",
            strengths=["实用的工具功能", "清晰的使用说明", "API 文档"],
            weaknesses=["缺少使用教程", "缺少博客内容"],
            opportunities=["创建使用教程", "添加 API 文档", "建立开发者社区"],
            seo_score=65,
            geo_score=55,
        ))
    else:
        insights.append(CompetitorInsight(
            competitor_url="竞品网站",
            strengths=["专业的品牌展示", "清晰的价值主张"],
            weaknesses=["内容较少", "缺少社交证明"],
            opportunities=["创建博客内容", "添加客户案例", "建立社交媒体存在"],
            seo_score=60,
            geo_score=50,
        ))
    
    return insights


# ─── 类型特定策略 ─────────────────────────────────────────────────────────

def get_type_specific_strategies(website_type: str, industry: str) -> dict[str, Any]:
    """根据网站类型和行业获取特定策略"""
    
    strategies = {
        "ecommerce": {
            "seo_focus": ["产品 Schema", "购买指南", "用户评价", "产品对比"],
            "geo_focus": ["产品信息结构化", "购买决策内容", "FAQ 和教程"],
            "content_types": ["购买指南", "产品对比", "用户评价", "使用教程"],
            "schema_types": ["Product", "Offer", "Review", "FAQPage"],
            "key_metrics": ["转化率", "购物车放弃率", "产品页停留时间"],
        },
        "blog": {
            "seo_focus": ["长内容优化", "作者权威", "内部链接", "内容新鲜度"],
            "geo_focus": ["深度研究内容", "引用和来源", "问答格式"],
            "content_types": ["深度文章", "教程", "案例研究", "行业报告"],
            "schema_types": ["Article", "Author", "FAQPage"],
            "key_metrics": ["页面浏览量", "停留时间", "分享数"],
        },
        "saas": {
            "seo_focus": ["功能页面", "定价页面", "客户案例", "帮助文档"],
            "geo_focus": ["产品功能说明", "使用教程", "对比内容"],
            "content_types": ["产品介绍", "教程", "案例研究", "帮助文档"],
            "schema_types": ["SoftwareApplication", "Organization", "FAQPage"],
            "key_metrics": ["注册转化率", "试用转化率", "功能使用率"],
        },
        "tool": {
            "seo_focus": ["工具使用说明", "API 文档", "教程内容"],
            "geo_focus": ["使用教程", "API 文档", "示例代码"],
            "content_types": ["使用教程", "API 文档", "示例代码", "案例研究"],
            "schema_types": ["HowTo", "TechArticle", "SoftwareApplication"],
            "key_metrics": ["工具使用率", "API 调用量", "用户留存率"],
        },
        "media": {
            "seo_focus": ["视频 SEO", "播客 SEO", "内容新鲜度", "社交分享"],
            "geo_focus": ["视频内容摘要", "播客转录", "热点追踪"],
            "content_types": ["视频", "播客", "新闻", "专题报道"],
            "schema_types": ["VideoObject", "PodcastEpisode", "NewsArticle"],
            "key_metrics": ["观看时长", "分享数", "订阅数"],
        },
        "local": {
            "seo_focus": ["本地 SEO", "Google My Business", "本地引用"],
            "geo_focus": ["本地商家信息", "位置相关搜索", "本地评论"],
            "content_types": ["本地新闻", "服务介绍", "客户案例"],
            "schema_types": ["LocalBusiness", "Event", "Offer"],
            "key_metrics": ["本地搜索排名", "到店转化", "电话咨询"],
        },
        "corporate": {
            "seo_focus": ["品牌页面", "投资者关系", "新闻发布"],
            "geo_focus": ["公司信息结构化", "高管信息", "新闻发布"],
            "content_types": ["公司介绍", "新闻发布", "投资者关系"],
            "schema_types": ["Organization", "Corporation", "NewsArticle"],
            "key_metrics": ["品牌搜索量", "新闻提及量", "社交提及量"],
        },
    }
    
    return strategies.get(website_type, strategies["corporate"])
