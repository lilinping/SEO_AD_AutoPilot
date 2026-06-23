"""Real SEO Data Skills - bridges ClawHub skills into the project skill system.

Integrates:
- DataForSEO API (keyword research, SERP, competitor analysis)
- Ahrefs API (backlinks, keywords, site audit, rank tracking)
- Google Search Console (search performance, indexing)

Each skill wraps the corresponding ClawHub skill's scripts/API calls
and returns results in the project's standard SkillOutput format.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

from .base import Skill, SkillCategory, SkillInput, SkillOutput, SkillRiskLevel


SKILLS_DIR = Path(os.environ.get(
    "CLAWHUB_SKILLS_DIR",
    os.path.expanduser("~/.openclaw/workspace/skills"),
))


class DataForKeywordResearchSkill(Skill):
    """DataForSEO keyword research - real search volume, CPC, competition data."""

    @property
    def name(self) -> str:
        return "DataForSEO Keyword Research"

    @property
    def description(self) -> str:
        return (
            "Real keyword data via DataForSEO API: search volume, CPC, competition, "
            "keyword suggestions, SERP analysis, competitor keywords, trending topics."
        )

    @property
    def category(self) -> SkillCategory:
        return SkillCategory.ANALYZE

    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.READ_ONLY

    def validate_input(self, skill_input: SkillInput) -> bool:
        return "keyword" in skill_input.params or "keywords" in skill_input.params

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "keyword": {"type": "string"},
                "keywords": {"type": "array", "items": {"type": "string"}},
                "operation": {
                    "type": "string",
                    "enum": [
                        "keyword_research",
                        "full_keyword_analysis",
                        "competitor_analysis",
                        "trending_topics",
                        "youtube_keyword_research",
                        "landing_page_keyword_research",
                    ],
                    "default": "keyword_research",
                },
                "location": {"type": "string", "default": "United States"},
                "competitor_domain": {"type": "string"},
            },
        }

    def execute(self, skill_input: SkillInput) -> SkillOutput:
        start_time = time.time()
        params = skill_input.params

        try:
            login = os.environ.get("DATAFORSEO_LOGIN", "")
            password = os.environ.get("DATAFORSEO_PASSWORD", "")
            if not login or not password:
                return self._create_output(
                    success=False,
                    error="DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD env vars required. Get from https://app.dataforseo.com/api-access",
                    execution_time_ms=int((time.time() - start_time) * 1000),
                )

            scripts_dir = SKILLS_DIR / "seo-dataforseo" / "scripts"
            if not scripts_dir.exists():
                return self._create_output(
                    success=False,
                    error=f"seo-dataforseo skill not installed at {scripts_dir}",
                    execution_time_ms=int((time.time() - start_time) * 1000),
                )

            operation = params.get("operation", "keyword_research")
            keyword = params.get("keyword", "")
            keywords = params.get("keywords", [])
            location = params.get("location", "United States")

            main_py = scripts_dir / "main.py"
            sys_path = str(scripts_dir)

            if operation == "keyword_research" and keyword:
                code = f"""
import sys; sys.path.insert(0, '{sys_path}')
from main import keyword_research
result = keyword_research("{keyword}", location_name="{location}")
print(json.dumps(result, default=str))
"""
            elif operation == "full_keyword_analysis" and keywords:
                kw_list = json.dumps(keywords)
                code = f"""
import sys; sys.path.insert(0, '{sys_path}')
from main import full_keyword_analysis
result = full_keyword_analysis({kw_list}, location_name="{location}")
print(json.dumps(result, default=str))
"""
            elif operation == "competitor_analysis" and params.get("competitor_domain"):
                domain = params["competitor_domain"]
                kw_list = json.dumps(keywords or [])
                code = f"""
import sys; sys.path.insert(0, '{sys_path}')
from main import competitor_analysis
result = competitor_analysis("{domain}", {kw_list}, location_name="{location}")
print(json.dumps(result, default=str))
"""
            elif operation == "trending_topics":
                code = f"""
