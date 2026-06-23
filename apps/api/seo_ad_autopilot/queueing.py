from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from collections import deque
from datetime import datetime, timezone, timedelta
from typing import Any, Deque, Optional
from urllib.parse import urlparse

from sqlalchemy import select

from .db import JobQueueRow, json_dump
from .models import WorkerJobStatus, new_id, utcnow


@dataclass
class WorkerJob:
    job_id: str
    project_id: str
    task_id: str
    stage: str
    payload: dict[str, Any]
    status: WorkerJobStatus = WorkerJobStatus.queued

    def fingerprint(self) -> str:
        return f"{self.project_id}:{self.task_id}:{self.stage}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "jobId": self.job_id,
            "projectId": self.project_id,
            "taskId": self.task_id,
            "stage": self.stage,
            "payload": self.payload,
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "WorkerJob":
        return cls(
            job_id=str(raw.get("jobId") or raw.get("job_id") or new_id("job")),
            project_id=str(raw.get("projectId") or raw.get("project_id") or ""),
            task_id=str(raw.get("taskId") or raw.get("task_id") or ""),
            stage=str(raw.get("stage") or ""),
            payload=dict(raw.get("payload") or {}),
            status=WorkerJobStatus(str(raw.get("status") or WorkerJobStatus.queued.value)),
        )


class BaseJobQueue:
    def enqueue(self, job: WorkerJob, delay_seconds: int = 0) -> bool:
        raise NotImplementedError

    def claim(self, limit: int = 50) -> list[WorkerJob]:
        raise NotImplementedError

    def complete(self, job: WorkerJob) -> None:
        raise NotImplementedError

    def fail(self, job: WorkerJob, error: str) -> None:
        raise NotImplementedError


class MemoryJobQueue(BaseJobQueue):
    def __init__(self) -> None:
        self._items: Deque[WorkerJob] = deque()
        self._active: set[str] = set()

    def enqueue(self, job: WorkerJob, delay_seconds: int = 0) -> bool:
        fingerprint = job.fingerprint()
        if fingerprint in self._active:
            return False
        if delay_seconds > 0:
            not_before = utcnow() + timedelta(seconds=max(0, int(delay_seconds)))
            job.payload["retryNotBefore"] = not_before.isoformat()
            job.payload["retryDelaySeconds"] = int(delay_seconds)
        self._active.add(fingerprint)
        self._items.append(job)
        return True

    def claim(self, limit: int = 50) -> list[WorkerJob]:
        claimed: list[WorkerJob] = []
        pending: Deque[WorkerJob] = deque()
        now = utcnow()
        while self._items and len(claimed) < limit:
            job = self._items.popleft()
            retry_not_before = str(job.payload.get("retryNotBefore") or "").strip()
            if retry_not_before:
                try:
                    due_at = datetime.fromisoformat(retry_not_before)
                    if due_at.tzinfo is None:
                        due_at = due_at.replace(tzinfo=timezone.utc)
                except ValueError:
                    due_at = now
                if due_at > now:
                    pending.append(job)
                    continue
            job.status = WorkerJobStatus.claimed
            claimed.append(job)
        while pending:
            self._items.appendleft(pending.pop())
        return claimed

    def complete(self, job: WorkerJob) -> None:
        job.status = WorkerJobStatus.completed
        self._active.discard(job.fingerprint())

    def fail(self, job: WorkerJob, error: str) -> None:
        job.status = WorkerJobStatus.failed
        job.payload["error"] = error
        self._active.discard(job.fingerprint())


