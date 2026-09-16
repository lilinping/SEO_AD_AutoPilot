"""Shared helpers for domain service facades."""
from __future__ import annotations

import time
import uuid
from typing import Any


def service_result(
    service: str,
    success: bool,
    result: dict[str, Any] | None = None,
    error: str | None = None,
    execution_time_ms: int = 0,
    *,
    task_id: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """Return the stable service envelope used by smoke tests and callers."""
    return {
        "task_id": task_id or str(uuid.uuid4()),
        "service": service,
        "status": status or ("complete" if success else "error"),
        "success": success,
        "result": result or {},
        "error": error,
        "execution_time_ms": execution_time_ms,
    }


def elapsed_ms(start: float) -> int:
    return int((time.time() - start) * 1000)