import sys; sys.path.insert(0, '{sys_path}')
from main import trending_topics
result = trending_topics("{location}")
print(json.dumps(result, default=str))
"""
            else:
                return self._create_output(
                    success=False,
                    error=f"Invalid operation '{operation}' or missing required params",
                    execution_time_ms=int((time.time() - start_time) * 1000),
                )

            proc = subprocess.run(
                [str(Path(os.environ.get("PYTHON", "python"))), "-c", code],
                capture_output=True, text=True, timeout=120,
                env={**os.environ, "DATAFORSEO_LOGIN": login, "DATAFORSEO_PASSWORD": password},
                cwd=str(scripts_dir),
            )

            elapsed_ms = int((time.time() - start_time) * 1000)

            if proc.returncode != 0:
                return self._create_output(
                    success=False,
                    error=f"DataForSEO API error: {proc.stderr[:500]}",
                    execution_time_ms=elapsed_ms,
                )

            try:
                result = json.loads(proc.stdout.strip())
            except json.JSONDecodeError:
                result = {"raw_output": proc.stdout[:2000]}

            return self._create_output(
                success=True,
                result={"source": "dataforseo", "operation": operation, "data": result},
                execution_time_ms=elapsed_ms,
            )

        except subprocess.TimeoutExpired:
            return self._create_output(
                success=False, error="DataForSEO API call timed out (120s)",
                execution_time_ms=int((time.time() - start_time) * 1000),
            )
        except Exception as e:
            return self._create_output(
                success=False, error=str(e),
                execution_time_ms=int((time.time() - start_time) * 1000),
            )


class AhrefsSiteExplorerSkill(Skill):
    """Ahrefs Site Explorer - domain analysis, backlinks, keywords, traffic."""

    @property
    def name(self) -> str:
        return "Ahrefs Site Explorer"

    @property
    def description(self) -> str:
        return (
            "Real SEO data via Ahrefs API: domain rating, organic traffic, "
            "backlinks, referring domains, top pages, organic keywords."
        )

    @property
    def category(self) -> SkillCategory:
        return SkillCategory.ANALYZE

    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.READ_ONLY

    def validate_input(self, skill_input: SkillInput) -> bool:
        return "domain" in skill_input.params or "target" in skill_input.params

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "Target domain (e.g. example.com)"},
                "endpoint": {
                    "type": "string",
                    "enum": [
                        "metrics", "backlinks_stats", "domain_rating",
                        "top_pages", "organic_keywords", "overview",
                    ],
                    "default": "overview",
                },
                "limit": {"type": "integer", "default": 10},
            },
        }

    def execute(self, skill_input: SkillInput) -> SkillOutput:
        start_time = time.time()
        params = skill_input.params

        try:
            token = os.environ.get("AHREFS_API_TOKEN", "")
            if not token:
                return self._create_output(
                    success=False,
                    error="AHREFS_API_TOKEN env var required. Get from https://ahrefs.com/api",
                    execution_time_ms=int((time.time() - start_time) * 1000),
                )

            import urllib.request
            import urllib.parse

            domain = params.get("domain") or params.get("target", "")
            endpoint = params.get("endpoint", "overview")
            limit = params.get("limit", 10)
            today = time.strftime("%Y-%m-%d")

            base = "https://api.ahrefs.com/v3/site-explorer"

            if endpoint == "overview":
                results = {}
                for ep, extra in [
                    ("metrics", ""),
                    ("backlinks-stats", ""),
                    ("domain-rating", ""),
                    ("top-pages", f"&limit={limit}&select=url,sum_traffic,keywords&order_by=sum_traffic:desc"),
                ]:
                    url = f"{base}/{ep}?date={today}&target={urllib.parse.quote(domain)}{extra}"
                    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
                    try:
                        with urllib.request.urlopen(req, timeout=15) as resp:
                            results[ep.replace("-", "_")] = json.loads(resp.read())
                    except Exception as e:
                        results[ep.replace("-", "_")] = {"error": str(e)}
                data = results
            else:
                ep = endpoint.replace("_", "-")
                extra = ""
                if endpoint == "top_pages":
                    extra = f"&limit={limit}&select=url,sum_traffic,keywords&order_by=sum_traffic:desc"
                url = f"{base}/{ep}?date={today}&target={urllib.parse.quote(domain)}{extra}"
                req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    data = json.loads(resp.read())

            elapsed_ms = int((time.time() - start_time) * 1000)
            return self._create_output(
                success=True,
                result={"source": "ahrefs", "domain": domain, "endpoint": endpoint, "data": data},
                execution_time_ms=elapsed_ms,
            )

        except Exception as e:
            return self._create_output(
                success=False, error=str(e),
                execution_time_ms=int((time.time() - start_time) * 1000),
            )


class AhrefsKeywordExplorerSkill(Skill):
    """Ahrefs Keywords Explorer - real keyword volume, difficulty, SERP data."""

    @property
    def name(self) -> str:
        return "Ahrefs Keyword Explorer"

    @property
    def description(self) -> str:
        return (
            "Real keyword data via Ahrefs API: search volume, keyword difficulty, "
            "CPC, SERP overview, related keywords, click potential."
        )

    @property
    def category(self) -> SkillCategory:
        return SkillCategory.ANALYZE

    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.READ_ONLY

    def validate_input(self, skill_input: SkillInput) -> bool:
        return "keyword" in skill_input.params

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "keyword": {"type": "string"},
                "country": {"type": "string", "default": "us"},
            },
        }

    def execute(self, skill_input: SkillInput) -> SkillOutput:
        start_time = time.time()
        params = skill_input.params

        try:
            token = os.environ.get("AHREFS_API_TOKEN", "")
            if not token:
                return self._create_output(
                    success=False,
                    error="AHREFS_API_TOKEN env var required",
                    execution_time_ms=int((time.time() - start_time) * 1000),
                )

            import urllib.request
            import urllib.parse

            keyword = params["keyword"]
            country = params.get("country", "us")
            today = time.strftime("%Y-%m-%d")

            url = (
                f"https://api.ahrefs.com/v3/keywords-explorer/keyword-overview"
                f"?date={today}&keyword={urllib.parse.quote(keyword)}&country={country}"
            )
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())

            elapsed_ms = int((time.time() - start_time) * 1000)
            return self._create_output(
                success=True,
                result={"source": "ahrefs", "keyword": keyword, "country": country, "data": data},
                execution_time_ms=elapsed_ms,
            )

        except Exception as e:
            return self._create_output(
                success=False, error=str(e),
                execution_time_ms=int((time.time() - start_time) * 1000),
            )


class AmazonAdsReporterSkill(Skill):
    """Amazon Ads Reporter - real SP/SB/SD campaign and keyword reports."""

    SCRIPT_DIR = SKILLS_DIR / "linkfox-amazon-ads-report" / "scripts"

    @property
    def name(self) -> str:
        return "Amazon Ads Reporter"

    @property
    def description(self) -> str:
        return (
            "Real Amazon Ads data: SP/SB/SD campaign reports, keyword reports, "
            "search term reports, bid inspection. Requires linkfox-amazon-ads-auth."
        )

    @property
    def category(self) -> SkillCategory:
        return SkillCategory.ECOMMERCE

    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.READ_ONLY

    def validate_input(self, skill_input: SkillInput) -> bool:
        params = skill_input.params
        return "profile_id" in params or "report_type_id" in params

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "profile_id": {"type": "integer"},
                "region": {"type": "string", "enum": ["NA", "EU", "FE"], "default": "NA"},
                "report_type_id": {"type": "string"},
                "ad_product": {"type": "string", "enum": ["SPONSORED_PRODUCTS", "SPONSORED_BRANDS", "SPONSORED_DISPLAY"]},
                "group_by": {"type": "array", "items": {"type": "string"}},
                "columns": {"type": "array", "items": {"type": "string"}},
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
                "time_unit": {"type": "string", "enum": ["DAILY", "SUMMARY"], "default": "SUMMARY"},
                "filters": {"type": "array", "items": {"type": "object"}},
            },
        }

    def execute(self, skill_input: SkillInput) -> SkillOutput:
        start_time = time.time()
        params = skill_input.params

        try:
            script = self.SCRIPT_DIR / "get_report.py"
            if not script.exists():
                return self._create_output(
                    success=False,
                    error=f"linkfox-amazon-ads-report not installed at {self.SCRIPT_DIR}",
                    execution_time_ms=int((time.time() - start_time) * 1000),
                )

            payload = {
                "profileId": params.get("profile_id"),
                "region": params.get("region", "NA"),
                "reportTypeId": params.get("report_type_id", ""),
                "adProduct": params.get("ad_product", "SPONSORED_PRODUCTS"),
                "groupBy": params.get("group_by", ["campaign"]),
                "columns": params.get("columns", ["date", "campaignId", "campaignName", "impressions", "clicks", "cost"]),
                "startDate": params.get("start_date", ""),
                "endDate": params.get("end_date", ""),
                "timeUnit": params.get("time_unit", "SUMMARY"),
            }
            if params.get("filters"):
                payload["filters"] = params["filters"]

            proc = subprocess.run(
                ["python", str(script), json.dumps(payload)],
                capture_output=True, text=True, timeout=900,
            )

            elapsed_ms = int((time.time() - start_time) * 1000)

            if proc.returncode == 42:
                return self._create_output(
                    success=False,
                    error="DEPENDENCY_MISSING: linkfox-amazon-ads-auth not installed",
                    execution_time_ms=elapsed_ms,
                )

            try:
                result = json.loads(proc.stdout)
            except json.JSONDecodeError:
                return self._create_output(
                    success=False, error=f"Invalid response: {proc.stdout[:500]}",
                    execution_time_ms=elapsed_ms,
                )

            return self._create_output(
                success=result.get("success", False),
                result={"source": "amazon_ads", **result},
                error=result.get("error"),
                execution_time_ms=elapsed_ms,
            )

        except subprocess.TimeoutExpired:
            return self._create_output(
                success=False, error="Amazon Ads report timed out (15min)",
                execution_time_ms=int((time.time() - start_time) * 1000),
            )
        except Exception as e:
            return self._create_output(
                success=False, error=str(e),
                execution_time_ms=int((time.time() - start_time) * 1000),
            )


class AmazonAdsNodeReporterSkill(Skill):
    """Amazon Ads Node.js Reporter - lightweight campaign/keyword reports."""

    SCRIPT_DIR = SKILLS_DIR / "skill-amazon-ads-reporter" / "scripts"

    @property
    def name(self) -> str:
        return "Amazon Ads Node Reporter"

    @property
    def description(self) -> str:
        return (
            "Amazon Ads campaign and keyword reports via Node.js scripts. "
            "Supports campaign-level report, keyword winner/dead analysis, bid inspection."
        )

    @property
    def category(self) -> SkillCategory:
        return SkillCategory.ECOMMERCE

    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.READ_ONLY

    def validate_input(self, skill_input: SkillInput) -> bool:
        return True

    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["get_bids", "keyword_report"],
                    "default": "get_bids",
                },
                "days": {"type": "integer", "default": 7},
            },
        }

    def execute(self, skill_input: SkillInput) -> SkillOutput:
        start_time = time.time()
        params = skill_input.params

        try:
            operation = params.get("operation", "get_bids")
            days = params.get("days", 7)

            if operation == "get_bids":
                script = self.SCRIPT_DIR / "get-bids.js"
            elif operation == "keyword_report":
                script = self.SCRIPT_DIR / "keyword-report.js"
            else:
                return self._create_output(
                    success=False, error=f"Unknown operation: {operation}",
                    execution_time_ms=int((time.time() - start_time) * 1000),
                )

            if not script.exists():
                return self._create_output(
                    success=False,
                    error=f"skill-amazon-ads-reporter not installed at {self.SCRIPT_DIR}",
                    execution_time_ms=int((time.time() - start_time) * 1000),
                )

            cmd = ["node", str(script)]
            if operation == "keyword_report":
                cmd.extend(["--days", str(days)])

            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            elapsed_ms = int((time.time() - start_time) * 1000)

            if proc.returncode != 0:
                return self._create_output(
                    success=False, error=proc.stderr[:500],
                    execution_time_ms=elapsed_ms,
                )

            output_file = Path.home() / ".openclaw" / "workspace" / "tmp" / "amazon-report-latest.json"
            data = {}
            if output_file.exists():
                try:
                    data = json.loads(output_file.read_text())
                except json.JSONDecodeError:
                    pass

            return self._create_output(
                success=True,
                result={
                    "source": "amazon_ads_node",
                    "operation": operation,
                    "data": data,
                    "raw_output": proc.stdout[:2000],
                },
                execution_time_ms=elapsed_ms,
            )

        except subprocess.TimeoutExpired:
            return self._create_output(
                success=False, error="Amazon Ads Node script timed out",
                execution_time_ms=int((time.time() - start_time) * 1000),
            )
        except Exception as e:
            return self._create_output(
                success=False, error=str(e),
                execution_time_ms=int((time.time() - start_time) * 1000),
            )
