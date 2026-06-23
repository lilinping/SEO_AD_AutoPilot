"""Cron job scheduling system.

Inspired by OpenClaw's cron capabilities:
- Scheduled analysis tasks
- Periodic monitoring
- Automated alerts
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional
from uuid import uuid4


class CronFrequency(str, Enum):
    """Cron job frequency."""
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


@dataclass
class CronJob:
    """A scheduled job."""
    job_id: str
    name: str
    frequency: CronFrequency
    action: str  # analyze, monitor, alert
    config: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class CronRunResult:
    """Result of a cron job run."""
    run_id: str
    job_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    success: bool = False
    result: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class CronScheduler:
    """Scheduler for cron jobs."""
    
    def __init__(self):
        self._jobs: dict[str, CronJob] = {}
        self._results: list[CronRunResult] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
    
    def add_job(
        self,
        name: str,
        frequency: CronFrequency,
        action: str,
        config: Optional[dict[str, Any]] = None,
    ) -> CronJob:
        """Add a new cron job."""
        job = CronJob(
            job_id=f"cron_{uuid.uuid4().hex[:8]}",
            name=name,
            frequency=frequency,
            action=action,
            config=config or {},
            next_run=self._calculate_next_run(frequency),
        )
        self._jobs[job.job_id] = job
        return job
    
    def remove_job(self, job_id: str) -> bool:
        """Remove a cron job."""
        if job_id in self._jobs:
            del self._jobs[job_id]
            return True
        return False
    
    def enable_job(self, job_id: str) -> bool:
        """Enable a cron job."""
        job = self._jobs.get(job_id)
        if job:
            job.enabled = True
            return True
        return False
    
    def disable_job(self, job_id: str) -> bool:
        """Disable a cron job."""
        job = self._jobs.get(job_id)
        if job:
            job.enabled = False
            return True
        return False
    
    def get_jobs(self) -> list[CronJob]:
        """Get all cron jobs."""
        return list(self._jobs.values())
    
    def get_results(self, job_id: Optional[str] = None) -> list[CronRunResult]:
        """Get job run results."""
        if job_id:
            return [r for r in self._results if r.job_id == job_id]
        return list(self._results)
    
    def start(self):
        """Start the scheduler."""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
    
    def stop(self):
        """Stop the scheduler."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
    
    def _run_loop(self):
        """Main scheduler loop."""
        while self._running:
            now = datetime.now()
            
            for job in self._jobs.values():
                if not job.enabled:
                    continue
                
                if job.next_run and job.next_run <= now:
                    self._execute_job(job)
                    job.last_run = now
                    job.next_run = self._calculate_next_run(job.frequency)
            
            time.sleep(60)  # Check every minute
    
    def _execute_job(self, job: CronJob):
        """Execute a cron job."""
        run = CronRunResult(
            run_id=f"run_{uuid.uuid4().hex[:8]}",
            job_id=job.job_id,
            started_at=datetime.now(),
        )
        
        try:
            # Execute based on action type
            if job.action == "analyze":
                result = self._execute_analyze(job.config)
            elif job.action == "monitor":
                result = self._execute_monitor(job.config)
            elif job.action == "alert":
                result = self._execute_alert(job.config)
            else:
                result = {"error": f"Unknown action: {job.action}"}
            
            run.completed_at = datetime.now()
            run.success = True
            run.result = result
        except Exception as e:
            run.completed_at = datetime.now()
            run.success = False
            run.error = str(e)
        
        self._results.append(run)
    
    def _execute_analyze(self, config: dict[str, Any]) -> dict[str, Any]:
        """Execute an analyze job."""
        # Placeholder for actual analysis
        return {"status": "analyzed", "url": config.get("url", "")}
    
    def _execute_monitor(self, config: dict[str, Any]) -> dict[str, Any]:
        """Execute a monitor job."""
        return {"status": "monitored"}
    
    def _execute_alert(self, config: dict[str, Any]) -> dict[str, Any]:
        """Execute an alert job."""
        return {"status": "alerted"}
    
    def _calculate_next_run(self, frequency: CronFrequency) -> datetime:
        """Calculate next run time based on frequency."""
        now = datetime.now()
        
        if frequency == CronFrequency.HOURLY:
            return now + timedelta(hours=1)
        elif frequency == CronFrequency.DAILY:
            return now + timedelta(days=1)
        elif frequency == CronFrequency.WEEKLY:
            return now + timedelta(weeks=1)
        elif frequency == CronFrequency.MONTHLY:
            return now + timedelta(days=30)
        
        return now + timedelta(hours=1)


def create_default_scheduler() -> CronScheduler:
    """Create a scheduler with default jobs."""
    scheduler = CronScheduler()
    
    # Add default monitoring job
    scheduler.add_job(
        name="Daily Site Monitor",
        frequency=CronFrequency.DAILY,
        action="monitor",
        config={"check_health": True},
    )
    
    return scheduler
