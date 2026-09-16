"""Notification service facade around configured alert channels."""
from __future__ import annotations

import time
from typing import Any

from ._helpers import service_result


class NotificationService:
    """Send alerts via the default notification manager."""

    def __init__(self, db=None, cache=None) -> None:
        self._db = db
        self._cache = cache

    async def run(self, **kwargs) -> dict[str, Any]:
        from ..notifications import create_default_notification_manager

        start = time.time()
        alert_type = kwargs.get("alert_type") or kwargs.get("type") or "info"
        message = kwargs.get("message") or ""
        manager = create_default_notification_manager()
        configured_channels = manager.get_configured_channels()
        deliveries = manager.send_alert(alert_type=alert_type, message=message) if configured_channels else {}
        result = {
            "alert_type": alert_type,
            "message": message,
            "configured_channels": configured_channels,
            "deliveries": deliveries,
        }
        return service_result("notification", True, result, execution_time_ms=int((time.time() - start) * 1000))
