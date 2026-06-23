"""广告分析模块 - 四维评分/异步加载/埋点/开关/政策检查"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AdSlotScore:
    """广告位四维评分"""
    visibility: float  # 可视性 0-100
    ux_impact: float  # 对体验影响 0-100 (越高越差)
    conversion_risk: float  # 对转化风险 0-100 (越高越差)
    ad_type_match: float  # 适配广告类型 0-100
    overall_score: float  # 综合评分
    recommendation: str  # 建议


@dataclass
class AdAsyncConfig:
    """广告异步加载配置"""
    script_async: bool
    script_defer: bool
    lazy_loading: bool
    preload_hints: list[str]
    optimization_suggestions: list[str]


@dataclass
class AdTelemetry:
    """广告埋点配置"""
    impression_tracking: bool
    click_tracking: bool
    viewability_tracking: bool
    close_tracking: bool
    page_dwell_tracking: bool
    conversion_tracking: bool
    tracking_code: str
    events: list[str]


@dataclass
class AdToggleConfig:
    """广告开关配置"""
    has_toggle: bool
    toggle_selector: str
    frequency_capping: bool
    position_replacement: bool
    revenue_tracking: bool
    quick_disable: bool


@dataclass
class PolicyCheck:
    """政策适配检查"""
    platform: str
    compliance_level: str  # compliant, warning, violation
    issues: list[str]
    recommendations: list[str]
    risk_level: str  # low, medium, high


# ─── 广告位四维评分 ─────────────────────────────────────────────────────

def score_ad_slot(raw_data: dict, slot_position: str = "content") -> AdSlotScore:
    """广告位四维评分"""
    
    # 1. 可视性评分 (Visibility)
    visibility = 70.0  # 默认中等
    
    # 根据位置调整
    position_visibility = {
        "hero": 90,
        "header": 85,
        "content": 70,
        "sidebar": 50,
        "footer": 40,
    }
    visibility = position_visibility.get(slot_position, 70)
    
    # 2. 对体验影响 (UX Impact) - 越高越差
    ux_impact = 30.0  # 默认低影响
    
    # 根据位置调整
    position_ux_impact = {
        "hero": 70,  # 首屏影响大
        "header": 50,  # 导航区影响中等
        "content": 30,  # 内容区影响小
        "sidebar": 20,  # 侧边栏影响小
        "footer": 10,  # 页脚影响最小
    }
    ux_impact = position_ux_impact.get(slot_position, 30)
    
    # 3. 对转化风险 (Conversion Risk) - 越高越差
    conversion_risk = 20.0  # 默认低风险
    
    position_conversion_risk = {
        "hero": 60,  # 首屏风险高
        "header": 40,  # 导航区风险中等
        "content": 20,  # 内容区风险低
        "sidebar": 15,  # 侧边栏风险低
        "footer": 10,  # 页脚风险最低
    }
    conversion_risk = position_conversion_risk.get(slot_position, 20)
    
    # 4. 适配广告类型 (Ad Type Match)
    ad_type_match = 70.0  # 默认中等
    
    # 根据内容类型调整
    content = raw_data.get("content", "")
    if "article" in content.lower() or "blog" in content.lower():
        ad_type_match = 85  # 文章页适合多种广告
    elif "product" in content.lower() or "shop" in content.lower():
        ad_type_match = 50  # 产品页广告受限
    
    # 综合评分 (加权平均)
    overall_score = (visibility * 0.3 + (100 - ux_impact) * 0.3 + (100 - conversion_risk) * 0.25 + ad_type_match * 0.15)
    
    # 生成建议
    if overall_score >= 70:
        recommendation = "推荐放置广告"
    elif overall_score >= 50:
        recommendation = "可以放置广告，但需谨慎"
    else:
        recommendation = "不建议放置广告"
    
    return AdSlotScore(
        visibility=visibility,
        ux_impact=ux_impact,
        conversion_risk=conversion_risk,
        ad_type_match=ad_type_match,
        overall_score=overall_score,
        recommendation=recommendation,
    )


# ─── 广告异步加载 ─────────────────────────────────────────────────────

def analyze_ad_async_config(raw_data: dict) -> AdAsyncConfig:
    """分析广告异步加载配置"""
    content = raw_data.get("content", "")
    
    # 检查是否使用异步加载
    script_async = "async" in content.lower() or "defer" in content.lower()
    script_defer = "defer" in content.lower()
    lazy_loading = "lazy" in content.lower() or "loading=\"lazy\"" in content
    
    # 生成优化建议
    optimization_suggestions = []
    
    if not script_async:
        optimization_suggestions.append("将广告脚本设置为 async 或 defer，避免阻塞首屏")
    
    if not lazy_loading:
        optimization_suggestions.append("为广告图片添加 lazy loading，提升页面加载速度")
    
    optimization_suggestions.append("使用 Intersection Observer 实现广告可视性追踪")
    optimization_suggestions.append("将广告脚本放在页面底部或使用 async 加载")
    
    return AdAsyncConfig(
        script_async=script_async,
        script_defer=script_defer,
        lazy_loading=lazy_loading,
        preload_hints=[],
        optimization_suggestions=optimization_suggestions,
    )


# ─── 广告埋点 ─────────────────────────────────────────────────────────

def generate_ad_telemetry(slot_id: str = "ad-slot-1") -> AdTelemetry:
    """生成广告埋点配置"""
    
    tracking_code = """
