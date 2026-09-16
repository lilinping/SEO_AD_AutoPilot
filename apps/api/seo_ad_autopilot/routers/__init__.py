from .metrics import router as metrics_router
from .ad_platforms import router as ad_platforms_router
from .analysis import router as analysis_router
from .health import router as health_router
from .rank_tracking import router as rank_tracking_router
from .keywords import router as keywords_router
from .competitor import router as competitor_router
from .agents import router as agents_router
from .content import router as content_router
from .ecommerce import router as ecommerce_router
from .search_engines import router as search_engines_router
from .settings import router as settings_router
from .data_trust import router as data_trust_router

all_routers = [
    ad_platforms_router,
    analysis_router,
    health_router,
    rank_tracking_router,
    keywords_router,
    competitor_router,
    agents_router,
    content_router,
    ecommerce_router,
    search_engines_router,
    settings_router,
    data_trust_router,
]
