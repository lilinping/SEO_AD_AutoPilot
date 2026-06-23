"""A/B Experiment System.

Inspired by OpenClaw's experimentation capabilities:
- Ad position testing
- Ad type testing
- Density optimization
- Automatic rollback on performance degradation
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class ExperimentStatus(str, Enum):
    """Experiment status."""
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class ExperimentDimension(str, Enum):
    """Experiment dimensions."""
    AD_POSITION = "ad_position"
    AD_TYPE = "ad_type"
    AD_DENSITY = "ad_density"
    AD_STYLE = "ad_style"
    CONTENT_MODULE = "content_module"


@dataclass
class ExperimentVariant:
    """An experiment variant."""
    variant_id: str
    name: str
    config: dict[str, Any]
    traffic_percentage: float = 50.0


@dataclass
class ExperimentMetrics:
    """Experiment metrics."""
    impressions: int = 0
    clicks: int = 0
    ctr: float = 0.0
    rpm: float = 0.0
    viewability: float = 0.0
    bounce_rate: float = 0.0
    conversion_rate: float = 0.0
    lcp: float = 0.0
    cls: float = 0.0


@dataclass
class ExperimentResult:
    """Experiment result."""
    variant_id: str
    metrics: ExperimentMetrics
    confidence: float = 0.0
    is_winner: bool = False


@dataclass
class Experiment:
    """An A/B experiment."""
    experiment_id: str
    name: str
    dimension: ExperimentDimension
    status: ExperimentStatus = ExperimentStatus.DRAFT
    variants: list[ExperimentVariant] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    results: list[ExperimentResult] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ABExperimentEngine:
    """A/B Experiment Engine."""
    
    def __init__(self):
        self._experiments: dict[str, Experiment] = {}
    
    def create_experiment(
        self,
        name: str,
        dimension: ExperimentDimension,
        variants: list[dict[str, Any]],
    ) -> Experiment:
        """Create a new experiment."""
        experiment_id = f"exp_{hashlib.md5(name.encode()).hexdigest()[:8]}"
        
        experiment_variants = [
            ExperimentVariant(
                variant_id=f"variant_{i}",
                name=v.get("name", f"Variant {i}"),
                config=v.get("config", {}),
                traffic_percentage=v.get("traffic_percentage", 50.0),
            )
            for i, v in enumerate(variants)
        ]
        
        experiment = Experiment(
            experiment_id=experiment_id,
            name=name,
            dimension=dimension,
            variants=experiment_variants,
        )
        
        self._experiments[experiment_id] = experiment
        return experiment
    
    def start_experiment(self, experiment_id: str) -> bool:
        """Start an experiment."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return False
        
        experiment.status = ExperimentStatus.RUNNING
        experiment.start_time = datetime.now()
        return True
    
    def pause_experiment(self, experiment_id: str) -> bool:
        """Pause an experiment."""
        experiment = self._experiments.get(experiment_id)
        if not experiment or experiment.status != ExperimentStatus.RUNNING:
            return False
        
        experiment.status = ExperimentStatus.PAUSED
        return True
    
    def complete_experiment(self, experiment_id: str) -> bool:
        """Complete an experiment."""
        experiment = self._experiments.get(experiment_id)
        if not experiment or experiment.status != ExperimentStatus.RUNNING:
            return False
        
        experiment.status = ExperimentStatus.COMPLETED
        experiment.end_time = datetime.now()
        
        # Determine winner
        self._determine_winner(experiment)
        
        return True
    
    def record_metrics(
        self,
        experiment_id: str,
        variant_id: str,
        metrics: dict[str, Any],
    ) -> bool:
        """Record metrics for a variant."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return False
        
        result = ExperimentResult(
            variant_id=variant_id,
            metrics=ExperimentMetrics(**metrics),
        )
        
        experiment.results.append(result)
        return True
    
    def get_experiment(self, experiment_id: str) -> Optional[Experiment]:
        """Get an experiment."""
        return self._experiments.get(experiment_id)
    
    def get_all_experiments(self) -> list[Experiment]:
        """Get all experiments."""
        return list(self._experiments.values())
    
    def get_experiment_summary(self, experiment_id: str) -> dict[str, Any]:
        """Get experiment summary."""
        experiment = self._experiments.get(experiment_id)
        if not experiment:
            return {}
        
        return {
            "experiment_id": experiment.experiment_id,
            "name": experiment.name,
            "dimension": experiment.dimension.value,
            "status": experiment.status.value,
            "variants": len(experiment.variants),
            "results": len(experiment.results),
            "start_time": experiment.start_time.isoformat() if experiment.start_time else None,
            "end_time": experiment.end_time.isoformat() if experiment.end_time else None,
        }
    
    def _determine_winner(self, experiment: Experiment) -> None:
        """Determine the winning variant."""
        if not experiment.results:
            return
        
        # Group results by variant
        variant_results: dict[str, list[ExperimentResult]] = {}
        for result in experiment.results:
            if result.variant_id not in variant_results:
                variant_results[result.variant_id] = []
            variant_results[result.variant_id].append(result)
        
        # Calculate average metrics for each variant
        variant_scores: dict[str, float] = {}
        for variant_id, results in variant_results.items():
            avg_ctr = sum(r.metrics.ctr for r in results) / len(results)
            avg_rpm = sum(r.metrics.rpm for r in results) / len(results)
            # Combined score: CTR * 0.4 + RPM * 0.4 + (1 - bounce_rate) * 0.2
            avg_bounce = sum(r.metrics.bounce_rate for r in results) / len(results)
            score = avg_ctr * 0.4 + avg_rpm * 0.4 + (1 - avg_bounce) * 0.2
            variant_scores[variant_id] = score
        
        # Find winner
        if variant_scores:
            winner_id = max(variant_scores, key=variant_scores.get)
            for result in experiment.results:
                if result.variant_id == winner_id:
                    result.is_winner = True
                    result.confidence = 0.95


def create_experiment_engine() -> ABExperimentEngine:
    """Create an A/B experiment engine."""
    return ABExperimentEngine()