class DatabaseJobQueue(BaseJobQueue):
    def __init__(self, database) -> None:
        self.database = database

    def enqueue(self, job: WorkerJob, delay_seconds: int = 0) -> bool:
        ready_at = utcnow() + timedelta(seconds=max(0, int(delay_seconds)))
        with self.database.session() as session:
            existing = session.scalars(
                select(JobQueueRow).where(
                    JobQueueRow.project_id == job.project_id,
                    JobQueueRow.task_id == job.task_id,
                    JobQueueRow.stage == job.stage,
                    JobQueueRow.status.in_([WorkerJobStatus.queued.value, WorkerJobStatus.claimed.value]),
                )
            ).first()
            if existing is not None:
                return False
            session.add(
                JobQueueRow(
                    id=job.job_id,
                    project_id=job.project_id,
                    task_id=job.task_id,
                    stage=job.stage,
                    status=job.status.value,
                    payload_json=json_dump(job.payload),
                    ready_at=ready_at,
                )
            )
        return True

    def claim(self, limit: int = 50) -> list[WorkerJob]:
        claimed: list[WorkerJob] = []
        with self.database.session() as session:
            rows = session.scalars(
                select(JobQueueRow)
                .where(JobQueueRow.status == WorkerJobStatus.queued.value, JobQueueRow.ready_at <= utcnow())
                .order_by(JobQueueRow.ready_at.asc(), JobQueueRow.created_at.asc())
                .limit(limit)
            ).all()
            for row in rows:
                row.status = WorkerJobStatus.claimed.value
                row.claimed_at = utcnow()
                row.updated_at = utcnow()
                session.add(row)
                claimed.append(
                    WorkerJob(
                        job_id=row.id,
                        project_id=row.project_id,
                        task_id=row.task_id,
                        stage=row.stage,
                        payload=dict(row.payload_json or {}),
                        status=WorkerJobStatus.claimed,
                    )
                )
        return claimed

    def complete(self, job: WorkerJob) -> None:
        with self.database.session() as session:
            row = session.get(JobQueueRow, job.job_id)
            if row is None:
                return
            row.status = WorkerJobStatus.completed.value
            row.finished_at = utcnow()
            row.updated_at = utcnow()
            session.add(row)

    def fail(self, job: WorkerJob, error: str) -> None:
        with self.database.session() as session:
            row = session.get(JobQueueRow, job.job_id)
            if row is None:
                return
            row.status = WorkerJobStatus.failed.value
            row.error_text = error
            row.finished_at = utcnow()
            row.updated_at = utcnow()
            session.add(row)


class RedisClient:
    def __init__(self, url: str, timeout: float = 2.0) -> None:
        parsed = urlparse(url)
        self.host = parsed.hostname or "127.0.0.1"
        self.port = parsed.port or 6379
        self.password = parsed.password
        self.db = int((parsed.path or "/0").lstrip("/") or 0)
        self.timeout = timeout

    def _encode(self, value: Any) -> bytes:
        if value is None:
            return b"$-1\r\n"
        if isinstance(value, bytes):
            data = value
        else:
            data = str(value).encode("utf-8")
        return b"$%d\r\n%b\r\n" % (len(data), data)

    def _command(self, *parts: Any) -> Any:
        payload = [f"*{len(parts)}\r\n".encode("utf-8")]
        for part in parts:
            if part is None:
                payload.append(b"$-1\r\n")
                continue
            data = part if isinstance(part, bytes) else str(part).encode("utf-8")
            payload.append(b"$%d\r\n%b\r\n" % (len(data), data))
        with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
            sock.settimeout(self.timeout)
            if self.password:
                self._read_response(sock, b"AUTH", self.password)
            if self.db:
                self._read_response(sock, b"SELECT", str(self.db))
            sock.sendall(b"".join(payload))
            return self._read_response(sock)

    def _readline(self, sock) -> bytes:
        chunks = []
        while True:
            char = sock.recv(1)
            if not char:
                raise ConnectionError("Redis connection closed")
            chunks.append(char)
            if b"".join(chunks).endswith(b"\r\n"):
                return b"".join(chunks[:-2])

    def _read_response(self, sock, *args) -> Any:
        if args:
            command = [f"*{len(args)}\r\n".encode("utf-8")]
            for arg in args:
                data = arg if isinstance(arg, bytes) else str(arg).encode("utf-8")
                command.append(b"$%d\r\n%b\r\n" % (len(data), data))
            sock.sendall(b"".join(command))
        prefix = sock.recv(1)
        if not prefix:
            raise ConnectionError("Redis connection closed")
        if prefix == b"+":
            return self._readline(sock).decode("utf-8")
        if prefix == b":":
            return int(self._readline(sock))
        if prefix == b"$":
            length = int(self._readline(sock))
            if length == -1:
                return None
            data = b""
            while len(data) < length + 2:
                data += sock.recv(length + 2 - len(data))
            return data[:-2].decode("utf-8")
        if prefix == b"*":
            count = int(self._readline(sock))
            return [self._read_response(sock) for _ in range(count)]
        if prefix == b"-":
            raise ConnectionError(self._readline(sock).decode("utf-8"))
        raise ConnectionError(f"Unknown Redis response prefix: {prefix!r}")

    def set_json(self, key: str, value: dict[str, Any]) -> None:
        self._command("SET", key, json.dumps(value, default=str))

    def get_json(self, key: str) -> Optional[dict[str, Any]]:
        raw = self._command("GET", key)
        if raw is None:
            return None
        return json.loads(raw)

    def delete(self, key: str) -> None:
        self._command("DEL", key)

    def setnx(self, key: str, value: str) -> bool:
        result = self._command("SETNX", key, value)
        return bool(int(result or 0))

    def ping(self) -> bool:
        result = self._command("PING")
        return str(result or "").upper() == "PONG"

    def llen(self, key: str) -> int:
        result = self._command("LLEN", key)
        return int(result or 0)

    def rpush(self, key: str, value: str) -> None:
        self._command("RPUSH", key, value)

    def lpop(self, key: str) -> Optional[str]:
        raw = self._command("LPOP", key)
        return raw if raw is None else str(raw)


