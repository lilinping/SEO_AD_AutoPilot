#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SEO-AD AutoPilot CLI - Command line interface for site analysis and system diagnostics.

Inspired by OpenClaw's onboard CLI experience.
"""

import argparse
import json
import os
import sys
import subprocess
from pathlib import Path
from typing import Optional

VERSION = "1.1.0-beta"

def cmd_analyze(args):
    """Analyze a website."""
    from apps.api.seo_ad_autopilot.search_engines.base import SearchEngineRegistry
    from apps.api.seo_ad_autopilot.ad_platforms.auto_discovery import analyze_site_for_ads
    from apps.api.seo_ad_autopilot.agents.geo import GEOAgent
    from apps.api.seo_ad_autopilot.agents.base import SiteContext

    url = args.url
    print()
    print(f"🔍 Analyzing: {url}")
    print()

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
    print()
    print("💰 Running ad platform analysis...")
    ad_result = analyze_site_for_ads(url, {"monthly_visits": 10000, "has_blog": True})

    print(f"   Ad Readiness Grade: {ad_result['ad_readiness']['grade']}")
    print(f"   Score: {ad_result['ad_readiness']['score']:.1f}/100")

    if ad_result['ad_recommendations']:
        print(f"   Top Platform: {ad_result['ad_recommendations'][0]['platform']}")

    # Search Engines
    print()
    print("🔎 Search engine coverage:")
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

    print()
    print("✅ Analysis complete!")
    print()


def load_env_file() -> dict:
    env_path = Path(".env")
    if not env_path.exists():
        return {}
    config = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            config[k.strip()] = v.strip()
    return config


def write_env_file(config: dict):
    env_path = Path(".env")
    example_path = Path(".env.example")

    # Preserve layout if example exists, otherwise write direct key-values
    template_lines = []
    if example_path.exists():
        template_lines = example_path.read_text(encoding="utf-8").splitlines()
    elif env_path.exists():
        template_lines = env_path.read_text(encoding="utf-8").splitlines()

    out = []
    processed_keys = set()

    for line in template_lines:
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            k = s.partition("=")[0].strip()
            if k in config:
                out.append(f"{k}={config[k]}")
                processed_keys.add(k)
                continue
        out.append(line)

    # Append any keys that weren't in the template
    for k, v in config.items():
        if k not in processed_keys:
            out.append(f"{k}={v}")

    env_path.write_text(chr(10).join(out) + chr(10), encoding="utf-8")


def cmd_config(args):
    """View or update configuration."""
    config = load_env_file()

    if args.show:
        print()
        print("📋 Current Configuration (.env):")
        if not config:
            print("  ⚠️  No .env file found. Run setup or config --set to create one.")
        else:
            for k, v in sorted(config.items()):
                # Mask secrets
                if "KEY" in k or "SECRET" in k or "TOKEN" in k or "PASSWORD" in k:
                    masked = v[:6] + "..." if len(v) > 6 else "********"
                    print(f"  {k}: {masked}")
                else:
                    print(f"  {k}: {v}")

        print()
        print("Search Engines Support Status:")
        print("  Google: " + ("✅ Configured" if config.get("GOOGLE_API_KEY") else "⚠️  Not configured (needs GOOGLE_API_KEY + GOOGLE_CX)"))
        print("  Bing: " + ("✅ Configured" if config.get("BING_API_KEY") else "⚠️  Not configured (needs BING_API_KEY)"))
        print("  ChatGPT: Built-in")
        print("  Perplexity: Built-in")
        print("  Claude: Built-in")

        print()
        print("Ad Platforms:")
        print("  Google AdSense: Auto-discover")
        print("  Mediavine: Auto-discover (50K+ visits)")
        print("  Ezoic: Auto-discover (10K+ visits)")

        print()
        print("Skills: 9 registered")
        print("  SiteCrawler, StyleExtractor, SiteAnalyzer")
        print("  ContentGenerator, SchemaBuilder")
        print("  GitHubPRCreator, CMSPublisher")
        print("  MetricsCollector, AlertManager")
    elif args.set_key:
        if args.set_value is None:
            print(f"❌ Error: Please specify a value using --value for the key '{args.set_key}'")
            return
        config[args.set_key] = args.set_value
        write_env_file(config)
        print(f"✅ Successfully set configuration: {args.set_key} = {args.set_value}")
    else:
        print("Use --show to display configuration, or --set <key> --value <val> to update a parameter.")
    print()


def cmd_serve(args):
    """Start the API server."""
    port = args.port or 8000
    print()
    print(f"🚀 Starting SEO-AD AutoPilot API on port {port}...")
    print()
    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "apps.api.seo_ad_autopilot.app:create_app",
        "--factory", "--reload",
        "--host", "127.0.0.1",
        "--port", str(port),
    ])


def cmd_web(args):
    """Start the web console."""
    print()
    print("🌐 Starting SEO-AD AutoPilot Web Console...")
    print()
    # Determine directory
    web_dir = Path("apps/web")
    if not web_dir.exists():
        print("❌ Error: Web Console folder (apps/web) not found in current directory.")
        return
    subprocess.run(["pnpm", "--dir", "apps/web", "dev"])


def cmd_doctor(args):
    """Run diagnostics to verify system health and dependencies."""
    print()
    print("🩺 Running SEO-AD AutoPilot Doctor Diagnostics...")
    print()
    all_pass = True

    # 1. Check Python version
    v = sys.version_info
    if v >= (3, 9):
        print(f"  [PASS] Python version: {v.major}.{v.minor}.{v.micro}")
    else:
        print(f"  [FAIL] Python version: {v.major}.{v.minor}.{v.micro} (Needs 3.9+)")
        all_pass = False

    # 2. Check Virtual Environment
    is_venv = (sys.prefix != sys.base_prefix) or "venv" in sys.prefix or ".venv" in sys.prefix
    if is_venv:
        print(f"  [PASS] Virtual Environment active: {sys.prefix}")
    else:
        print("  [WARN] Not running inside a Python virtual environment! (Highly recommended)")

    # 3. Check critical Python packages
    critical_pkgs = ["fastapi", "uvicorn", "pydantic", "sqlalchemy", "alembic", "aiosqlite", "openai"]
    missing_pkgs = []
    for pkg in critical_pkgs:
        try:
            __import__(pkg)
        except ImportError:
            missing_pkgs.append(pkg)
    if not missing_pkgs:
        print("  [PASS] Critical Python dependencies: All present")
    else:
        print(f"  [FAIL] Missing Python packages: {', '.join(missing_pkgs)}")
        all_pass = False

    # 4. Check Node.js and package managers
    try:
        node_ver = subprocess.check_output(["node", "--version"], text=True).strip()
        print(f"  [PASS] Node.js version: {node_ver}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("  [FAIL] Node.js is not installed or not in PATH")
        all_pass = False

    try:
        pnpm_ver = subprocess.check_output(["pnpm", "--version"], text=True).strip()
        print(f"  [PASS] pnpm version: {pnpm_ver}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("  [WARN] pnpm is not installed or not in PATH (Web dependencies need pnpm)")

    # 5. Check configuration files
    if Path(".env").exists():
        print("  [PASS] .env configuration file exists")
        env_cfg = load_env_file()
        if "OPENAI_API_KEY" in env_cfg and "sk-" in env_cfg["OPENAI_API_KEY"] and "your" not in env_cfg["OPENAI_API_KEY"]:
            print("  [PASS] OpenAI API Key configured")
        else:
            print("  [WARN] OpenAI API Key is missing or placeholder value inside .env")
    else:
        print("  [FAIL] .env configuration file is missing (run setup to create it)")
        all_pass = False

    # 6. Check database file
    db_file = Path("seo_ad_bot.db")
    if db_file.exists():
        print(f"  [PASS] SQLite local database found: {db_file.absolute()}")
    else:
        print("  [INFO] SQLite database does not exist yet (will be auto-created on startup)")

    print("-" * 50)
    if all_pass:
        print("🎉 Diagnostics complete: System health is GOOD!")
    else:
        print("❌ Diagnostics complete: Issues found. Please run setup again or fix the errors above.")
    print()


def cmd_status(args):
    """Check service status."""
    print()
    print("📊 Checking SEO-AD AutoPilot Service Status...")
    print()

    # Try checking API
    import socket
    api_running = False
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    result = sock.connect_ex(('127.0.0.1', 8000))
    if result == 0:
        api_running = True
        print("  API Server (Port 8000):  🟢 RUNNING")
    else:
        print("  API Server (Port 8000):  🔴 NOT RUNNING")
    sock.close()

    # Try checking Web UI
    web_running = False
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    result = sock.connect_ex(('127.0.0.1', 3000))
    if result == 0:
        web_running = True
        print("  Web Console (Port 3000): 🟢 RUNNING")
    else:
        print("  Web Console (Port 3000): 🔴 NOT RUNNING")
    sock.close()

    if api_running and web_running:
        print()
        print("✨ Awesome! Both parts of SEO-AD AutoPilot are active and ready.")
    elif api_running or web_running:
        print()
        print("⚠️  Partial components are running. Use './start-all.sh' (Unix) or 'start-all.bat' (Windows) to run all components together.")
    else:
        print()
        print("💡 Tip: Run './start-all.sh' (Unix) or 'start-all.bat' (Windows) to start the ecosystem.")
    print()


def cmd_version(args):
    """Show version info."""
    print(f"SEO-AD AutoPilot CLI version: {VERSION}")


def main():
    parser = argparse.ArgumentParser(
        description="SEO-AD AutoPilot - Multi-Engine SEO + GEO + Auto Ad Discovery",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  seo-ad analyze https://example.com     # Analyze a website
  seo-ad config --show                   # Show configuration
  seo-ad config --set KEY --value VAL    # Update configuration
  seo-ad serve --port 8000              # Start API server
  seo-ad web                             # Start web console
  seo-ad doctor                          # Troubleshoot / check diagnostics
  seo-ad status                          # Check if API or Web is running
  seo-ad version                         # Show version information
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

    # Doctor command
    doctor_parser = subparsers.add_parser("doctor", help="Run diagnostic health checks")
    doctor_parser.set_defaults(func=cmd_doctor)

    # Status command
    status_parser = subparsers.add_parser("status", help="Check active server status")
    status_parser.set_defaults(func=cmd_status)

    # Version command
    version_parser = subparsers.add_parser("version", help="Show version information")
    version_parser.set_defaults(func=cmd_version)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
