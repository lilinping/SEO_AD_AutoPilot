"""Middleware package.

Provides:
- RequestLoggerMiddleware: structured JSON logging + X-Request-ID injection
- SubscriptionQuotaMiddleware: Stripe subscription + API Quota gateway interceptor
- configure_structured_logging: replace root logger with JSON formatter
- get_request_id: access current request ID from anywhere in the call stack
"""

from .request_logger import (
    RequestLoggerMiddleware,
    configure_structured_logging,
    get_request_id,
)
from .subscription_quota import SubscriptionQuotaMiddleware

__all__ = [
    "RequestLoggerMiddleware",
    "SubscriptionQuotaMiddleware",
    "configure_structured_logging",
    "get_request_id",
]
