from __future__ import annotations

from .models import SeedSite, SiteIntake


DEMO_SITES: list[SeedSite] = [
    SeedSite(
        name="Aurora Shop",
        intake=SiteIntake(
            url="https://aurora-shop.example",
            site_name="Aurora Shop",
            repo_url="https://github.com/example/aurora-shop",
            sitemap_urls=["/sitemap.xml"],
            keywords=["winter jackets", "outdoor gear", "membrane shell"],
            brand_whitelist=["Aurora"],
            competitors=["northpeak", "snowtrail"],
            language="en",
            locale="en-US",
            notes="ecommerce storefront with script-safe checkout path",
        ),
    ),
    SeedSite(
        name="Northstar Media",
        intake=SiteIntake(
            url="https://northstar-media.example",
            site_name="Northstar Media",
            repo_url="https://github.com/example/northstar-media",
            sitemap_urls=["/sitemap.xml", "/news-sitemap.xml"],
            keywords=["industry insights", "growth signals", "editorial brief"],
            brand_whitelist=["Northstar"],
            competitors=["dailybrief", "signalroom"],
            language="en",
            locale="en-US",
            notes="content publisher focused on deep briefings and snippets",
        ),
    ),
    SeedSite(
        name="LedgerFlow",
        intake=SiteIntake(
            url="https://ledgerflow.example",
            site_name="LedgerFlow",
            cms_name="webflow",
            sitemap_urls=["/sitemap.xml"],
            keywords=["budget tracker", "cash flow", "monthly plan"],
            brand_whitelist=["LedgerFlow"],
            competitors=["finpilot", "budgetwise"],
            language="en",
            locale="en-US",
            notes="saas landing page with pricing and use cases",
        ),
    ),
    SeedSite(
        name="Pixel Notes",
        intake=SiteIntake(
            url="https://pixel-notes.example",
            site_name="Pixel Notes",
            cms_name="contentful",
            sitemap_urls=["/sitemap.xml"],
            keywords=["note taking", "knowledge base", "task memory"],
            brand_whitelist=["Pixel Notes"],
            competitors=["noteforge", "memolane"],
            language="en",
            locale="en-US",
            notes="tool site requiring preview-first growth modules",
        ),
    ),
    SeedSite(
        name="Greenhouse Recipes",
        intake=SiteIntake(
            url="https://greenhouse-recipes.example",
            site_name="Greenhouse Recipes",
            repo_url="https://github.com/example/greenhouse-recipes",
            sitemap_urls=["/sitemap.xml"],
            keywords=["seasonal meals", "meal planning", "family recipes"],
            brand_whitelist=["Greenhouse"],
            competitors=["pantrynote", "kitchenloop"],
            language="en",
            locale="en-US",
            notes="content site with article clusters and FAQ opportunities",
        ),
    ),
    SeedSite(
        name="Peak Supplies",
        intake=SiteIntake(
            url="https://peak-supplies.example",
            site_name="Peak Supplies",
            repo_url="https://github.com/example/peak-supplies",
            sitemap_urls=["/sitemap.xml"],
            keywords=["camping stove", "trail kit", "gear bundle"],
            brand_whitelist=["Peak"],
            competitors=["ridgebox", "summitkit"],
            language="en",
            locale="en-US",
            notes="commerce catalog with product detail and collection pages",
        ),
    ),
    SeedSite(
        name="StudyCraft",
        intake=SiteIntake(
            url="https://studycraft.example",
            site_name="StudyCraft",
            cms_name="sanity",
            sitemap_urls=["/sitemap.xml"],
            keywords=["study planner", "student workflow", "focus sprint"],
            brand_whitelist=["StudyCraft"],
            competitors=["learnflow", "noteforge"],
            language="en",
            locale="en-US",
            notes="product-led saas with comparison and pricing pages",
        ),
    ),
    SeedSite(
        name="Retro Gear",
        intake=SiteIntake(
            url="https://retro-gear.example",
            site_name="Retro Gear",
            repo_url="https://github.com/example/retro-gear",
            sitemap_urls=["/sitemap.xml"],
            keywords=["vintage headphones", "audio gear", "retro electronics"],
            brand_whitelist=["Retro"],
            competitors=["oldsound", "vibeaudio"],
            language="en",
            locale="en-US",
            notes="ecommerce with product schema and collection filters",
        ),
    ),
    SeedSite(
        name="Trust Clinic",
        intake=SiteIntake(
            url="https://trust-clinic.example",
            site_name="Trust Clinic",
            cms_name="drupal",
            sitemap_urls=["/sitemap.xml"],
            keywords=["medical guidance", "patient resources", "clinic reviews"],
            brand_whitelist=[],
            competitors=["careline", "healthvault"],
            language="en",
            locale="en-US",
            notes="ymyl site where ad inventory should not be recommended",
        ),
        auto_run=True,
    ),
    SeedSite(
        name="North Forge Tools",
        intake=SiteIntake(
            url="https://northforge-tools.example",
            site_name="North Forge Tools",
            cms_name="ghost",
            sitemap_urls=["/sitemap.xml"],
            keywords=["workflow generator", "template builder", "tooling"],
            brand_whitelist=["North Forge"],
            competitors=["taskfoundry", "tooltrace"],
            language="en",
            locale="en-US",
            notes="utility product with script-safe preview and monitoring",
        ),
    ),
]


def seed_sites() -> list[SeedSite]:
    return DEMO_SITES


if __name__ == "__main__":
    from .service import WorkflowService

    service = WorkflowService()
    service.bootstrap()
    print(f"Seeded {len(DEMO_SITES)} demo sites.")