class RedisJobQueue(BaseJobQueue):
    def __init__(self, redis_url: str, namespace: str = "seo_ad_autopilot") -> None:
        self.client = RedisClient(redis_url)
        self.namespace = namespace
        self.queue_key = f"{namespace}:job_queue"

    def _job_key(self, job_id: str) -> str:
        return f"{self.namespace}:job:{job_id}"

    def _fingerprint_key(self, job: WorkerJob) -> str:
        return f"{self.namespace}:jobfp:{job.fingerprint()}"

    def enqueue(self, job: WorkerJob, delay_seconds: int = 0) -> bool:
        if delay_seconds > 0:
            not_before = utcnow() + timedelta(seconds=max(0, int(delay_seconds)))
            job.payload["retryNotBefore"] = not_before.isoformat()
            job.payload["retryDelaySeconds"] = int(delay_seconds)
        fingerprint_key = self._fingerprint_key(job)
        if not self.client.setnx(fingerprint_key, job.job_id):
            return False
        self.client.set_json(self._job_key(job.job_id), job.to_dict())
        self.client.rpush(self.queue_key, json.dumps(job.to_dict(), default=str))
        return True

    def claim(self, limit: int = 50) -> list[WorkerJob]:
        claimed: list[WorkerJob] = []
        deferred: list[WorkerJob] = []
        now = utcnow()
        for _ in range(limit):
            raw = self.client.lpop(self.queue_key)
            if raw is None:
                break
            job = WorkerJob.from_dict(json.loads(raw))
            retry_not_before = str(job.payload.get("retryNotBefore") or "").strip()
            if retry_not_before:
                try:
                    due_at = datetime.fromisoformat(retry_not_before)
                    if due_at.tzinfo is None:
                        due_at = due_at.replace(tzinfo=timezone.utc)
                except ValueError:
                    due_at = now
                if due_at > now:
                    deferred.append(job)
                    continue
            job.status = WorkerJobStatus.claimed
            claimed.append(job)
            self.client.set_json(self._job_key(job.job_id), job.to_dict())
        for job in deferred:
            self.client.rpush(self.queue_key, json.dumps(job.to_dict(), default=str))
        return claimed

    def complete(self, job: WorkerJob) -> None:
        job.status = WorkerJobStatus.completed
        self.client.set_json(self._job_key(job.job_id), job.to_dict())
        self.client.delete(self._fingerprint_key(job))

    def fail(self, job: WorkerJob, error: str) -> None:
        job.status = WorkerJobStatus.failed
        job.payload["error"] = error
        self.client.set_json(self._job_key(job.job_id), job.to_dict())
        self.client.delete(self._fingerprint_key(job))


def build_job_queue(backend: str, database, redis_url: str | None = None) -> BaseJobQueue:
    normalized = backend.lower().strip()
    if normalized == "db":
        return DatabaseJobQueue(database)
    if normalized == "redis":
        return RedisJobQueue(redis_url or "redis://127.0.0.1:6379/0")
    return MemoryJobQueue()
