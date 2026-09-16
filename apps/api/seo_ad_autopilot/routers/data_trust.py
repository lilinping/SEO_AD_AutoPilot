"""Data-trust (数据可信度) readiness API.

Aggregates the unified DataProvenance across all evaluable data sources so the
console can show a single "how real is my data, and what do I fix next?"
answer. See ``docs/数据可信度与真实数据源就绪度-产品设计.md``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/api/data-trust", tags=["data-trust"])


@router.get("")
async def data_trust_overview() -> dict[str, Any]:
    """Workspace-level data-trust score, tier distribution and remediation gaps."""
    from ..data_provenance import build_data_trust_report

    return build_data_trust_report()
