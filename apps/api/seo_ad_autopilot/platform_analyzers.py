"""Comprehensive Platform Analyzers - 每个平台的全面策略分析

每个 SEO/GEO 平台都有独立的、详细的分析逻辑和专属策略。
基于真实爬取数据，提供最全面的优化建议。
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse


# ═══════════════════════════════════════════════════════════════════════════
# SEO 平台分析器
# ═══════════════════════════════════════════════════════════════════════════

def _analyze_google(url: str, raw_data: dict) -> dict:
    """Google 深度分析 - 基于 2024/2025 Google 排名因素和 AI Overviews
    
    最新策略来源:
    - Google 2024 核心更新 (March, August, December)
    - E-E-A-T 评估体系
    - AI Overviews (原 SGE)
    - Core Web Vitals
    - Mobile-First Indexing
    - Helpful Content System
    """
    findings = []
    recs = []
    score = 20.0
    details = {"ranking_factors": [], "opportunities": [], "risks": [], "ai_overview": [], "eeat": []}
    
    # ── 1. E-E-A-T (Experience, Expertise, Authority, Trust) - 2024 核心 ──
    # Google 2024 年核心更新强调 E-E-A-T
    links = raw_data.get("links", [])
    has_about = any("/about" in l.lower() for l in links)
    has_author = bool(raw_data.get("author"))
    
    if has_about and has_author:
        findings.append("✅ E-E-A-T 信号良好 - 包含 About 页面和作者信息")
        score += 10
        details["eeat"].append("About 页面 + 作者信息")
    elif has_about:
        findings.append("⚠️ E-E-A-T 信号不完整 - 有 About 页面但缺少作者信息")
        recs.append("添加作者简介和资质信息，Google 2024 年强调 E-E-A-T")
        score += 5
    else:
        findings.append("❌ E-E-A-T 信号不足 - 缺少 About 页面和作者信息")
        recs.append("创建详细的 About 页面，包含团队介绍、使命愿景、联系方式")
        recs.append("添加作者简介和资质信息，这是 Google 2024 年核心更新的重点")
        details["risks"].append("E-E-A-T 信号不足可能导致排名下降")
    
    # ── 2. AI Overviews 优化 (2024 新功能) ──
    # Google 2024 年推出 AI Overviews，影响搜索结果展示
    content = " ".join(raw_data.get("headings", {}).get("h1", []))
    content += " " + " ".join(raw_data.get("headings", {}).get("h2", []))
    
    # 检查是否适合 AI Overviews
    has_direct_answer = bool(re.search(r"what is|how to|why|when|where|guide|tutorial", content.lower()))
    if has_direct_answer:
        findings.append("✅ 包含问答/指南格式 - 适合 Google AI Overviews 展示")
        score += 5
        details["ai_overview"].append("问答格式内容更容易被 AI Overviews 引用")
    else:
        recs.append("添加问答/指南格式内容，提高被 Google AI Overviews 引用的概率")
    
    # ── 3. Title Tag (权重: 高) ──
    title = raw_data.get("title", "")
    if not title:
        findings.append("❌ 缺少 title 标签 - 这是 Google 最重要的排名因素之一")
        recs.append("添加唯一的、描述性的 title 标签 (30-60 字符)")
        details["risks"].append("无 title 会导致 Google 无法理解页面主题")
    elif len(title) < 30:
        findings.append(f"⚠️ title 过短 ({len(title)} 字符) - 可能无法充分利用搜索结果展示空间")
        recs.append(f"当前 title 只有 {len(title)} 字符，建议扩展到 30-60 字符")
        score += 5
    elif len(title) > 60:
        findings.append(f"⚠️ title 过长 ({len(title)} 字符) - Google 通常显示 50-60 字符，超出部分会被截断")
        recs.append(f"当前 title 有 {len(title)} 字符，建议精简到 50-60 字符，把重要关键词放在前面")
        score += 5
    else:
        findings.append(f"✅ title 长度适中 ({len(title)} 字符) - 符合 Google 最佳实践")
        score += 15
        details["ranking_factors"].append("title_optimal")
    
    # ── 4. Meta Description (权重: 中) ──
    meta = raw_data.get("meta_description", "")
    if not meta:
        findings.append("❌ 缺少 meta description - Google 会自动截取页面内容作为摘要")
        recs.append("添加吸引人的 meta description (150-160 字符)，直接影响搜索结果点击率 (CTR)")
        details["risks"].append("无 meta description 可能导致 CTR 下降 5-10%")
    elif len(meta) < 120:
        findings.append(f"⚠️ meta description 过短 ({len(meta)} 字符) - 无法充分利用搜索结果展示空间")
        recs.append(f"当前描述只有 {len(meta)} 字符，建议扩展到 150-160 字符以获得更多展示空间")
        score += 5
    elif len(meta) > 160:
        findings.append(f"⚠️ meta description 过长 ({len(meta)} 字符) - 会被 Google 截断")
        recs.append(f"当前描述有 {len(meta)} 字符，建议精简到 150-160 字符，把核心卖点放在前 120 字符")
        score += 5
    else:
        findings.append(f"✅ meta description 长度适中 ({len(meta)} 字符) - 符合 Google 最佳实践")
        score += 10
        details["ranking_factors"].append("meta_optimal")
    
    # ── 5. HTTPS (权重: 高) ──
    if raw_data.get("has_https"):
        findings.append("✅ 已启用 HTTPS - Google 从 2014 年起将 HTTPS 作为排名信号")
        score += 10
        details["ranking_factors"].append("https_enabled")
    else:
        findings.append("❌ 未启用 HTTPS - Google 明确将 HTTPS 作为排名信号")
        recs.append("强烈建议启用 HTTPS，这是 Google 的硬性排名因素")
        details["risks"].append("HTTP 网站在搜索结果中会被标记为'不安全'")
    
    # ── 6. 结构化数据 (权重: 高) ──
    schema_data = raw_data.get("schema_data", [])
    if schema_data:
        schema_types = [s.get("@type", "unknown") for s in schema_data]
        findings.append(f"✅ 已添加结构化数据: {', '.join(schema_types)}")
        score += 15
        details["schema_types"] = schema_types
        details["ranking_factors"].append("schema_present")
    else:
        findings.append("❌ 缺少结构化数据 (Schema.org) - Google 使用结构化数据生成 Rich Snippets")
        recs.append("添加结构化数据可以获得 Google 搜索结果的富文本展示")
        recs.append("推荐 Schema 类型: Organization, Article, Product, FAQ, HowTo, BreadcrumbList")
    
    # ── 7. Open Graph (权重: 中) ──
    if raw_data.get("og_title") or raw_data.get("og_description"):
        findings.append("✅ 已添加 Open Graph 标签 - 影响社交媒体分享展示")
        score += 5
    else:
        findings.append("⚠️ 缺少 Open Graph 标签 - 社交媒体分享时无法显示自定义标题和描述")
        recs.append("添加 og:title, og:description, og:image 以优化社交媒体分享效果")
    
    # ── 8. Canonical (权重: 中) ──
    if raw_data.get("canonical"):
        findings.append("✅ 已设置 canonical URL - 避免重复内容问题")
        score += 5
    else:
        findings.append("⚠️ 未设置 canonical URL - 可能存在重复内容问题")
        recs.append("添加 <link rel='canonical'> 标签指向首选 URL")
    
    # ── 9. 移动端 (权重: 极高) ──
    if raw_data.get("has_viewport"):
        findings.append("✅ 已设置移动端视口 - 符合 Google Mobile-First Indexing")
        score += 10
    else:
        findings.append("❌ 缺少 viewport meta 标签 - Google 使用 Mobile-First Indexing")
        recs.append("添加 <meta name='viewport' content='width=device-width, initial-scale=1'>")
    
    # ── 10. 内容质量 (权重: 极高) ──
    word_count = raw_data.get("word_count", 0)
    if word_count > 2000:
        findings.append(f"✅ 内容非常充实 ({word_count} 词) - 高质量长内容")
        score += 10
    elif word_count > 1000:
        findings.append(f"✅ 内容充实 ({word_count} 词)")
        score += 5
    elif word_count > 300:
        findings.append(f"⚠️ 内容较少 ({word_count} 词)")
        recs.append("Google 偏好内容丰富的页面，建议增加到 1000+ 词")
    else:
        findings.append(f"❌ 内容过少 ({word_count} 词) - 可能被 Google 判定为薄内容")
        recs.append("页面内容过少，建议大幅增加内容")
    
    # ── 11. 链接分析 (权重: 高) ──
    internal_links = [l for l in links if not l.startswith("http")]
    external_links = [l for l in links if l.startswith("http")]
    
    findings.append(f"📊 链接结构: {len(internal_links)} 个内部链接, {len(external_links)} 个外部链接")
    
    if len(internal_links) < 3:
        recs.append("增加内部链接以帮助 Google 理解网站结构")
    
    # ── 12. 图片优化 ──
    images = raw_data.get("images", [])
    findings.append(f"📊 图片数量: {len(images)}")
    if len(images) > 0:
        recs.append("为所有图片添加描述性的 alt 属性")
    
    details["title_length"] = len(title)
    details["meta_length"] = len(meta)
    details["word_count"] = word_count
    details["internal_links"] = len(internal_links)
    details["external_links"] = len(external_links)
    details["image_count"] = len(images)
    
    return {
        "name": "Google",
        "type": "seo",
        "score": min(score, 100),
        "status": "analyzed",
        "findings": findings,
        "recommendations": recs,
        "details": details,
    }
    
    # ── 8. 内容质量 (权重: 极高) ──
    word_count = raw_data.get("word_count", 0)
    if word_count > 2000:
        findings.append(f"✅ 内容非常充实 ({word_count} 词) - 高质量长内容")
        score += 10
        details["ranking_factors"].append("content_rich")
    elif word_count > 1000:
        findings.append(f"✅ 内容充实 ({word_count} 词) - 符合 Google 内容质量要求")
        score += 5
    elif word_count > 300:
        findings.append(f"⚠️ 内容较少 ({word_count} 词) - Google 偏好内容丰富的页面")
        recs.append("Google 偏好内容丰富的页面，建议增加到 1000+ 词")
        details["opportunities"].append("增加内容深度可以提高排名")
    else:
        findings.append(f"❌ 内容过少 ({word_count} 词) - 可能被 Google 判定为薄内容")
        recs.append("页面内容过少，Google 可能认为是低质量页面，建议大幅增加内容")
        details["risks"].append("薄内容可能导致排名下降")
    
    # ── 9. 链接分析 (权重: 高) ──
    links = raw_data.get("links", [])
    internal_links = [l for l in links if not l.startswith("http")]
    external_links = [l for l in links if l.startswith("http")]
    
    findings.append(f"📊 链接结构: {len(internal_links)} 个内部链接, {len(external_links)} 个外部链接")
    
    if len(internal_links) < 3:
        recs.append("增加内部链接以帮助 Google 理解网站结构和页面关系")
        details["opportunities"].append("内部链接可以帮助 Google 发现更多页面")
    
    if len(external_links) > 0:
        # 检查是否有权威链接
        authority_domains = ["wikipedia.org", "github.com", "edu", "gov", "org"]
        authority_links = [l for l in external_links if any(ad in l.lower() for ad in authority_domains)]
        if authority_links:
            findings.append(f"✅ 包含 {len(authority_links)} 个权威来源链接")
            score += 5
    
    details["ranking_factors"].append("link_structure")
    details["internal_links"] = len(internal_links)
    details["external_links"] = len(external_links)
    
    # ── 10. 图片优化 (权重: 中) ──
    images = raw_data.get("images", [])
    findings.append(f"📊 图片数量: {len(images)}")
    if len(images) > 0:
        recs.append("为所有图片添加描述性的 alt 属性")
        details["opportunities"].append("图片 alt 属性帮助 Google 理解图片内容")
    
    # ── 11. URL 结构 ──
    parsed = urlparse(url)
    path = parsed.path
    if len(path) > 50:
        findings.append("⚠️ URL 路径较长")
        recs.append("保持 URL 简洁明了，使用关键词")
    
    details["title_length"] = len(title)
    details["meta_length"] = len(meta)
    details["word_count"] = word_count
    details["internal_links"] = len(internal_links)
    details["external_links"] = len(external_links)
    details["image_count"] = len(images)
    
    return {
        "name": "Google",
        "type": "seo",
        "score": min(score, 100),
        "status": "analyzed",
        "findings": findings,
        "recommendations": recs,
        "details": details,
    }


def _analyze_bing(url: str, raw_data: dict) -> dict:
    """Bing 深度分析 - 基于 Bing 的排名因素"""
    findings = []
    recs = []
    score = 20.0
    details = {"ranking_factors": [], "bing_specific": []}
    
    # ── 1. HTTPS ──
    if raw_data.get("has_https"):
        findings.append("✅ HTTPS 已启用")
        score += 10
        details["ranking_factors"].append("https")
    else:
        recs.append("启用 HTTPS")
    
    # ── 2. 结构化数据 ──
    if raw_data.get("has_schema"):
        findings.append("✅ 已添加结构化数据")
        score += 15
    else:
        recs.append("添加结构化数据")
    
    # ── 3. 站点地图 ──
    recs.append("注册 Bing Webmaster Tools 并提交 XML 站点地图")
    details["bing_specific"].append("Bing 非常重视站点地图提交")
    
    # ── 4. 社交信号 (Bing 特有) ──
    links = raw_data.get("links", [])
    social_domains = ["facebook.com", "twitter.com", "linkedin.com", "instagram.com", "tiktok.com"]
    social_links = [l for l in links if any(sd in l.lower() for sd in social_domains)]
    
    if social_links:
        findings.append(f"✅ 包含 {len(social_links)} 个社交媒体链接 - Bing 重视社交信号")
        score += 15
        details["bing_specific"].append("Bing 比 Google 更重视社交媒体信号")
    else:
        findings.append("⚠️ 缺少社交媒体链接 - Bing 重视社交信号")
        recs.append("Bing 比 Google 更重视社交媒体信号，建议添加社交媒体链接")
        details["bing_specific"].append("社交信号是 Bing 的重要排名因素")
    
    # ── 5. 内容质量 ──
    word_count = raw_data.get("word_count", 0)
    if word_count > 500:
        findings.append(f"✅ 内容质量良好 ({word_count} 词)")
        score += 10
    
    # ── 6. 权威信号 ──
    links = raw_data.get("links", [])
    has_about = any("/about" in l.lower() for l in links)
    if has_about:
        findings.append("✅ 包含 About 页面 - Bing 重视网站权威性")
        score += 10
    else:
        recs.append("创建 About 页面以提高网站权威性")
    
    has_privacy = any("/privacy" in l.lower() for l in links)
    if has_privacy:
        findings.append("✅ 包含隐私政策")
        score += 5
    
    # ── 7. Bing 特有因素 ──
    details["bing_specific"].append("Bing 使用机器学习来理解搜索意图")
    details["bing_specific"].append("Bing 更重视实体和知识图谱")
    
    details["social_links"] = len(social_links)
    details["word_count"] = word_count
    
    return {
        "name": "Bing",
        "type": "seo",
        "score": min(score, 100),
        "status": "analyzed",
        "findings": findings,
        "recommendations": recs,
        "details": details,
    }


def _analyze_baidu(url: str, raw_data: dict) -> dict:
    """百度深度分析 - 基于百度的排名因素"""
    findings = []
    recs = []
    score = 15.0
    details = {"baidu_specific": [], "china_market": []}
    
    # ── 1. 域名分析 ──
    domain = urlparse(url).netloc
    if ".cn" in domain or ".com.cn" in domain:
        findings.append("✅ 域名适合中国市场 (.cn/.com.cn)")
        score += 15
        details["china_market"].append("中国域名有助于百度排名")
    else:
        findings.append("⚠️ 域名不是中国域名")
        recs.append("考虑使用 .cn 或 .com.cn 域名以提高百度排名")
        details["china_market"].append("非中国域名在百度排名中处于劣势")
    
    # ── 2. HTTPS ──
    if raw_data.get("has_https"):
        findings.append("✅ HTTPS 已启用 - 百度重视网站安全")
        score += 10
    else:
        recs.append("百度重视 HTTPS，建议启用")
    
    # ── 3. ICP 备案 ──
    recs.append("必须完成 ICP 备案才能在中国正常展示")
    details["china_market"].append("ICP 备案是百度排名的必要条件")
    
    # ── 4. 百度生态 ──
    recs.append("注册百度站长平台并提交站点")
    recs.append("使用百度统计获取分析数据")
    recs.append("提交百度推送 API 加速收录")
    details["baidu_specific"].append("百度生态整合有助于排名")
    
    # ── 5. 内容分析 ──
    word_count = raw_data.get("word_count", 0)
    if word_count > 500:
        findings.append(f"✅ 内容充实 ({word_count} 词)")
        score += 10
    else:
        recs.append("百度偏好内容丰富的页面")
    
    # ── 6. 中文内容 ──
    content = raw_data.get("content", "")
    if re.search(r"[\u4e00-\u9fff]", content):
        findings.append("✅ 包含中文内容")
        score += 5
        details["china_market"].append("中文内容有助于百度排名")
    else:
        recs.append("添加中文内容以提高百度排名")
    
    details["domain"] = domain
    details["word_count"] = word_count
    
    return {
        "name": "百度",
        "type": "seo",
        "score": min(score, 100),
        "status": "analyzed",
        "findings": findings,
        "recommendations": recs,
        "details": details,
    }


# ═══════════════════════════════════════════════════════════════════════════
# GEO 平台分析器
# ═══════════════════════════════════════════════════════════════════════════

def _analyze_chatgpt(url: str, raw_data: dict) -> dict:
    """ChatGPT 深度分析 - 基于 2024/2025 OpenAI 的引用偏好和 GPT 搜索"""
    findings = []
    recs = []
    score = 15.0
    details = {"ai_specific": [], "citation_analysis": [], "gpt_search": []}
    
    content = " ".join(raw_data.get("headings", {}).get("h1", []))
    content += " " + " ".join(raw_data.get("headings", {}).get("h2", []))
    
    # ── 1. GPT 搜索优化 (2024 新功能) ──
    # ChatGPT 2024 年推出 SearchGPT，影响内容引用
    has_structured_content = bool(re.search(r"^\s*[\-\*]\s|^\s*\d+\.\s", content, re.MULTILINE))
    if has_structured_content:
        findings.append("✅ 包含结构化内容 - 适合 GPT 搜索引用")
        score += 5
        details["gpt_search"].append("结构化内容更容易被 GPT 搜索引用")
    
    # ── 2. 引用信号 (ChatGPT 核心偏好) ──
    citation_patterns = [
        (r"according to", "包含 'according to' 引用句式"),
        (r"source:", "包含 'source:' 来源标注"),
        (r"study shows", "包含 'study shows' 研究引用"),
        (r"research indicates", "包含 'research indicates' 研究引用"),
        (r"data from", "包含 'data from' 数据引用"),
        (r"published in", "包含 'published in' 发表引用"),
        (r"official", "包含 'official' 官方引用"),
        (r"verified", "包含 'verified' 验证引用"),
    ]
    
    found_citations = []
    for pattern, desc in citation_patterns:
        if re.search(pattern, content.lower()):
            found_citations.append(desc)
            score += 5
    
    if found_citations:
        findings.append(f"✅ 引用信号: {', '.join(found_citations)}")
        details["citation_analysis"] = found_citations
    else:
        findings.append("⚠️ 缺少引用信号 - ChatGPT 非常重视内容来源")
        recs.append("ChatGPT 偏好有来源引用的内容，建议添加 'According to...' 或 'Source:' 引用")
        recs.append("引用研究报告、官方数据或专家观点以提高可信度")
        recs.append("在关键声明后添加来源链接")
    
    # ── 3. 结构化数据 ──
    if raw_data.get("has_schema"):
        findings.append("✅ 已添加结构化数据 - 帮助 ChatGPT 理解内容结构")
        score += 15
    else:
        recs.append("添加 Schema.org 结构化数据帮助 ChatGPT 理解内容")
        recs.append("推荐: Article, FAQPage, HowTo, Organization Schema")
    
    # ── 4. 标题层级 ──
    headings = raw_data.get("headings", {})
    h2_count = len(headings.get("h2", []))
    h3_count = len(headings.get("h3", []))
    
    if h2_count >= 3:
        findings.append(f"✅ 标题层级清晰 ({h2_count} 个 H2, {h3_count} 个 H3)")
        score += 10
    elif h2_count >= 1:
        findings.append(f"⚠️ 标题层级较少 ({h2_count} 个 H2)")
        recs.append("ChatGPT 偏好结构清晰的内容，建议添加更多 H2/H3 标题")
    else:
        findings.append("❌ 缺少 H2 标题")
        recs.append("添加 H2/H3 标题来组织内容")
    
    # ── 5. 列表和表格 ──
    if "- " in content or "1." in content:
        findings.append("✅ 包含列表格式")
        score += 5
    
    # ── 6. 问答格式 ──
    if re.search(r"what is|how to|why|when|where", content.lower()):
        findings.append("✅ 包含问答格式")
        score += 5
    
    # ── 7. 内容深度 ──
    word_count = raw_data.get("word_count", 0)
    if word_count > 1000:
        findings.append(f"✅ 内容深度良好 ({word_count} 词)")
        score += 10
    elif word_count > 500:
        findings.append(f"⚠️ 内容深度一般 ({word_count} 词)")
        recs.append("建议增加到 1000+ 词")
    else:
        findings.append(f"❌ 内容过少 ({word_count} 词)")
        recs.append("建议大幅增加内容")
    
    details["citation_count"] = len(found_citations)
    details["h2_count"] = h2_count
    details["h3_count"] = h3_count
    details["word_count"] = word_count
    
    return {
        "name": "ChatGPT",
        "type": "geo",
        "score": min(score, 100),
        "status": "analyzed",
        "findings": findings,
        "recommendations": recs,
        "details": details,
    }


def _analyze_perplexity(url: str, raw_data: dict) -> dict:
    """Perplexity 深度分析 - 基于 2024/2025 Perplexity 的实时搜索和引用偏好
    
    最新策略来源:
    - Perplexity 2024 年强化实时搜索能力
    - Perplexity 引用追踪系统
    - Perplexity Pro 订阅服务
    - Perplexity Spaces 协作功能
    """
    findings = []
    recs = []
    score = 15.0
    details = {"ai_specific": [], "structure_analysis": [], "realtime_search": []}
    
    content = " ".join(raw_data.get("headings", {}).get("h1", []))
    content += " " + " ".join(raw_data.get("headings", {}).get("h2", []))
    
    # ── 1. 实时搜索优化 (2024 新功能) ──
    # Perplexity 2024 年强化实时搜索能力
    has_fresh_content = bool(re.search(r"2024|2025|latest|recent|updated", content.lower()))
    if has_fresh_content:
        findings.append("✅ 包含时效性内容 - Perplexity 重视实时信息")
        score += 5
        details["realtime_search"].append("时效性内容更容易被 Perplexity 引用")
    else:
        recs.append("添加时效性内容（最新数据、更新日期），Perplexity 重视实时信息")
    
    # ── 2. 内容深度 (Perplexity 核心偏好) ──
    word_count = raw_data.get("word_count", 0)
    if word_count > 2000:
        findings.append(f"✅ 内容深度优秀 ({word_count} 词) - Perplexity 偏好深度内容")
        score += 15
    elif word_count > 1000:
        findings.append(f"✅ 内容深度良好 ({word_count} 词)")
        score += 10
    elif word_count > 500:
        findings.append(f"⚠️ 内容深度一般 ({word_count} 词)")
        recs.append("Perplexity 偏好深度内容，建议增加到 1000+ 词")
    else:
        findings.append(f"❌ 内容过少 ({word_count} 词)")
        recs.append("Perplexity 偏好内容丰富的页面，建议大幅增加内容")
    
    # ── 3. FAQ 和问答 ──
    if re.search(r"what is|how to|why|when|where|faq|question|guide|tutorial", content.lower()):
        findings.append("✅ 包含问答格式 - Perplexity 偏好问答式内容")
        score += 10
    else:
        recs.append("添加 FAQ 部分，Perplexity 偏好问答格式的内容")
    
    # ── 4. 表格 (Perplexity 核心偏好) ──
    if "<table" in content or "|" in content:
        findings.append("✅ 包含表格数据 - Perplexity 偏好结构化数据")
        score += 10
    else:
        recs.append("使用表格展示对比数据，Perplexity 偏好结构化数据")
    
    # ── 5. 引用 ──
    if re.search(r"according to|source:|reference:|study|research|data", content.lower()):
        findings.append("✅ 包含引用信号")
        score += 10
    else:
        recs.append("添加来源引用，Perplexity 重视引用质量")
    
    # ── 6. 列表 ──
    if "- " in content or "1." in content:
        findings.append("✅ 包含列表格式")
        score += 5
    
    details["word_count"] = word_count
    
    return {
        "name": "Perplexity",
        "type": "geo",
        "score": min(score, 100),
        "status": "analyzed",
        "findings": findings,
        "recommendations": recs,
        "details": details,
    }


def _analyze_claude(url: str, raw_data: dict) -> dict:
    """Claude 深度分析 - 基于 2024/2025 Anthropic 的信任偏好和 Constitutional AI
    
    最新策略来源:
    - Anthropic Constitutional AI 原则
    - Claude 3.5/4 系列模型更新
    - Claude 搜索功能
    - Claude 企业版功能
    """
    findings = []
    recs = []
    score = 15.0
    details = {"ai_specific": [], "trust_signals": [], "constitutional_ai": []}
    
    links = raw_data.get("links", [])
    
    # ── 1. HTTPS (Claude 重视安全) ──
    if raw_data.get("has_https"):
        findings.append("✅ HTTPS 已启用 - Claude 重视网站安全")
        score += 5
        details["trust_signals"].append("HTTPS")
    else:
        findings.append("❌ 未启用 HTTPS - Claude 重视网站安全")
        recs.append("Claude 重视网站安全，强烈建议启用 HTTPS")
    
    # ── 2. About 页面 (Claude 核心偏好) ──
    has_about = any("/about" in l.lower() for l in links)
    if has_about:
        findings.append("✅ 包含 About 页面 - Claude 重视作者和组织信息")
        score += 15
        details["trust_signals"].append("About 页面")
        details["constitutional_ai"].append("About 页面帮助 Claude 理解网站背后的人和组织")
    else:
        findings.append("⚠️ 缺少 About 页面 - Claude 重视作者和组织信息")
        recs.append("创建详细的 About 页面，包含团队介绍、使命愿景、联系方式")
    
    # ── 3. 隐私政策 (Claude 重视合规) ──
    has_privacy = any("/privacy" in l.lower() or "/policy" in l.lower() for l in links)
    if has_privacy:
        findings.append("✅ 包含隐私政策 - Claude 重视网站合规性")
        score += 10
        details["trust_signals"].append("隐私政策")
        details["constitutional_ai"].append("隐私政策帮助 Claude 评估网站合规性")
    else:
        findings.append("⚠️ 缺少隐私政策 - Claude 重视网站合规性")
        recs.append("添加隐私政策页面，Claude 重视网站的信任信号")
    
    # ── 4. 联系方式 ──
    has_contact = any("/contact" in l.lower() for l in links)
    if has_contact:
        findings.append("✅ 包含联系方式 - 增加网站可信度")
        score += 5
        details["trust_signals"].append("联系方式")
    else:
        recs.append("添加联系方式页面，增加网站可信度")
    
    # ── 5. 社交媒体 ──
    social_domains = ["facebook.com", "twitter.com", "linkedin.com", "github.com", "instagram.com"]
    social_links = [l for l in links if any(sd in l.lower() for sd in social_domains)]
    if social_links:
        findings.append(f"✅ 包含 {len(social_links)} 个社交媒体/专业链接")
        score += 10
        details["trust_signals"].append(f"{len(social_links)} social links")
    else:
        recs.append("添加社交媒体和专业平台链接")
    
    # ── 6. 权威来源 ──
    authority_domains = ["wikipedia.org", "github.com", "edu", "gov", "org", "arxiv.org"]
    authority_links = [l for l in links if any(ad in l.lower() for ad in authority_domains)]
    if authority_links:
        findings.append(f"✅ 包含 {len(authority_links)} 个权威来源链接")
        score += 10
        details["trust_signals"].append(f"{len(authority_links)} authority links")
    else:
        recs.append("链接到权威来源 (Wikipedia, GitHub, .edu, .gov)")
    
    details["social_links"] = len(social_links)
    details["authority_links"] = len(authority_links)
    
    return {
        "name": "Claude",
        "type": "geo",
        "score": min(score, 100),
        "status": "analyzed",
        "findings": findings,
        "recommendations": recs,
        "details": details,
    }


def _analyze_ernie(url: str, raw_data: dict) -> dict:
    """文心一言 深度分析 - 基于百度 AI 的偏好"""
    findings = []
    recs = []
    score = 10.0
    details = {"baidu_ecosystem": [], "china_specific": []}
    
    domain = urlparse(url).netloc
    
    # ── 1. 域名分析 ──
    if ".cn" in domain or ".com.cn" in domain:
        findings.append("✅ 域名适合中国市场")
        score += 15
        details["china_specific"].append("中国域名有助于百度生态")
    else:
        findings.append("⚠️ 域名不是中国域名")
        recs.append("考虑使用 .cn 域名以提高百度生态排名")
    
    # ── 2. 结构化数据 ──
    if raw_data.get("has_schema"):
        findings.append("✅ 已添加结构化数据")
        score += 10
    else:
        recs.append("添加 Schema.org 结构化数据")
    
    # ── 3. 百度生态整合 ──
    recs.append("注册百度站长平台并验证网站")
    recs.append("使用百度统计获取用户行为数据")
    recs.append("提交百度推送 API 加速收录")
    recs.append("创建百度百科词条 (如品牌/产品适用)")
    details["baidu_ecosystem"].append("百度生态整合有助于文心一言理解内容")
    
    # ── 4. 中文内容 ──
    content = raw_data.get("content", "")
    if re.search(r"[\u4e00-\u9fff]", content):
        findings.append("✅ 包含中文内容")
        score += 5
    else:
        recs.append("添加中文内容")
    
    details["domain"] = domain
    
    return {
        "name": "文心一言",
        "type": "geo",
        "score": min(score, 100),
        "status": "analyzed",
        "findings": findings,
        "recommendations": recs,
        "details": details,
    }


def _analyze_qwen(url: str, raw_data: dict) -> dict:
    """通义千问 深度分析 - 基于阿里 AI 的偏好"""
    findings = []
    recs = []
    score = 10.0
    details = {"ali_ecosystem": [], "ecommerce_signals": []}
    
    # ── 1. 结构化数据 ──
    schema_data = raw_data.get("schema_data", [])
    if schema_data:
        schema_types = [s.get("@type", "") for s in schema_data]
        if "Product" in schema_types:
            findings.append("✅ 包含产品结构化数据 - 通义千问重视电商信息")
            score += 15
            details["ecommerce_signals"].append("Product Schema")
        else:
            findings.append("⚠️ 缺少产品结构化数据")
            recs.append("添加 Product Schema 以提高通义千问的电商理解")
    else:
        recs.append("添加结构化数据 (Product, Organization)")
    
    # ── 2. 阿里生态 ──
    links = raw_data.get("links", [])
    ali_domains = ["alibaba.com", "taobao.com", "tmall.com", "aliyun.com", "1688.com"]
    ali_links = [l for l in links if any(ad in l.lower() for ad in ali_domains)]
    
    if ali_links:
        findings.append(f"✅ 包含 {len(ali_links)} 个阿里生态链接")
        score += 10
        details["ali_ecosystem"].append(f"{len(ali_links)} Alibaba ecosystem links")
    else:
        recs.append("链接到阿里生态 (如适用): alibaba.com, taobao.com, tmall.com")
        details["ali_ecosystem"].append("阿里生态链接有助于通义千问理解内容")
    
    # ── 3. 产品信息 ──
    if raw_data.get("has_schema"):
        findings.append("✅ 包含结构化数据")
        score += 10
    
    # ── 4. 价格和规格 ──
    content = " ".join(raw_data.get("headings", {}).get("h1", []))
    content += " " + " ".join(raw_data.get("headings", {}).get("h2", []))
    if re.search(r"price|价格|规格|specification", content.lower()):
        findings.append("✅ 包含价格/规格信息 - 通义千问重视电商数据")
        score += 5
    
    details["ali_links"] = len(ali_links)
    
    return {
        "name": "通义千问",
        "type": "geo",
        "score": min(score, 100),
        "status": "analyzed",
        "findings": findings,
        "recommendations": recs,
        "details": details,
    }


def _analyze_deepseek(url: str, raw_data: dict) -> dict:
    """DeepSeek 深度分析 - 基于深度求索的技术偏好"""
    findings = []
    recs = []
    score = 10.0
    details = {"tech_signals": [], "github_analysis": []}
    
    content = " ".join(raw_data.get("headings", {}).get("h1", []))
    content += " " + " ".join(raw_data.get("headings", {}).get("h2", []))
    
    # ── 1. 技术内容 (DeepSeek 核心偏好) ──
    tech_patterns = [
        ("api", "API 接口"), ("code", "代码"), ("programming", "编程"),
        ("developer", "开发者"), ("technical", "技术"), ("documentation", "文档"),
        ("algorithm", "算法"), ("model", "模型"), ("training", "训练"),
    ]
    tech_matches = [desc for pattern, desc in tech_patterns if pattern in content.lower()]
    
    if tech_matches:
        findings.append(f"✅ 包含技术内容: {', '.join(tech_matches)}")
        score += 15
        details["tech_signals"] = tech_matches
    else:
        recs.append("添加技术内容和代码示例 - DeepSeek 重视技术内容")
        details["tech_signals"].append("技术内容是 DeepSeek 的重要信号")
    
    # ── 2. GitHub 链接 (DeepSeek 核心偏好) ──
    links = raw_data.get("links", [])
    github_links = [l for l in links if "github.com" in l.lower()]
    
    if github_links:
        findings.append(f"✅ 包含 {len(github_links)} 个 GitHub 链接 - DeepSeek 重视开源生态")
        score += 15
        details["github_analysis"] = [l for l in github_links[:5]]
    else:
        recs.append("引用 GitHub 开源项目 - DeepSeek 重视开源生态")
        details["tech_signals"].append("GitHub 链接是 DeepSeek 的重要信号")
    
    # ── 3. 代码示例 ──
    if "```" in content or "<code>" in content or "def " in content or "function " in content:
        findings.append("✅ 包含代码示例 - DeepSeek 重视技术文档")
        score += 10
    else:
        recs.append("添加代码示例和技术文档")
    
    # ── 4. API 文档 ──
    if re.search(r"api|endpoint|request|response|json|http", content.lower()):
        findings.append("✅ 包含 API 相关内容")
        score += 5
    
    details["tech_matches"] = tech_matches
    details["github_links"] = len(github_links)
    
    return {
        "name": "DeepSeek",
        "type": "geo",
        "score": min(score, 100),
        "status": "analyzed",
        "findings": findings,
        "recommendations": recs,
        "details": details,
    }


# ═══════════════════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════════════════

def analyze_all_platforms(url: str, raw_data: dict, website_profile: dict = None) -> tuple[list[dict], list[dict]]:
    """分析所有平台，返回 SEO 和 GEO 平台结果
    
    Args:
        url: 网站 URL
        raw_data: 爬取的原始数据
        website_profile: 网站类型画像 (可选，用于更精准的分析)
    """
    seo_platforms = [
        _analyze_google(url, raw_data),
        _analyze_bing(url, raw_data),
        _analyze_baidu(url, raw_data),
    ]
    
    geo_platforms = [
        _analyze_chatgpt(url, raw_data),
        _analyze_perplexity(url, raw_data),
        _analyze_claude(url, raw_data),
        _analyze_ernie(url, raw_data),
        _analyze_qwen(url, raw_data),
        _analyze_deepseek(url, raw_data),
    ]
    
    return seo_platforms, geo_platforms
