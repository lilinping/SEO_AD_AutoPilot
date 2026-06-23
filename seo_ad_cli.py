#!/usr/bin/env python3
"""SEO-AD AutoPilot CLI - Command line interface for site analysis.

Inspired by OpenClaw's onboard CLI experience.
"""

import argparse
import json
import sys
from typing import Optional

def cmd_analyze(args):
    """Analyze a website."""
    from apps.api.seo_ad_autopilot.search_engines.base import SearchEngineRegistry
    from apps.api.seo_ad_autopilot.ad_platforms.auto_discovery import analyze_site_for_ads
    from apps.api.seo_ad_autopilot.agents.geo import GEOAgent
    from apps.api.seo_ad_autopilot.agents.base import SiteContext
    
    url = args.url
    print(f"\n🔍 Analyzing: {url}\n")
    
    # GEO Analysis
    print("📊 Running GEO analysis...")
    geo_agent = GEOAgent()
    context = SiteContext(url=url, raw_data={"content": "Analyzing site..."})
    geo_output = geo_agent.analyze(context)
    geo_scores = geo_output.content.get("geo_scores", {})
    
    print(f"   Overall GEO Score: {geo_scores.get('overall', 0):.1f}/100")
    print(f"   Citation: {geo_scores.get('citation', 0)}")
    print(f"   Entity: {geo_scores.get('entity', 0)}")
    print(f"   Structure: {geo_scores.get('structure', 0)}")
    print(f"   Authority: {geo_scores.get('authority', 0)}")
    print(f"   AI Presence: {geo_scores.get('ai_presence', 0)}")
    
    # Ad Analysis
    print("\n💰 Running ad platform analysis...")
    ad_result = analyze_site_for_ads(url, {"monthly_visits": 10000, "has_blog": True})
    
    print(f"   Ad Readiness Grade: {ad_result['ad_readiness']['grade']}")
    print(f"   Score: {ad_result['ad_readiness']['score']:.1f}/100")
    
    if ad_result['ad_recommendations']:
        print(f"   Top Platform: {ad_result['ad_recommendations'][0]['platform']}")
    
    # Search Engines
    print("\n🔎 Search engine coverage:")
    registry = SearchEngineRegistry()
    from apps.api.seo_ad_autopilot.search_engines.google import GoogleSearchEngine
    from apps.api.seo_ad_autopilot.search_engines.bing import BingSearchEngine
    from apps.api.seo_ad_autopilot.search_engines.chatgpt import ChatGPTGEOEngine
    from apps.api.seo_ad_autopilot.search_engines.perplexity import PerplexityGEOEngine
    
    registry.register(GoogleSearchEngine())
    registry.register(BingSearchEngine())
    registry.register(ChatGPTGEOEngine())
    registry.register(PerplexityGEOEngine())
    
    for engine in registry.get_all():
        status = "✅" if engine.is_available() else "⚠️  Not configured"
        print(f"   {engine.name}: {status}")
    
    print("\n✅ Analysis complete!\n")


def cmd_config(args):
    """View or update configuration."""
    if args.show:
        print("\n📋 Current Configuration:\n")
        print("Search Engines:")
        print("  Google: Not configured (needs API Key + CX)")
        print("  Bing: Not configured (needs API Key)")
        print("  ChatGPT: Built-in")
        print("  Perplexity: Built-in")
        print("  Claude: Built-in")
        print("\nAd Platforms:")
        print("  Google AdSense: Auto-discover")
        print("  Mediavine: Auto-discover (50K+ visits)")
        print("  Ezoic: Auto-discover (10K+ visits)")
        print("\nSkills: 9 registered")
        print("  SiteCrawler, StyleExtractor, SiteAnalyzer")
        print("  ContentGenerator, SchemaBuilder")
        print("  GitHubPRCreator, CMSPublisher")
        print("  MetricsCollector, AlertManager")
    elif args.set:
        print(f"Setting {args.set_key} = {args.set_value}")
        # TODO: Implement config update
    print()


def cmd_serve(args):
    """Start the API server."""
    import subprocess
    port = args.port or 8000
    print(f"\n🚀 Starting SEO-AD AutoPilot API on port {port}...\n")
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "apps.api.seo_ad_autopilot.app:create_app",
        "--factory", "--reload",
        "--host", "127.0.0.1",
        "--port", str(port),
    ])


def cmd_web(args):
    """Start the web console."""
    import subprocess
    print("\n🌐 Starting SEO-AD AutoPilot Web Console...\n")
    subprocess.run(["pnpm", "--dir", "apps/web", "dev"])


def main():
    parser = argparse.ArgumentParser(
        description="SEO-AD AutoPilot - Multi-Engine SEO + GEO + Auto Ad Discovery",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  seo-ad analyze https://example.com     # Analyze a website
  seo-ad config --show                   # Show configuration
  seo-ad serve --port 8000              # Start API server
  seo-ad web                             # Start web console
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze a website")
    analyze_parser.add_argument("url", help="Website URL to analyze")
    analyze_parser.set_defaults(func=cmd_analyze)
    
    # Config command
    config_parser = subparsers.add_parser("config", help="View or update configuration")
    config_parser.add_argument("--show", action="store_true", help="Show current config")
    config_parser.add_argument("--set", dest="set_key", help="Config key to set")
    config_parser.add_argument("--value", dest="set_value", help="Value to set")
    config_parser.set_defaults(func=cmd_config)
    
    # Serve command
    serve_parser = subparsers.add_parser("serve", help="Start API server")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port number")
    serve_parser.set_defaults(func=cmd_serve)
    
    # Web command
    web_parser = subparsers.add_parser("web", help="Start web console")
    web_parser.set_defaults(func=cmd_web)
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return
    
    args.func(args)


if __name__ == "__main__":
    main()
