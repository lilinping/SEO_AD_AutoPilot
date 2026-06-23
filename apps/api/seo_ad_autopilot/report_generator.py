"""SEO 分析报告生成器 - 生成完整的分析报告"""

from __future__ import annotations

import json
from typing import Any
from datetime import datetime


def generate_seo_report(analysis_data: dict) -> str:
    """生成完整的 SEO 分析报告"""
    
    url = analysis_data.get("url", "")
    title = analysis_data.get("title", "")
    website_profile = analysis_data.get("website_profile", {})
    page_analysis = analysis_data.get("page_analysis", {})
    seo_score = analysis_data.get("seo_score", 0)
    geo_scores = analysis_data.get("geo_scores", {})
    ad_readiness = analysis_data.get("ad_readiness", {})
    technical = analysis_data.get("technical", {})
    content = analysis_data.get("content", {})
    recommendations = analysis_data.get("recommendations", [])
    competitor_insights = analysis_data.get("competitor_insights", [])
    type_strategies = analysis_data.get("type_strategies", {})
    
    report = []
    
    # ═══════════════════════════════════════════════════════════════════
    # 报告标题
    # ═══════════════════════════════════════════════════════════════════
    report.append("=" * 80)
    report.append("SEO-AD AutoPilot 分析报告")
    report.append("=" * 80)
    report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"分析网址: {url}")
    report.append(f"页面标题: {title}")
    report.append("")
    
    # ═══════════════════════════════════════════════════════════════════
    # 网站概览
    # ═══════════════════════════════════════════════════════════════════
    report.append("=" * 80)
    report.append("一、网站概览")
    report.append("=" * 80)
    report.append(f"网站类型: {website_profile.get('type', '未知')}")
    report.append(f"行业: {website_profile.get('industry', '未知')}")
    report.append(f"内容焦点: {website_profile.get('content_focus', '未知')}")
    report.append(f"目标受众: {website_profile.get('audience', '未知')}")
    report.append(f"主要语言: {website_profile.get('language', '未知')}")
    report.append(f"成熟度评分: {website_profile.get('maturity_score', 0)}/100")
    report.append(f"信号标签: {', '.join(website_profile.get('signals', []))}")
    report.append("")
    
    # ═══════════════════════════════════════════════════════════════════
    # 产品分析
    # ═══════════════════════════════════════════════════════════════════
    product = analysis_data.get("product_analysis", {})
    if product.get("has_products"):
        report.append("=" * 80)
        report.append("二、产品分析")
        report.append("=" * 80)
        report.append(f"产品类别: {', '.join(product.get('product_categories', []))}")
        report.append(f"产品特性: {', '.join(product.get('product_features', []))}")
        report.append(f"定价信息: {', '.join(product.get('pricing_info', []))}")
        report.append(f"相关服务: {', '.join(product.get('related_services', []))}")
        report.append(f"产品 Schema: {'已添加' if product.get('product_schema') else '未添加'}")
        report.append(f"用户评价: {'有' if product.get('has_reviews') else '无'}")
        report.append(f"产品对比: {'有' if product.get('has_comparison') else '无'}")
        report.append(f"购买指南: {'有' if product.get('has_buying_guide') else '无'}")
        report.append("")
    
    # ═══════════════════════════════════════════════════════════════════
    # 页面元素分析
    # ═══════════════════════════════════════════════════════════════════
    report.append("=" * 80)
    report.append("三、页面元素分析")
    report.append("=" * 80)
    
    # CTA 分析
    ctas = page_analysis.get("ctas", [])
    report.append(f"CTA 数量: {len(ctas)}")
    for cta in ctas[:5]:
        report.append(f"  - {cta.get('text', '')} ({cta.get('type', '')})")
    report.append("")
    
    # 转化路径
    conv_path = page_analysis.get("conversion_path", {})
    report.append("转化路径:")
    for step in conv_path.get("steps", []):
        report.append(f"  → {step}")
    report.append(f"预计时间: {conv_path.get('estimated_time_seconds', 0)}秒")
    if conv_path.get("friction_points"):
        report.append(f"摩擦点: {', '.join(conv_path.get('friction_points', []))}")
    report.append("")
    
    # 停留时长
    dwell = page_analysis.get("dwell_time", {})
    report.append(f"预计停留时长: {dwell.get('estimated_minutes', 0)}分钟")
    report.append("")
    
    # 信息密度
    density = page_analysis.get("content_density", {})
    report.append(f"信息密度评分: {density.get('density_score', 0)}/100")
    report.append(f"可读性评分: {density.get('readability_score', 0)}/100")
    report.append(f"字数: {density.get('word_count', 0)}")
    report.append(f"标题数: {density.get('heading_count', 0)}")
    report.append(f"链接数: {density.get('link_count', 0)}")
    report.append(f"图片数: {density.get('image_count', 0)}")
    report.append("")
    
    # 购买意图
    intent = page_analysis.get("purchase_intent", {})
    report.append("购买意图分析:")
    report.append(f"  意图级别: {intent.get('intent_level', 'none')}")
    report.append(f"  意图评分: {intent.get('intent_score', 0)}/100")
    report.append(f"  有定价信息: {'是' if intent.get('has_pricing') else '否'}")
    report.append(f"  有购买 CTA: {'是' if intent.get('has_cta_buy') else '否'}")
    report.append(f"  有用户评价: {'是' if intent.get('has_reviews') else '否'}")
    report.append(f"  有产品对比: {'是' if intent.get('has_comparison') else '否'}")
    report.append(f"  有 FAQ: {'是' if intent.get('has_faq') else '否'}")
    report.append("")
    
    # ═══════════════════════════════════════════════════════════════════
    # SEO 分析
    # ═══════════════════════════════════════════════════════════════════
    report.append("=" * 80)
    report.append("四、SEO 分析")
    report.append("=" * 80)
    report.append(f"SEO 总评分: {seo_score}/100")
    report.append("")
    
    # 技术状态
    report.append("技术状态:")
    report.append(f"  HTTPS: {'✓' if technical.get('has_https') else '✗'}")
    report.append(f"  移动端适配: {'✓' if technical.get('has_viewport') else '✗'}")
    report.append(f"  规范链接: {'✓' if technical.get('has_canonical') else '✗'}")
    report.append(f"  OG 标签: {'✓' if technical.get('has_og_tags') else '✗'}")
    report.append("")
    
    # 内容分析
    report.append("内容分析:")
    report.append(f"  字数: {content.get('word_count', 0)}")
    report.append(f"  内容状态: {content.get('status', '未知')}")
    report.append("")
    
    # ═══════════════════════════════════════════════════════════════════
    # GEO 分析
    # ═══════════════════════════════════════════════════════════════════
    report.append("=" * 80)
    report.append("五、GEO 分析 (AI 搜索引擎优化)")
    report.append("=" * 80)
    report.append(f"GEO 总评分: {geo_scores.get('overall', 0)}/100")
    report.append(f"AI 就绪度: {analysis_data.get('ai_readiness', '未知')}")
    report.append("")
    report.append("各维度评分:")
    report.append(f"  引用信号: {geo_scores.get('citation', 0)}/100")
    report.append(f"  实体识别: {geo_scores.get('entity', 0)}/100")
    report.append(f"  内容结构: {geo_scores.get('structure', 0)}/100")
    report.append(f"  权威信号: {geo_scores.get('authority', 0)}/100")
    report.append(f"  AI 存在感: {geo_scores.get('ai_presence', 0)}/100")
    report.append("")
    
    # ═══════════════════════════════════════════════════════════════════
    # 广告分析
    # ═══════════════════════════════════════════════════════════════════
    report.append("=" * 80)
    report.append("六、广告分析")
    report.append("=" * 80)
    report.append(f"广告就绪度: {ad_readiness.get('score', 0)}/100")
    report.append(f"广告等级: {ad_readiness.get('grade', 'D')}")
    report.append("")
    
    # 广告位评分
    ad_slot = analysis_data.get("ad_slot_analysis", {})
    if ad_slot:
        report.append("广告位四维评分:")
        slot_scores = ad_slot.get("slot_scores", {})
        for position, score_data in slot_scores.items():
            report.append(f"  {position}: {score_data.get('overall_score', 0):.0f}/100 - {score_data.get('recommendation', '')}")
        report.append("")
    
    # ═══════════════════════════════════════════════════════════════════
    # 竞品分析
    # ═══════════════════════════════════════════════════════════════════
    report.append("=" * 80)
    report.append("七、竞品分析")
    report.append("=" * 80)
    for competitor in competitor_insights:
        report.append(f"竞品: {competitor.get('url', '未知')}")
        report.append(f"  优势: {', '.join(competitor.get('strengths', []))}")
        report.append(f"  劣势: {', '.join(competitor.get('weaknesses', []))}")
        report.append(f"  机会: {', '.join(competitor.get('opportunities', []))}")
        report.append(f"  SEO 评分: {competitor.get('seo_score', 0)}")
        report.append(f"  GEO 评分: {competitor.get('geo_score', 0)}")
        report.append("")
    
    # ═══════════════════════════════════════════════════════════════════
    # 类型特定策略
    # ═══════════════════════════════════════════════════════════════════
    report.append("=" * 80)
    report.append("八、类型特定策略")
    report.append("=" * 80)
    if type_strategies:
        report.append("SEO 焦点:")
        for item in type_strategies.get("seo_focus", []):
            report.append(f"  • {item}")
        report.append("")
        report.append("GEO 焦点:")
        for item in type_strategies.get("geo_focus", []):
            report.append(f"  • {item}")
        report.append("")
        report.append("推荐内容类型:")
        for item in type_strategies.get("content_types", []):
            report.append(f"  • {item}")
        report.append("")
        report.append("推荐 Schema 类型:")
        for item in type_strategies.get("schema_types", []):
            report.append(f"  • {item}")
        report.append("")
        report.append("关键指标:")
        for item in type_strategies.get("key_metrics", []):
            report.append(f"  • {item}")
        report.append("")
    
    # ═══════════════════════════════════════════════════════════════════
    # 优化建议
    # ═══════════════════════════════════════════════════════════════════
    report.append("=" * 80)
    report.append("九、优化建议")
    report.append("=" * 80)
    
    high_priority = [r for r in recommendations if r.get("priority") == "high"]
    medium_priority = [r for r in recommendations if r.get("priority") == "medium"]
    low_priority = [r for r in recommendations if r.get("priority") == "low"]
    
    if high_priority:
        report.append("高优先级:")
        for rec in high_priority:
            report.append(f"  [{rec.get('type', '')}] {rec.get('title', '')}")
            report.append(f"    {rec.get('description', '')}")
            report.append(f"    影响: {rec.get('impact', '')}")
        report.append("")
    
    if medium_priority:
        report.append("中优先级:")
        for rec in medium_priority:
            report.append(f"  [{rec.get('type', '')}] {rec.get('title', '')}")
            report.append(f"    {rec.get('description', '')}")
        report.append("")
    
    if low_priority:
        report.append("低优先级:")
        for rec in low_priority:
            report.append(f"  [{rec.get('type', '')}] {rec.get('title', '')}")
        report.append("")
    
    # ═══════════════════════════════════════════════════════════════════
    # 总结
    # ═══════════════════════════════════════════════════════════════════
    report.append("=" * 80)
    report.append("十、总结")
    report.append("=" * 80)
    report.append(f"SEO 评分: {seo_score}/100")
    report.append(f"GEO 评分: {geo_scores.get('overall', 0)}/100")
    report.append(f"广告就绪度: {ad_readiness.get('score', 0)}/100 ({ad_readiness.get('grade', 'D')})")
    report.append(f"信息密度: {page_analysis.get('content_density', {}).get('density_score', 0)}/100")
    report.append(f"购买意图: {page_analysis.get('purchase_intent', {}).get('intent_level', 'none')}")
    report.append("")
    report.append("=" * 80)
    report.append("报告结束")
    report.append("=" * 80)
    
    return "\n".join(report)