<!-- Ad Telemetry Tracking Code -->
<script>
(function() {
    var slot = document.getElementById('%s');
    if (!slot) return;
    
    // 1. 曝光追踪 (Impression)
    var impressionObserver = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry) {
            if (entry.isIntersecting) {
                console.log('Ad impression:', '%s');
                impressionObserver.unobserve(entry.target);
            }
        });
    }, { threshold: 0.5 });
    impressionObserver.observe(slot);
    
    // 2. 点击追踪 (Click)
    slot.addEventListener('click', function() {
        console.log('Ad click:', '%s');
    });
    
    // 3. 可视性追踪 (Viewability)
    var viewabilityObserver = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry) {
            var ratio = entry.intersectionRatio;
            console.log('Ad viewability:', '%s', ratio);
        });
    }, { threshold: [0, 0.25, 0.5, 0.75, 1] });
    viewabilityObserver.observe(slot);
    
    // 4. 关闭追踪 (Close)
    var closeBtn = slot.querySelector('.ad-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', function() {
            console.log('Ad closed:', '%s');
        });
    }
    
    // 5. 页面停留追踪 (Page Dwell)
    var startTime = Date.now();
    window.addEventListener('beforeunload', function() {
        var dwellTime = (Date.now() - startTime) / 1000;
        console.log('Ad dwell time:', '%s', dwellTime);
    });
})();
</script>
""" % (slot_id, slot_id, slot_id, slot_id, slot_id, slot_id)
    
    return AdTelemetry(
        impression_tracking=True,
        click_tracking=True,
        viewability_tracking=True,
        close_tracking=True,
        page_dwell_tracking=True,
        conversion_tracking=False,
        tracking_code=tracking_code,
        events=["impression", "click", "viewability", "close", "dwell"],
    )


# ─── 广告开关 ─────────────────────────────────────────────────────────

def generate_ad_toggle_config(slot_id: str = "ad-slot-1") -> AdToggleConfig:
    """生成广告开关配置"""
    
    return AdToggleConfig(
        has_toggle=True,
        toggle_selector=f"#toggle-{slot_id}",
        frequency_capping=True,
        position_replacement=True,
        revenue_tracking=True,
        quick_disable=True,
    )


# ─── 政策适配检查 ─────────────────────────────────────────────────────

def check_ad_policy(raw_data: dict, platform: str = "general") -> PolicyCheck:
    """检查广告政策适配性"""
    issues = []
    recommendations = []
    
    content = raw_data.get("content", "")
    
    # 检查内容政策
    prohibited_content = ["gambling", "adult", "drugs", "weapons", "hate"]
    for keyword in prohibited_content:
        if keyword in content.lower():
            issues.append(f"包含禁止内容: {keyword}")
    
    # 检查广告密度
    if content.count("ad") > 5:
        issues.append("广告密度过高")
        recommendations.append("减少广告数量，提升用户体验")
    
    # 检查误导性内容
    misleading_keywords = ["free money", "guaranteed", "click here now"]
    for keyword in misleading_keywords:
        if keyword in content.lower():
            issues.append(f"可能包含误导性内容: {keyword}")
    
    # 确定合规级别
    if not issues:
        compliance_level = "compliant"
        risk_level = "low"
    elif len(issues) <= 2:
        compliance_level = "warning"
        risk_level = "medium"
    else:
        compliance_level = "violation"
        risk_level = "high"
    
    # 生成建议
    if compliance_level != "compliant":
        recommendations.append("移除或修改违规内容")
        recommendations.append("确保广告与内容明确区分")
        recommendations.append("添加广告标识 (Sponsored/Ad)")
    
    return PolicyCheck(
        platform=platform,
        compliance_level=compliance_level,
        issues=issues,
        recommendations=recommendations,
        risk_level=risk_level,
    )
