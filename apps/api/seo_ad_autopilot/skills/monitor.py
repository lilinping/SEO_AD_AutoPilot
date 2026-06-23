"""Monitoring skills - delegates to real observability and alerting systems."""

from __future__ import annotations

import time
from typing import Any

from .base import Skill, SkillCategory, SkillInput, SkillOutput, SkillRiskLevel


class MetricsCollectorSkill(Skill):
    """Metrics Collector - collects real performance metrics."""
    
    @property
    def name(self) -> str:
        return "MetricsCollector"
    
    @property
    def description(self) -> str:
        return "Collect SEO, GEO, and performance metrics"
    
    @property
    def category(self) -> SkillCategory:
        return SkillCategory.MONITOR
    
    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.READ_ONLY
    
    def execute(self, skill_input: SkillInput) -> SkillOutput:
        start_time = time.time()
        
        url = skill_input.params.get("url", "")
        
        if not url:
            return self._create_output(
                success=False,
                error="URL is required",
            )
        
        try:
            from ..observability import collect_metrics
            
            metrics = collect_metrics(url)
            
            execution_time = int((time.time() - start_time) * 1000)
            
            return self._create_output(
                success=True,
                result=metrics,
                execution_time_ms=execution_time,
            )
            
        except ImportError:
            return self._create_output(
                success=False,
                error="Observability module not available. Configure monitoring backends.",
                execution_time_ms=int((time.time() - start_time) * 1000),
            )
        except Exception as e:
            return self._create_output(
                success=False,
                error=f"Metrics collection failed: {str(e)}",
                execution_time_ms=int((time.time() - start_time) * 1000),
            )
    
    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to collect metrics for"},
                "metrics": {"type": "array", "description": "Specific metrics to collect"},
            },
            "required": ["url"],
        }


class AlertManagerSkill(Skill):
    """Alert Manager - manages alerts via real notification channels."""
    
    @property
    def name(self) -> str:
        return "AlertManager"
    
    @property
    def description(self) -> str:
        return "Manage alerts for traffic drops, performance issues, and other events"
    
    @property
    def category(self) -> SkillCategory:
        return SkillCategory.MONITOR
    
    @property
    def risk_level(self) -> SkillRiskLevel:
        return SkillRiskLevel.LOW
    
    def execute(self, skill_input: SkillInput) -> SkillOutput:
        start_time = time.time()
        
        alert_type = skill_input.params.get("type", "info")
        message = skill_input.params.get("message", "")
        channels = skill_input.params.get("channels", ["email", "webhook"])
        
        try:
            from ..notifications import NotificationManager
            
            manager = NotificationManager()
            result_data = manager.send_alert(
                alert_type=alert_type,
                message=message,
                channels=channels,
            )
            
            execution_time = int((time.time() - start_time) * 1000)
            
            return self._create_output(
                success=result_data.get("success", False),
                result=result_data,
                error=result_data.get("error"),
                execution_time_ms=execution_time,
            )
            
        except ImportError:
            return self._create_output(
                success=False,
                error="Notification module not available. Configure alert channels in .env",
                execution_time_ms=int((time.time() - start_time) * 1000),
            )
        except Exception as e:
            return self._create_output(
                success=False,
                error=f"Alert sending failed: {str(e)}",
                execution_time_ms=int((time.time() - start_time) * 1000),
            )
    
    def get_input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["info", "warning", "error", "critical"], "description": "Alert type"},
                "message": {"type": "string", "description": "Alert message"},
                "channels": {"type": "array", "description": "Notification channels"},
            },
            "required": ["type", "message"],
        }
