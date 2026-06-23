"""Amazon Ads Report skill wrapper.

This module wraps the OpenClaw linkfox-amazon-ads-report skill for use
in the SEO_AD_BOT project.

Workflow (from SKILL.md):
1. Determine reportTypeId based on user intent
2. Look up references/report-types/<adProduct-dir>/<reportTypeId>.md
3. Ask user for customizations (timeUnit, columns, filters)
4. Construct parameters with defaults
5. Call get_report.py with adProduct / groupBy / columns

Dependencies:
- linkfox-amazon-ads-auth (for authentication)
- Python 3.9+
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from .base import Skill, SkillCategory, SkillInput, SkillOutput, SkillRiskLevel


class AdProduct(str, Enum):
    """Amazon Ads product types."""
    SPONSORED_PRODUCTS = "SPONSORED_PRODUCTS"
    SPONSORED_BRANDS = "SPONSORED_BRANDS"
    SPONSORED_DISPLAY = "SPONSORED_DISPLAY"


class TimeUnit(str, Enum):
    """Report time unit."""
    DAILY = "DAILY"
    SUMMARY = "SUMMARY"


@dataclass
class ReportMetadata:
    """Metadata from report-types .md file."""
    report_type_id: str
    ad_product: str
    group_by: list[str]
    time_unit: list[str]
    format: str
    date_range: dict[str, Any]
    filters: list[dict[str, Any]] = field(default_factory=list)
    base_metrics: list[str] = field(default_factory=list)


class AmazonAdsReportSkill(Skill):
    """Skill for fetching Amazon Ads reports (SP/SB/SD).
    
    Wraps the OpenClaw linkfox-amazon-ads-report skill.
    Follows the documented workflow from SKILL.md.
    """
    
    # Path to the OpenClaw skill
    SKILL_DIR = Path(__file__).parent.parent.parent.parent.parent / "OpenClaw" / "skills" / "linkfox-amazon-ads-report"
    SCRIPTS_DIR = SKILL_DIR / "scripts"
    REFERENCES_DIR = SKILL_DIR / "references"
    
    @property
    def name(self) -> str:
        return "Amazon Ads Report"
    
    @property
    def description(self) -> str:
        return (
            "Fetch Amazon Ads reports for SP/SB/SD. "
            "Wraps linkfox-amazon-ads-report skill from ClawHub."
        )
    
    @property
    def category(self) -> SkillCategory:
        return SkillCategory.ECOMMERCE
    
    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.READ_ONLY
    
    def validate_input(self, skill_input: SkillInput) -> bool:
        """Validate required parameters."""
        params = skill_input.params
        # reportTypeId is required, adProduct/groupBy/columns will be looked up from reference
        return "reportTypeId" in params and "profileId" in params
    
    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "required": ["profileId", "reportTypeId"],
            "properties": {
                "profileId": {"type": "integer", "description": "Amazon Ads profile ID"},
                "region": {"type": "string", "default": "NA", "enum": ["NA", "EU", "FE"]},
                "reportTypeId": {"type": "string", "description": "Report type (e.g. spCampaigns)"},
                "adProduct": {"type": "string", "enum": ["SPONSORED_PRODUCTS", "SPONSORED_BRANDS", "SPONSORED_DISPLAY"]},
                "groupBy": {"type": "array", "items": {"type": "string"}},
                "columns": {"type": "array", "items": {"type": "string"}},
                "startDate": {"type": "string", "format": "date"},
                "endDate": {"type": "string", "format": "date"},
                "timeUnit": {"type": "string", "enum": ["DAILY", "SUMMARY"]},
                "filters": {"type": "array", "items": {"type": "object"}},
                "maxAttempts": {"type": "integer", "default": 20},
                "pollInterval": {"type": "integer", "default": 30},
            },
        }
    
    def execute(self, skill_input: SkillInput) -> SkillOutput:
        """Execute the report fetch following the documented workflow."""
        start_time = time.time()
        params = skill_input.params
        
        try:
            # Step 1: Get report metadata from reference
            report_type_id = params["reportTypeId"]
            ad_product = params.get("adProduct")
            
            metadata = self.get_report_metadata(report_type_id, ad_product)
            if not metadata:
                return self._create_output(
                    success=False,
                    error=f"Report type not found: {report_type_id}",
                )
            
            # Step 2: Apply defaults per SKILL.md
            ad_product = metadata.ad_product
            group_by = params.get("groupBy") or metadata.group_by[:1]
            
            # Determine timeUnit based on date span
            start_date = params.get("startDate", "")
            end_date = params.get("endDate", "")
            time_unit = params.get("timeUnit")
            
            if not time_unit and start_date and end_date:
                try:
                    start = datetime.strptime(start_date, "%Y-%m-%d")
                    end = datetime.strptime(end_date, "%Y-%m-%d")
                    days = (end - start).days
                    time_unit = "DAILY" if days <= 7 else "SUMMARY"
                except ValueError:
                    time_unit = "SUMMARY"
            else:
                time_unit = time_unit or "SUMMARY"
            
            # Step 3: Construct columns with defaults
            columns = params.get("columns")
            if not columns:
                columns = self._build_default_columns(metadata, time_unit, params)
            
            # Step 4: Build the request payload
            payload = {
                "profileId": params["profileId"],
                "region": params.get("region", "NA"),
                "reportTypeId": report_type_id,
                "adProduct": ad_product,
                "groupBy": group_by,
                "columns": columns,
                "startDate": start_date,
                "endDate": end_date,
                "timeUnit": time_unit,
                "maxAttempts": params.get("maxAttempts", 20),
                "pollInterval": params.get("pollInterval", 30),
            }
            
            # Add filters if provided
            if params.get("filters"):
                payload["filters"] = params["filters"]
            
            # Step 5: Call get_report.py
            result = self._call_get_report(payload)
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            if result.get("success"):
                return self._create_output(
                    success=True,
                    result={
                        "reportId": result.get("reportId"),
                        "reportTypeId": result.get("reportTypeId"),
                        "startDate": result.get("startDate"),
                        "endDate": result.get("endDate"),
                        "downloadPath": result.get("downloadPath"),
                        "extractedFileHttpUrl": result.get("extractedFileHttpUrl"),
                        "extractedFileHttpServeSeconds": result.get("extractedFileHttpServeSeconds", 300),
                    },
                    execution_time_ms=elapsed_ms,
                )
            else:
                return self._create_output(
                    success=False,
                    error=result.get("error", "Report fetch failed"),
                    result={
                        "httpStatus": result.get("httpStatus"),
                        "failureReason": result.get("failureReason"),
                        "reportId": result.get("reportId"),
                    },
                    execution_time_ms=elapsed_ms,
                )
        
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            return self._create_output(
                success=False,
                error=str(e),
                execution_time_ms=elapsed_ms,
            )
    
    def _build_default_columns(
        self,
        metadata: ReportMetadata,
        time_unit: str,
        params: dict[str, Any],
    ) -> list[str]:
        """Build default columns based on metadata and user intent."""
        columns = []
        
        # Time dimension
        if time_unit == "DAILY":
            columns.append("date")
        else:
            columns.extend(["startDate", "endDate"])
        
        # Primary key fields based on groupBy
        if "campaign" in metadata.group_by:
            columns.extend(["campaignId", "campaignName"])
        elif "searchTerm" in metadata.group_by:
            columns.extend(["searchTerm", "keyword", "matchType"])
        elif "advertisedProduct" in metadata.group_by:
            columns.extend(["advertisedAsin", "advertisedSku"])
        elif "adGroup" in metadata.group_by:
            columns.extend(["adGroupId", "adGroupName"])
        elif "keyword" in metadata.group_by:
            columns.extend(["keyword", "matchType"])
        
        # Base metrics (always include if available)
        base_metrics = ["impressions", "clicks", "cost"]
        for metric in base_metrics:
            if metric in metadata.base_metrics:
                columns.append(metric)
        
        # Attribution metrics (only if user mentions sales/conversion/ROI/ACOS)
        user_intent = str(params).lower()
        attribution_keywords = ["sales", "转化", "roi", "acos", "roas", "purchases"]
        if any(kw in user_intent for kw in attribution_keywords):
            attribution_metrics = ["sales7d", "purchases7d", "acosClicks7d", "roasClicks7d"]
            for metric in attribution_metrics:
                if metric in metadata.base_metrics:
                    columns.append(metric)
        
        return columns
    
    def _call_get_report(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Call the get_report.py script."""
        script_path = self.SCRIPTS_DIR / "get_report.py"
        
        if not script_path.exists():
            return {"error": f"Script not found: {script_path}"}
        
        try:
            proc = subprocess.run(
                ["python3", str(script_path), json.dumps(payload)],
                capture_output=True,
                text=True,
                timeout=900,  # 15 minutes max
            )
            
            # Exit code 42 = dependency missing
            if proc.returncode == 42:
                return {"error": "DEPENDENCY_MISSING: linkfox-amazon-ads-auth not installed"}
            
            # Exit code 2 = STILL_PROCESSING
            if proc.returncode == 2:
                try:
                    data = json.loads(proc.stdout)
                    return {
                        "success": False,
                        "reportId": data.get("reportId"),
                        "error": "STILL_PROCESSING",
                        "failureReason": "Client polling window exhausted but report still generating",
                        "resumeHint": data.get("resumeHint"),
                    }
                except json.JSONDecodeError:
                    return {"error": proc.stdout or proc.stderr}
            
            # Parse response
            try:
                data = json.loads(proc.stdout)
            except json.JSONDecodeError:
                return {"error": f"Invalid response: {proc.stdout[:500]}"}
            
            return data
        
        except subprocess.TimeoutExpired:
            return {"error": "Script timed out after 15 minutes"}
        except FileNotFoundError:
            return {"error": "Python3 not found in PATH"}
    
    def get_report_types(self, ad_product: Optional[str] = None) -> dict[str, list[str]]:
        """List available report types from references."""
        ref_dir = self.REFERENCES_DIR / "report-types"
        
        if not ref_dir.exists():
            return {}
        
        result = {}
        for product_dir in ref_dir.iterdir():
            if not product_dir.is_dir():
                continue
            if ad_product and product_dir.name.upper() != ad_product.upper():
                continue
            
            report_types = []
            for md_file in product_dir.glob("*.md"):
                if md_file.stem != "index":
                    report_types.append(md_file.stem)
            
            if report_types:
                result[product_dir.name] = sorted(report_types)
        
        return result
    
    def get_report_metadata(self, report_type_id: str, ad_product: Optional[str] = None) -> Optional[ReportMetadata]:
        """Get metadata for a specific report type from references."""
        ref_dir = self.REFERENCES_DIR / "report-types"
        
        # Try to find the report type in any ad product directory
        for product_dir in ref_dir.iterdir():
            if not product_dir.is_dir():
                continue
            if ad_product and product_dir.name.upper() != ad_product.upper():
                continue
            
            md_file = product_dir / f"{report_type_id}.md"
            if md_file.exists():
                return self._parse_report_metadata(md_file, report_type_id)
        
        return None
    
    def _parse_report_metadata(self, md_file: Path, report_type_id: str) -> Optional[ReportMetadata]:
        """Parse report metadata from .md file."""
        try:
            content = md_file.read_text()
            lines = content.split("\n")
            
            # Parse frontmatter
            in_frontmatter = False
            frontmatter_lines = []
            
            for line in lines:
                if line.strip() == "---":
                    if in_frontmatter:
                        break
                    in_frontmatter = True
                    continue
                if in_frontmatter:
                    frontmatter_lines.append(line)
            
            # Parse key-value pairs
            metadata_dict = {}
            for line in frontmatter_lines:
                if ":" in line:
                    key, _, value = line.partition(":")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if value.startswith("["):
                        try:
                            value = json.loads(value)
                        except json.JSONDecodeError:
                            pass
                    metadata_dict[key] = value
            
            # Parse Base Metrics table
            base_metrics = []
            in_metrics_table = False
            for line in lines:
                if "Base Metrics" in line or "Base metrics" in line:
                    in_metrics_table = True
                    continue
                if in_metrics_table:
                    if line.startswith("|") and "Column" not in line and "---" not in line:
                        parts = [p.strip() for p in line.split("|")]
                        if len(parts) >= 2 and parts[1]:
                            base_metrics.append(parts[1])
                    elif line.startswith("#") or line.startswith("##"):
                        break
            
            return ReportMetadata(
                report_type_id=report_type_id,
                ad_product=metadata_dict.get("adProduct", ""),
                group_by=metadata_dict.get("groupBy", []),
                time_unit=metadata_dict.get("timeUnit", []),
                format=metadata_dict.get("format", "GZIP_JSON"),
                date_range=metadata_dict.get("dateRange", {}),
                base_metrics=base_metrics,
            )
        
        except Exception:
            return None
    
    def list_authorized_stores(self) -> dict[str, Any]:
        """List authorized stores using linkfox-amazon-ads-auth."""
        auth_skill_dir = self.SKILL_DIR.parent / "linkfox-amazon-ads-auth"
        script_path = auth_skill_dir / "scripts" / "authorized_stores.py"
        
        if not script_path.exists():
            return {"error": "linkfox-amazon-ads-auth not installed"}
        
        try:
            proc = subprocess.run(
                ["python3", str(script_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            
            try:
                return json.loads(proc.stdout)
            except json.JSONDecodeError:
                return {"error": f"Invalid response: {proc.stdout[:500]}"}
        
        except subprocess.TimeoutExpired:
            return {"error": "Script timed out"}
        except FileNotFoundError:
            return {"error": "Python3 not found in PATH"}
