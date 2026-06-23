"""Industry Templates - 行业模板系统.

Inspired by BettaFish's report templates:
- E-commerce templates
- Content/Blog templates
- Tool/Utility templates
- SaaS templates
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class IndustryType(str, Enum):
    """Industry types."""
    ECOMMERCE = "ecommerce"
    CONTENT = "content"
    SAAS = "saas"
    TOOL = "tool"
    LOCAL = "local"
    MEDIA = "media"


@dataclass
class TemplateComponent:
    """A template component."""
    component_id: str
    name: str
    description: str
    html_template: str
    css_styles: str = ""
    position: str = "body"
    priority: int = 0


@dataclass
class IndustryTemplate:
    """An industry template."""
    template_id: str
    industry: IndustryType
    name: str
    description: str
    components: list[TemplateComponent] = field(default_factory=list)
    seo_rules: dict[str, Any] = field(default_factory=dict)
    ad_rules: dict[str, Any] = field(default_factory=dict)


class TemplateRegistry:
    """Registry of industry templates."""
    
    def __init__(self):
        self._templates: dict[str, IndustryTemplate] = {}
        self._initialize_default_templates()
    
    def _initialize_default_templates(self) -> None:
        """Initialize default industry templates."""
        # E-commerce template
        self.register_template(IndustryTemplate(
            template_id="ecommerce_default",
            industry=IndustryType.ECOMMERCE,
            name="E-commerce Default",
            description="Default template for e-commerce sites",
            components=[
                TemplateComponent(
                    component_id="product_schema",
                    name="Product Schema",
                    description="Product structured data",
                    html_template='<script type="application/ld+json">{"@type": "Product"}</script>',
                    priority=10,
                ),
                TemplateComponent(
                    component_id="faq_section",
                    name="FAQ Section",
                    description="Product FAQ section",
                    html_template='<div class="faq-section"><h2>FAQ</h2></div>',
                    priority=8,
                ),
                TemplateComponent(
                    component_id="related_products",
                    name="Related Products",
                    description="Related product recommendations",
                    html_template='<div class="related-products"><h2>Related Products</h2></div>',
                    priority=7,
                ),
            ],
            seo_rules={
                "require_product_schema": True,
                "require_price_schema": True,
                "max_title_length": 70,
            },
            ad_rules={
                "allowed_positions": ["below_content", "sidebar"],
                "max_ads_per_page": 3,
                "exclude_cart_page": True,
            },
        ))
        
        # Content/Blog template
        self.register_template(IndustryTemplate(
            template_id="content_default",
            industry=IndustryType.CONTENT,
            name="Content Site Default",
            description="Default template for content/blog sites",
            components=[
                TemplateComponent(
                    component_id="article_schema",
                    name="Article Schema",
                    description="Article structured data",
                    html_template='<script type="application/ld+json">{"@type": "Article"}</script>',
                    priority=10,
                ),
                TemplateComponent(
                    component_id="author_bio",
                    name="Author Bio",
                    description="Author biography section",
                    html_template='<div class="author-bio"><h3>About the Author</h3></div>',
                    priority=8,
                ),
                TemplateComponent(
                    component_id="related_articles",
                    name="Related Articles",
                    description="Related article recommendations",
                    html_template='<div class="related-articles"><h2>Related Articles</h2></div>',
                    priority=7,
                ),
                TemplateComponent(
                    component_id="newsletter_signup",
                    name="Newsletter Signup",
                    description="Email newsletter subscription",
                    html_template='<div class="newsletter"><h3>Subscribe to our newsletter</h3></div>',
                    priority=6,
                ),
            ],
            seo_rules={
                "require_article_schema": True,
                "require_author_schema": True,
                "max_title_length": 60,
            },
            ad_rules={
                "allowed_positions": ["in_article", "below_content", "sidebar"],
                "max_ads_per_page": 5,
                "require_sponsored_label": True,
            },
        ))
        
        # SaaS template
        self.register_template(IndustryTemplate(
            template_id="saas_default",
            industry=IndustryType.SAAS,
            name="SaaS Default",
            description="Default template for SaaS sites",
            components=[
                TemplateComponent(
                    component_id="product_schema",
                    name="SoftwareApplication Schema",
                    description="Software application structured data",
                    html_template='<script type="application/ld+json">{"@type": "SoftwareApplication"}</script>',
                    priority=10,
                ),
                TemplateComponent(
                    component_id="feature_comparison",
                    name="Feature Comparison",
                    description="Feature comparison table",
                    html_template='<div class="feature-comparison"><h2>Features</h2></div>',
                    priority=8,
                ),
                TemplateComponent(
                    component_id="pricing_faq",
                    name="Pricing FAQ",
                    description="Pricing and billing FAQ",
                    html_template='<div class="pricing-faq"><h2>Pricing FAQ</h2></div>',
                    priority=7,
                ),
            ],
            seo_rules={
                "require_software_schema": True,
                "require_faq_schema": True,
            },
            ad_rules={
                "allowed_positions": ["blog_only"],
                "max_ads_per_page": 2,
            },
        ))
        
        # Tool/Utility template
        self.register_template(IndustryTemplate(
            template_id="tool_default",
            industry=IndustryType.TOOL,
            name="Tool Site Default",
            description="Default template for tool/utility sites",
            components=[
                TemplateComponent(
                    component_id="howto_schema",
                    name="HowTo Schema",
                    description="How-to structured data",
                    html_template='<script type="application/ld+json">{"@type": "HowTo"}</script>',
                    priority=10,
                ),
                TemplateComponent(
                    component_id="usage_guide",
                    name="Usage Guide",
                    description="Tool usage guide",
                    html_template='<div class="usage-guide"><h2>How to Use</h2></div>',
                    priority=8,
                ),
            ],
            seo_rules={
                "require_howto_schema": True,
                "require_faq_schema": True,
            },
            ad_rules={
                "allowed_positions": ["below_content"],
                "max_ads_per_page": 2,
            },
        ))
    
    def register_template(self, template: IndustryTemplate) -> None:
        """Register a template."""
        self._templates[template.template_id] = template
    
    def get_template(self, template_id: str) -> Optional[IndustryTemplate]:
        """Get a template by ID."""
        return self._templates.get(template_id)
    
    def get_templates_by_industry(self, industry: IndustryType) -> list[IndustryTemplate]:
        """Get templates by industry."""
        return [t for t in self._templates.values() if t.industry == industry]
    
    def get_all_templates(self) -> list[IndustryTemplate]:
        """Get all templates."""
        return list(self._templates.values())
    
    def get_template_for_site(self, site_type: str) -> Optional[IndustryTemplate]:
        """Get the best template for a site type."""
        type_mapping = {
            "ecommerce": IndustryType.ECOMMERCE,
            "shop": IndustryType.ECOMMERCE,
            "store": IndustryType.ECOMMERCE,
            "blog": IndustryType.CONTENT,
            "news": IndustryType.CONTENT,
            "content": IndustryType.CONTENT,
            "saas": IndustryType.SAAS,
            "tool": IndustryType.TOOL,
            "calculator": IndustryType.TOOL,
        }
        
        industry = type_to_industry.get(site_type, IndustryType.CONTENT)
        return self.get_template_by_industry(industry)
    
    def get_template_by_industry(self, industry: IndustryType) -> Optional[IndustryTemplate]:
        """Get template by industry type."""
        for template in self._templates.values():
            if template.industry == industry:
                return template
        return None
    
    def get_template(self, template_id: str) -> Optional[IndustryTemplate]:
        """Get template by ID."""
        return self._templates.get(template_id)
    
    def get_all_templates(self) -> list[IndustryTemplate]:
        """Get all templates."""
        return list(self._templates.values())


def create_template_registry() -> TemplateRegistry:
    """Create a template registry with default templates."""
    return TemplateRegistry()
