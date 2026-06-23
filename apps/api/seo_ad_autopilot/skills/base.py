"""Skill base class with OpenClaw-style registration.

Design principles:
- Each skill is a self-contained, atomic execution unit
- Skills have defined input/output schemas
- Skills are categorized by risk level
- Skills can be composed into workflows
- Skills are auditable and reversible
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


class SkillCategory(str, Enum):
    """Skill categories."""
    CRAWL = "crawl"
    ANALYZE = "analyze"
    GENERATE = "generate"
    DEPLOY = "deploy"
    MONITOR = "monitor"
    ROLLBACK = "rollback"
    ECOMMERCE = "ecommerce"


class SkillRiskLevel(str, Enum):
    """Skill risk levels."""
    READ_ONLY = "read_only"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class SkillInput:
    """Skill input parameters."""
    params: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillOutput:
    """Skill execution output."""
    skill_id: str
    success: bool
    result: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    execution_time_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class Skill(ABC):
    """Base class for all skills."""
    
    def __init__(self):
        self._skill_id: str = f"{self.__class__.__name__}_{uuid4().hex[:8]}"
    
    @property
    def skill_id(self) -> str:
        return self._skill_id
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Return human-readable skill name."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Return skill description."""
        pass
    
    @property
    @abstractmethod
    def category(self) -> SkillCategory:
        """Return skill category."""
        pass
    
    @property
    @abstractmethod
    def risk_level(self) -> SkillRiskLevel:
        """Return skill risk level."""
        pass
    
    @property
    def requires_approval(self) -> bool:
        """Check if skill requires approval."""
        return self.risk_level in [SkillRiskLevel.MEDIUM, SkillRiskLevel.HIGH]
    
    @property
    def rollback_supported(self) -> bool:
        """Check if skill supports rollback."""
        return True
    
    @abstractmethod
    def execute(self, skill_input: SkillInput) -> SkillOutput:
        """Execute the skill."""
        pass
    
    def validate_input(self, skill_input: SkillInput) -> bool:
        """Validate skill input. Override for custom validation."""
        return True
    
    def get_input_schema(self) -> dict[str, Any]:
        """Get input schema. Override for custom schema."""
        return {"type": "object", "properties": {}}
    
    def get_output_schema(self) -> dict[str, Any]:
        """Get output schema. Override for custom schema."""
        return {"type": "object", "properties": {}}
    
    def _create_output(
        self,
        success: bool,
        result: dict[str, Any] | None = None,
        error: str | None = None,
        execution_time_ms: int = 0,
    ) -> SkillOutput:
        """Create a skill output."""
        return SkillOutput(
            skill_id=self._skill_id,
            success=success,
            result=result or {},
            error=error,
            execution_time_ms=execution_time_ms,
        )