def generate_html_report(analysis_data: dict) -> str:
    """生成 HTML 格式的分析报告"""
    
    url = analysis_data.get("url", "")
    title = analysis_data.get("title", "")
    website_profile = analysis_data.get("website_profile", {})
    seo_score = analysis_data.get("seo_score", 0)
    geo_scores = analysis_data.get("geo_scores", {})
    ad_readiness = analysis_data.get("ad_readiness", {})
    
    score_class = "score-good" if seo_score >= 70 else "score-medium" if seo_score >= 40 else "score-bad"
    geo_class = "score-good" if geo_scores.get("overall", 0) >= 70 else "score-medium" if geo_scores.get("overall", 0) >= 40 else "score-bad"
    ad_class = "score-good" if ad_readiness.get("score", 0) >= 70 else "score-medium" if ad_readiness.get("score", 0) >= 40 else "score-bad"
    
    html = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SEO Analysis Report</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #f5f5f5; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 20px; }
        .section { background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .section h2 { color: #333; border-bottom: 2px solid #667eea; padding-bottom: 10px; margin-top: 0; }
        .score { font-size: 24px; font-weight: bold; }
        .score-good { color: #4CAF50; }
        .score-medium { color: #FF9800; }
        .score-bad { color: #f44336; }
        .metric { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #eee; }
    </style>
</head>
<body>
    <div class="header">
        <h1>SEO Analysis Report</h1>
        <p>URL: """ + url + """</p>
        <p>Title: """ + title + """</p>
    </div>
    
    <div class="section">
        <h2>Scores</h2>
        <div class="metric"><span>SEO Score</span><span class="score """ + score_class + """">""" + str(seo_score) + """/100</span></div>
        <div class="metric"><span>GEO Score</span><span class="score """ + geo_class + """">""" + str(geo_scores.get('overall', 0)) + """/100</span></div>
        <div class="metric"><span>Ad Readiness</span><span class="score """ + ad_class + """">""" + str(ad_readiness.get('score', 0)) + """/100 (""" + ad_readiness.get('grade', 'D') + """)</span></div>
    </div>
    
    <div class="section">
        <h2>Website Info</h2>
        <div class="metric"><span>Type</span><span>""" + website_profile.get('type', 'Unknown') + """</span></div>
        <div class="metric"><span>Industry</span><span>""" + website_profile.get('industry', 'Unknown') + """</span></div>
        <div class="metric"><span>Audience</span><span>""" + website_profile.get('audience', 'Unknown') + """</span></div>
        <div class="metric"><span>Maturity</span><span>""" + str(website_profile.get('maturity_score', 0)) + """/100</span></div>
    </div>
    
    <div class="section">
        <h2>GEO Scores</h2>
        <div class="metric"><span>Citation</span><span>""" + str(geo_scores.get('citation', 0)) + """/100</span></div>
        <div class="metric"><span>Entity</span><span>""" + str(geo_scores.get('entity', 0)) + """/100</span></div>
        <div class="metric"><span>Structure</span><span>""" + str(geo_scores.get('structure', 0)) + """/100</span></div>
        <div class="metric"><span>Authority</span><span>""" + str(geo_scores.get('authority', 0)) + """/100</span></div>
        <div class="metric"><span>AI Presence</span><span>""" + str(geo_scores.get('ai_presence', 0)) + """/100</span></div>
    </div>
</body>
</html>
"""
    
    return html
    
    return html
