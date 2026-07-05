"""Competitor Service — GAP-007: extracted from service.py."""
from __future__ import annotations
from typing import Any, Optional
import time, uuid


class CompetitorService:
    """Competitor service stub — Phase 2 (GAP-007)."""

    def __init__(self, db=None, cache=None) -> None:
        self._db = db
        self._cache = cache

    # Override in concrete implementations
    async def run(self, **kwargs) -> dict[str, Any]:
        raise NotImplementedError(f"CompetitorService.run() not implemented yet")
