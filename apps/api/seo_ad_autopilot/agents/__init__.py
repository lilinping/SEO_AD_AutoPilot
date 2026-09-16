"""Multi-Agent system for SEO_AD_BOT.

All 11 agent roles are exported here.
"""

from .base import Agent, AgentRole, AgentOutput, DebateRound
from .sniffer import SnifferAgent
from .query import QueryAgent
from .geo import GEOAgent
from .strategist import StrategistAgent
from .ux_reviewer import UXReviewerAgent
from .coordinator import CoordinatorAgent
from .policy_guard import PolicyGuardAgent
from .aio_optimizer import AIOOptimizerAgent
from .rank_tracker import RankTrackerAgent
from .competitor_analyst import CompetitorAnalystAgent

__all__ = [
    # Base classes
    "Agent",
    "AgentRole",
    "AgentOutput",
    "DebateRound",
    # Core agents
    "CoordinatorAgent",
    "PolicyGuardAgent",
    # Analysis agents
    "SnifferAgent",
    "QueryAgent",
    "StrategistAgent",
    "UXReviewerAgent",
    # Specialized agents
    "AIOOptimizerAgent",
    "GEOAgent",
    "RankTrackerAgent",
    "CompetitorAnalystAgent",
]
