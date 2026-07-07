"""Content service facade around content generation skills."""
from __future__ import annotations

import inspect
from typing import Any

from ..skills import ContentDecayDetectorSkill, ContentGeneratorSkill, SchemaBuilderSkill, SkillInput
from ._helpers import service_result


class ContentService:
    """Run content generation, schema, and decay workflows."""

    def __init__(self, db=None, cache=None) -> None:
        self._db = db
        self._cache = cache

    async def run(self, **kwargs) -> dict[str, Any]:
        action = str(kwargs.pop("action", "generate"))
        if action == "schema":
            skill = SchemaBuilderSkill()
        elif action in {"decay", "content_decay"}:
            skill = ContentDecayDetectorSkill()
        else:
            skill = ContentGeneratorSkill()

        output = skill.execute(SkillInput(url=kwargs.get("url", ""), params=kwargs, context=kwargs.get("context", {})))
        if inspect.isawaitable(output):
            output = await output
        return service_result("content", output.success, output.result, output.error, output.execution_time_ms)
