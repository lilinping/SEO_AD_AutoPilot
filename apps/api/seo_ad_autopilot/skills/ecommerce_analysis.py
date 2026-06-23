"""E-commerce Analysis skill - comprehensive product, listing, and conversion analysis.

Combines:
- Amazon Ads Report pattern (SP/SB/SD reporting)
- Product listing analysis (title, bullets, images, A+ content)
- Competitor pricing and positioning
- Conversion funnel analysis (CTA, checkout, cart abandonment)
- Platform recommendations (Amazon, Shopify, WooCommerce, etc.)
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from urllib.parse import urlparse

from .base import Skill, SkillCategory, SkillInput, SkillOutput, SkillRiskLevel


class EcommercePlatform(str, Enum):
    """E-commerce platform types."""
    AMAZON = "amazon"
    SHOPIFY = "shopify"
    WOOCOMMERCE = "woocommerce"
    MAGENTO = "magento"
    CUSTOM = "custom"


class AnalysisScope(str, Enum):
    """What to analyze."""
    FULL = "full"
    LISTING = "listing"
    PRICING = "pricing"
    CONVERSION = "conversion"
    COMPETITORS = "competitors"


@dataclass
class ProductListing:
    """Parsed product listing data."""
    title: str = ""
    bullets: list[str] = field(default_factory=list)
    description: str = ""
    price: Optional[str] = None
    original_price: Optional[str] = None
    images: list[str] = field(default_factory=list)
    rating: Optional[float] = None
    review_count: int = 0
    brand: str = ""
    category: str = ""
    asin: Optional[str] = None
    has_a_plus: bool = False
    has_video: bool = False
    has_variants: bool = False


@dataclass
class ConversionSignals:
    """Conversion-related signals from page analysis."""
    cta_count: int = 0
    cta_texts: list[str] = field(default_factory=list)
    cta_positions: list[str] = field(default_factory=list)
    has_add_to_cart: bool = False
    has_buy_now: bool = False
    has_checkout_flow: bool = False
    has_trust_badges: bool = False
    has_return_policy: bool = False
    has_free_shipping: bool = False
    has_urgency_signals: bool = False
    urgency_texts: list[str] = field(default_factory=list)
    social_proof_count: int = 0
    price_display: bool = False
    stock_indicator: Optional[str] = None


@dataclass
class CompetitorData:
    """Competitor information."""
    url: str = ""
    title: str = ""
    price: Optional[str] = None
    rating: Optional[float] = None
    review_count: int = 0
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)


@dataclass
class ListingScore:
    """Listing quality score breakdown."""
    title_score: float = 0.0
    bullet_score: float = 0.0
    description_score: float = 0.0
    image_score: float = 0.0
    a_plus_score: float = 0.0
    review_score: float = 0.0
    overall: float = 0.0


@dataclass
class ConversionScore:
    """Conversion optimization score."""
    cta_score: float = 0.0
    trust_score: float = 0.0
    urgency_score: float = 0.0
    social_proof_score: float = 0.0
    checkout_score: float = 0.0
    overall: float = 0.0


class EcommerceAnalysisSkill(Skill):
    """Comprehensive e-commerce analysis skill.
    
    Analyzes product listings, conversion funnels, competitor positioning,
    and provides actionable optimization recommendations for e-commerce sites.
    """

    @property
    def name(self) -> str:
        return "E-commerce Analysis"

    @property
    def description(self) -> str:
        return (
            "Analyze e-commerce product listings, conversion funnels, "
            "competitor positioning, and provide optimization recommendations. "
            "Supports Amazon, Shopify, WooCommerce, and custom platforms."
        )

    @property
    def category(self) -> SkillCategory:
        return SkillCategory.ECOMMERCE

    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.READ_ONLY

    def validate_input(self, skill_input: SkillInput) -> bool:
        params = skill_input.params
        return "url" in params or "html" in params or "product_data" in params

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Product page URL"},
                "html": {"type": "string", "description": "Raw HTML content of product page"},
                "product_data": {
                    "type": "object",
                    "description": "Pre-parsed product data (title, price, bullets, etc.)"
                },
                "scope": {
                    "type": "string",
                    "enum": ["full", "listing", "pricing", "conversion", "competitors"],
                    "default": "full",
                },
                "platform": {
                    "type": "string",
                    "enum": ["amazon", "shopify", "woocommerce", "magento", "custom", "auto"],
                    "default": "auto",
                },
                "competitors": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of competitor URLs to compare",
                },
                "target_market": {
                    "type": "string",
                    "default": "US",
                    "description": "Target market (US, EU, JP, CN, etc.)",
                },
            },
        }

    def get_output_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "platform": {"type": "string"},
                "listing_score": {"type": "object"},
                "conversion_score": {"type": "object"},
                "competitors": {"type": "array"},
                "recommendations": {"type": "array"},
                "quick_wins": {"type": "array"},
                "critical_issues": {"type": "array"},
            },
        }

    def execute(self, skill_input: SkillInput) -> SkillOutput:
        start_time = time.time()
        params = skill_input.params

        try:
            platform = self._detect_platform(params)
            scope = AnalysisScope(params.get("scope", "full"))
            product = self._parse_product(params)
            conversions = self._analyze_conversions(params)
            listing_score = self._score_listing(product, platform)
            conversion_score = self._score_conversion(conversions, platform)
            competitors = self._analyze_competitors(params.get("competitors", []))
            recommendations = self._generate_recommendations(
                product, conversions, listing_score, conversion_score, platform, competitors
            )
            quick_wins = self._extract_quick_wins(recommendations)
            critical_issues = self._extract_critical_issues(recommendations)

            elapsed_ms = int((time.time() - start_time) * 1000)

            result = {
                "platform": platform.value,
                "scope": scope.value,
                "product": {
                    "title": product.title,
                    "price": product.price,
                    "original_price": product.original_price,
                    "brand": product.brand,
                    "category": product.category,
                    "bullet_count": len(product.bullets),
                    "image_count": len(product.images),
                    "rating": product.rating,
                    "review_count": product.review_count,
                    "has_a_plus": product.has_a_plus,
                    "has_video": product.has_video,
                    "has_variants": product.has_variants,
                },
                "listing_score": {
                    "title": listing_score.title_score,
                    "bullets": listing_score.bullet_score,
                    "description": listing_score.description_score,
                    "images": listing_score.image_score,
                    "a_plus": listing_score.a_plus_score,
                    "reviews": listing_score.review_score,
                    "overall": listing_score.overall,
                },
                "conversion_score": {
                    "cta": conversion_score.cta_score,
                    "trust": conversion_score.trust_score,
                    "urgency": conversion_score.urgency_score,
                    "social_proof": conversion_score.social_proof_score,
                    "checkout": conversion_score.checkout_score,
                    "overall": conversion_score.overall,
                },
                "conversion_signals": {
                    "cta_count": conversions.cta_count,
                    "cta_texts": conversions.cta_texts,
                    "has_add_to_cart": conversions.has_add_to_cart,
                    "has_buy_now": conversions.has_buy_now,
                    "has_trust_badges": conversions.has_trust_badges,
                    "has_return_policy": conversions.has_return_policy,
                    "has_free_shipping": conversions.has_free_shipping,
                    "has_urgency_signals": conversions.has_urgency_signals,
                    "urgency_texts": conversions.urgency_texts,
                    "social_proof_count": conversions.social_proof_count,
                    "stock_indicator": conversions.stock_indicator,
                },
                "competitors": [
                    {
                        "url": c.url,
                        "title": c.title,
                        "price": c.price,
                        "rating": c.rating,
                        "review_count": c.review_count,
                        "strengths": c.strengths,
                        "weaknesses": c.weaknesses,
                    }
                    for c in competitors
                ],
                "recommendations": recommendations,
                "quick_wins": quick_wins,
                "critical_issues": critical_issues,
                "summary": {
                    "total_recommendations": len(recommendations),
                    "quick_wins_count": len(quick_wins),
                    "critical_issues_count": len(critical_issues),
                    "listing_grade": self._grade(listing_score.overall),
                    "conversion_grade": self._grade(conversion_score.overall),
                },
            }

            return self._create_output(
                success=True,
                result=result,
                execution_time_ms=elapsed_ms,
            )

        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            return self._create_output(
                success=False,
                error=str(e),
                execution_time_ms=elapsed_ms,
            )

    def _detect_platform(self, params: dict[str, Any]) -> EcommercePlatform:
        """Auto-detect e-commerce platform from URL or HTML."""
        explicit = params.get("platform", "auto")
        if explicit != "auto":
            try:
                return EcommercePlatform(explicit)
            except ValueError:
                pass

        url = params.get("url", "")
        html = params.get("html", "")

        if url:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if "amazon" in domain:
                return EcommercePlatform.AMAZON
            if "myshopify.com" in domain or "shopify" in domain:
                return EcommercePlatform.SHOPIFY

        if html:
            lower = html.lower()
            if "amazon" in lower or "asin" in lower:
                return EcommercePlatform.AMAZON
            if "shopify" in lower or "Shopify.theme" in html:
                return EcommercePlatform.SHOPIFY
            if "woocommerce" in lower:
                return EcommercePlatform.WOOCOMMERCE
            if "magento" in lower:
                return EcommercePlatform.MAGENTO

        if url:
            parsed = urlparse(url)
            if "/cart" in parsed.path or "shopify" in url:
                return EcommercePlatform.SHOPIFY

        return EcommercePlatform.CUSTOM

    def _parse_product(self, params: dict[str, Any]) -> ProductListing:
        """Parse product data from params or HTML."""
        if "product_data" in params:
            pd = params["product_data"]
            return ProductListing(
                title=pd.get("title", ""),
                bullets=pd.get("bullets", []),
                description=pd.get("description", ""),
                price=pd.get("price"),
                original_price=pd.get("original_price"),
                images=pd.get("images", []),
                rating=pd.get("rating"),
                review_count=pd.get("review_count", 0),
                brand=pd.get("brand", ""),
                category=pd.get("category", ""),
                asin=pd.get("asin"),
                has_a_plus=pd.get("has_a_plus", False),
                has_video=pd.get("has_video", False),
                has_variants=pd.get("has_variants", False),
            )

        html = params.get("html", "")
        if not html:
            return ProductListing()

        product = ProductListing()

        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        if title_match:
            product.title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()

        bullet_matches = re.findall(
            r'<li[^>]*class="[^"]*a-list-item[^"]*"[^>]*>(.*?)</li>',
            html, re.IGNORECASE | re.DOTALL
        )
        if not bullet_matches:
            bullet_matches = re.findall(
                r'<span[^>]*class="[^"]*a-list-item[^"]*"[^>]*>(.*?)</span>',
                html, re.IGNORECASE | re.DOTALL
            )
        product.bullets = [re.sub(r'<[^>]+>', '', b).strip() for b in bullet_matches if b.strip()]

        price_match = re.search(r'class="[^"]*a-price-whole[^"]*"[^>]*>([\d,]+)', html)
        if price_match:
            product.price = price_match.group(1).replace(",", "")
        else:
            price_match = re.search(r'\$([0-9]+\.?[0-9]*)', html)
            if price_match:
                product.price = price_match.group(1)

        img_matches = re.findall(r'<img[^>]*src="([^"]*)"[^>]*>', html)
        product.images = [img for img in img_matches if ("media-amazon" in img or "image" in img.lower())]

        rating_match = re.search(r'(\d\.?\d?)\s*out of\s*5', html)
        if rating_match:
            try:
                product.rating = float(rating_match.group(1))
            except ValueError:
                pass

        review_match = re.search(r'([\d,]+)\s*(?:ratings|reviews)', html, re.IGNORECASE)
        if review_match:
            try:
                product.review_count = int(review_match.group(1).replace(",", ""))
            except ValueError:
                pass

        if "aplus" in html.lower() or "a-plus" in html.lower():
            product.has_a_plus = True
        if "video" in html.lower() and ("player" in html.lower() or "autoplay" in html.lower()):
            product.has_video = True

        return product

    def _analyze_conversions(self, params: dict[str, Any]) -> ConversionSignals:
        """Analyze conversion signals from HTML or product data."""
        html = params.get("html", "")
        if not html:
            signals = ConversionSignals()
            if params.get("product_data"):
                pd = params["product_data"]
                if pd.get("has_add_to_cart"):
                    signals.has_add_to_cart = True
                if pd.get("has_buy_now"):
                    signals.has_buy_now = True
            return signals

        signals = ConversionSignals()
        lower = html.lower()

        cta_patterns = [
            r'add\s*to\s*cart', r'buy\s*now', r'add\s*to\s*basket',
            r'place\s*order', r'checkout', r'purchase', r'order\s*now',
            r'shop\s*now', r'get\s*it\s*now', r'grab\s*this\s*deal',
        ]
        for pat in cta_patterns:
            matches = re.findall(pat, lower)
            signals.cta_count += len(matches)
            if matches:
                signals.cta_texts.extend(matches[:3])

        signals.has_add_to_cart = bool(re.search(r'add.?to.?cart', lower))
        signals.has_buy_now = bool(re.search(r'buy.?now|one.?click', lower))
        signals.has_checkout_flow = bool(re.search(r'checkout|payment|billing', lower))

        trust_patterns = [r'trust', r'secure', r'ssl', r'safe\s*checkout', r'verified', r'guarantee']
        for pat in trust_patterns:
            if re.search(pat, lower):
                signals.has_trust_badges = True
                break

        signals.has_return_policy = bool(re.search(r'return|refund|money.?back', lower))
        signals.has_free_shipping = bool(re.search(r'free\s*shipping|free\s*delivery', lower))

        urgency_patterns = [
            r'limited\s*time', r'only\s*\d+\s*left', r'last\s*(?:chance|day|hours)',
            r'selling\s*fast', r'low\s*stock', r'ends?\s*(?:today|soon|tonight)',
            r'\d+\s*(?:people|customers?)\s*(?:are\s*)?viewing', r'don.t\s*miss',
        ]
        for pat in urgency_patterns:
            match = re.search(pat, lower)
            if match:
                signals.has_urgency_signals = True
                signals.urgency_texts.append(match.group(0))

        social_patterns = [
            r'([\d,]+)\s*(?:reviews?|ratings?|sold)',
            r'([\d,]+)\s*customers?',
        ]
        for pat in social_patterns:
            match = re.search(pat, lower)
            if match:
                try:
                    count = int(match.group(1).replace(",", ""))
                    signals.social_proof_count = max(signals.social_proof_count, count)
                except ValueError:
                    pass

        if re.search(r'in\s*stock|out\s*of\s*stock|only\s*\d+\s*available', lower):
            if "out of stock" in lower:
                signals.stock_indicator = "out_of_stock"
            else:
                signals.stock_indicator = "in_stock"

        return signals

    def _score_listing(self, product: ProductListing, platform: EcommercePlatform) -> ListingScore:
        """Score product listing quality."""
        score = ListingScore()

        if product.title:
            title_len = len(product.title)
            if platform == EcommercePlatform.AMAZON:
                if 80 <= title_len <= 200:
                    score.title_score = 100.0
                elif 50 <= title_len <= 250:
                    score.title_score = 75.0
                elif title_len > 0:
                    score.title_score = 50.0
            else:
                if 30 <= title_len <= 150:
                    score.title_score = 100.0
                elif title_len > 0:
                    score.title_score = 70.0

        bullet_count = len(product.bullets)
        if platform == EcommercePlatform.AMAZON:
            if bullet_count >= 5:
                score.bullet_score = 100.0
            elif bullet_count >= 3:
                score.bullet_score = 70.0
            elif bullet_count > 0:
                score.bullet_score = 40.0
        else:
            if bullet_count >= 3:
                score.bullet_score = 100.0
            elif bullet_count > 0:
                score.bullet_score = 60.0

        desc_len = len(product.description)
        if desc_len >= 500:
            score.description_score = 100.0
        elif desc_len >= 200:
            score.description_score = 75.0
        elif desc_len > 0:
            score.description_score = 50.0

        img_count = len(product.images)
        if img_count >= 7:
            score.image_score = 100.0
        elif img_count >= 4:
            score.image_score = 80.0
        elif img_count >= 2:
            score.image_score = 60.0
        elif img_count == 1:
            score.image_score = 30.0

        if product.has_a_plus:
            score.a_plus_score = 100.0
        elif product.has_video:
            score.a_plus_score = 60.0

        if product.review_count >= 100:
            score.review_score = 100.0
        elif product.review_count >= 20:
            score.review_score = 75.0
        elif product.review_count >= 5:
            score.review_score = 50.0
        elif product.review_count > 0:
            score.review_score = 25.0

        weights = [0.25, 0.20, 0.15, 0.20, 0.10, 0.10]
        scores = [
            score.title_score, score.bullet_score, score.description_score,
            score.image_score, score.a_plus_score, score.review_score,
        ]
        score.overall = sum(w * s for w, s in zip(weights, scores))

        return score

    def _score_conversion(self, signals: ConversionSignals, platform: EcommercePlatform) -> ConversionScore:
        """Score conversion optimization."""
        score = ConversionScore()

        cta_pts = 0.0
        if signals.has_add_to_cart:
            cta_pts += 40.0
        if signals.has_buy_now:
            cta_pts += 30.0
        if signals.cta_count >= 2:
            cta_pts += 30.0
        elif signals.cta_count >= 1:
            cta_pts += 15.0
        score.cta_score = min(cta_pts, 100.0)

        trust_pts = 0.0
        if signals.has_trust_badges:
            trust_pts += 40.0
        if signals.has_return_policy:
            trust_pts += 30.0
        if signals.has_free_shipping:
            trust_pts += 30.0
        score.trust_score = min(trust_pts, 100.0)

        urgency_pts = 0.0
        if signals.has_urgency_signals:
            urgency_pts += 50.0
        if len(signals.urgency_texts) >= 2:
            urgency_pts += 30.0
        if signals.stock_indicator and signals.stock_indicator != "out_of_stock":
            urgency_pts += 20.0
        score.urgency_score = min(urgency_pts, 100.0)

        if signals.social_proof_count >= 100:
            score.social_proof_score = 100.0
        elif signals.social_proof_count >= 20:
            score.social_proof_score = 75.0
        elif signals.social_proof_count > 0:
            score.social_proof_score = 50.0

        checkout_pts = 0.0
        if signals.has_checkout_flow:
            checkout_pts += 50.0
        if signals.has_add_to_cart and signals.has_buy_now:
            checkout_pts += 30.0
        if signals.price_display:
            checkout_pts += 20.0
        score.checkout_score = min(checkout_pts, 100.0)

        weights = [0.30, 0.25, 0.15, 0.15, 0.15]
        scores = [
            score.cta_score, score.trust_score, score.urgency_score,
            score.social_proof_score, score.checkout_score,
        ]
        score.overall = sum(w * s for w, s in zip(weights, scores))

        return score

    def _analyze_competitors(self, competitor_urls: list[str]) -> list[CompetitorData]:
        """Analyze competitor data from provided URLs."""
        competitors = []
        for url in competitor_urls:
            if not url:
                continue
            competitors.append(CompetitorData(
                url=url,
                title="",
                strengths=["Requires live crawl to analyze"],
                weaknesses=["Data not yet available"],
            ))
        return competitors

    def _generate_recommendations(
        self,
        product: ProductListing,
        conversions: ConversionSignals,
        listing_score: ListingScore,
        conversion_score: ConversionScore,
        platform: EcommercePlatform,
        competitors: list[CompetitorData],
    ) -> list[dict[str, Any]]:
        """Generate actionable recommendations."""
        recs = []
        priority = 1

        if listing_score.title_score < 75:
            if platform == EcommercePlatform.AMAZON:
                recs.append({
                    "priority": priority,
                    "category": "listing",
                    "title": "优化产品标题",
                    "description": (
                        f"当前标题长度 {len(product.title)} 字符。"
                        "Amazon 建议标题 80-200 字符，包含品牌名、核心关键词、产品特性、规格。"
                        "使用「品牌 + 核心关键词 + 关键特性 + 规格」格式。"
                    ),
                    "impact": "high",
                    "effort": "low",
                })
            else:
                recs.append({
                    "priority": priority,
                    "category": "listing",
                    "title": "优化页面标题",
                    "description": "标题应在 30-60 字符之间，包含主要关键词，吸引点击。",
                    "impact": "high",
                    "effort": "low",
                })
            priority += 1

        if len(product.bullets) < 5 and platform == EcommercePlatform.AMAZON:
            recs.append({
                "priority": priority,
                "category": "listing",
                "title": "补充 Bullet Points",
                "description": (
                    f"当前 {len(product.bullets)} 个 Bullet Points。"
                    "Amazon 允许 5 个 Bullet Points，每个 100-200 字符。"
                    "每个 bullet 聚焦一个卖点，首字母大写关键词。"
                ),
                "impact": "high",
                "effort": "low",
            })
            priority += 1

        if len(product.images) < 5:
            recs.append({
                "priority": priority,
                "category": "listing",
                "title": "增加产品图片",
                "description": (
                    f"当前 {len(product.images)} 张图片。"
                    "建议至少 7 张：主图、细节图、尺寸图、使用场景图、包装图。"
                    "主图白底，其他图片可包含生活场景和卖点标注。"
                ),
                "impact": "high",
                "effort": "medium",
            })
            priority += 1

        if not product.has_a_plus and platform == EcommercePlatform.AMAZON:
            recs.append({
                "priority": priority,
                "category": "listing",
                "title": "创建 A+ Content / 品牌故事",
                "description": (
                    "A+ Content 可提升转化率 5-10%。"
                    "使用图文混排模块展示品牌故事、产品对比、细节特写。"
                    "品牌注册后即可使用。"
                ),
                "impact": "high",
                "effort": "medium",
            })
            priority += 1

        if not product.has_video:
            recs.append({
                "priority": priority,
                "category": "listing",
                "title": "添加产品视频",
                "description": (
                    "产品视频可提升转化率 20-30%。"
                    "包含：产品开箱、功能演示、使用场景、对比测试。"
                    "时长 30-60 秒为佳。"
                ),
                "impact": "high",
                "effort": "medium",
            })
            priority += 1

        if not conversions.has_add_to_cart:
            recs.append({
                "priority": priority,
                "category": "conversion",
                "title": "添加 Add to Cart 按钮",
                "description": "缺少 Add to Cart 是转化率最大的杀手。确保按钮显眼、颜色突出、位置固定。",
                "impact": "critical",
                "effort": "low",
            })
            priority += 1

        if not conversions.has_trust_badges:
            recs.append({
                "priority": priority,
                "category": "conversion",
                "title": "添加信任标识",
                "description": (
                    "添加 SSL 安全标识、支付图标、信任徽章。"
                    "可提升转化率 10-15%。"
                ),
                "impact": "high",
                "effort": "low",
            })
            priority += 1

        if not conversions.has_free_shipping:
            recs.append({
                "priority": priority,
                "category": "conversion",
                "title": "提供免运费选项",
                "description": "免运费是影响购买决策的 top-3 因素。即使提高商品价格 5-10% 来覆盖运费也值得。",
                "impact": "high",
                "effort": "medium",
            })
            priority += 1

        if not conversions.has_return_policy:
            recs.append({
                "priority": priority,
                "category": "conversion",
                "title": "展示退货政策",
                "description": "清晰的退货政策可降低购买犹豫。在产品页和结账页展示 30 天退货保证。",
                "impact": "medium",
                "effort": "low",
            })
            priority += 1

        if not conversions.has_urgency_signals:
            recs.append({
                "priority": priority,
                "category": "conversion",
                "title": "添加紧迫感元素",
                "description": (
                    "限时折扣、库存提示、倒计时等紧迫感元素可提升转化 5-10%。"
                    "注意：不能误导用户。"
                ),
                "impact": "medium",
                "effort": "low",
            })
            priority += 1

        if conversion_score.social_proof_score < 50:
            recs.append({
                "priority": priority,
                "category": "conversion",
                "title": "增强社会认证",
                "description": (
                    f"当前社会认证数据：{conversions.social_proof_count} 条。"
                    "添加客户评价、销量数据、用户照片、网红推荐等社会认证元素。"
                ),
                "impact": "medium",
                "effort": "medium",
            })
            priority += 1

        if listing_score.bullet_score < 75 and platform == EcommercePlatform.AMAZON:
            recs.append({
                "priority": priority,
                "category": "seo",
                "title": "优化 Bullet Points 关键词",
                "description": "每个 Bullet Point 首行使用大写关键词短语，自然融入长尾关键词。",
                "impact": "high",
                "effort": "low",
            })
            priority += 1

        if platform == EcommercePlatform.AMAZON:
            recs.append({
                "priority": priority,
                "category": "ads",
                "title": "启用 Amazon Sponsored Products 广告",
                "description": (
                    "使用自动广告跑词 2 周 → 筛选高转化词 → 开启手动精准广告。"
                    "ACoS 目标 < 25%。"
                ),
                "impact": "high",
                "effort": "medium",
            })
            priority += 1

        if len(competitors) > 0:
            recs.append({
                "priority": priority,
                "category": "competitive",
                "title": "竞品差异化定位",
                "description": "分析竞品的定价、评价、卖点差异，找到差异化切入点。",
                "impact": "medium",
                "effort": "medium",
            })
            priority += 1

        recs.sort(key=lambda r: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(r.get("impact", "low"), 3))

        for i, rec in enumerate(recs, 1):
            rec["priority"] = i

        return recs

    def _extract_quick_wins(self, recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Extract quick wins (high impact + low effort)."""
        return [
            r for r in recommendations
            if r.get("effort") == "low" and r.get("impact") in ("high", "critical")
        ]

    def _extract_critical_issues(self, recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Extract critical issues."""
        return [r for r in recommendations if r.get("impact") == "critical"]

    def _grade(self, score: float) -> str:
        """Convert numeric score to letter grade."""
        if score >= 90:
            return "A+"
        if score >= 80:
            return "A"
        if score >= 70:
            return "B+"
        if score >= 60:
            return "B"
        if score >= 50:
            return "C+"
        if score >= 40:
            return "C"
        if score >= 30:
            return "D"
        return "F"
