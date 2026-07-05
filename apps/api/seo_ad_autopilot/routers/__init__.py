"""Router package for SEO_AD_BOT API.

All sub-routers are registered here and included in app.py via:
    from .routers import all_routers
    for router in all_routers:
        app.include_router(router)
"""

from .keywords import router as keywords_router
from .ecommerce import router as ecommerce_router
from .agents import router as agents_router
from .analysis import router as analysis_router
from .content import router as content_router
from .ad_platforms import router as ad_platforms_router
from .rank_tracking import router as rank_tracking_router
from .competitor import router as competitor_router
from .search_engines import router as search_engines_router
from .health import router as health_router

all_routers = [
    health_router,
    keywords_router,
    ecommerce_router,
    agents_router,
    analysis_router,
    content_router,
    ad_platforms_router,
    rank_tracking_router,
    competitor_router,
    search_engines_router,
]

__all__ = ["all_routers"]
