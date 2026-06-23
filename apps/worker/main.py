from __future__ import annotations

import argparse
import json
import os
import signal
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional, Sequence

from apps.api.seo_ad_autopilot.models import WorkerRunOnceRequest, WorkerRunOnceResult
from apps.api.seo_ad_autopilot.service import WorkflowService


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_int(value: Any, fallback: int, minimum: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = fallback
    return max(minimum, parsed)


@dataclass
class WorkerRuntimeState:
    started_at: str = field(default_factory=_utc_now_iso)
    last_tick_at: Optional[str] = None
    status: str = "starting"
    processed: int = 0
    enqueued: int = 0
    claimed: int = 0
    skipped_duplicates: int = 0
    due_projects: int = 0
    failures: int = 0
    last_error: Optional[str] = None
    targets: list[str] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def update(self, result: WorkerRunOnceResult) -> None:
        with self.lock:
            self.last_tick_at = _utc_now_iso()
            self.status = "running"
            self.processed = int(result.processed)
            self.enqueued = int(result.enqueued)
            self.claimed = int(result.claimed)
            self.skipped_duplicates = int(result.skipped_duplicates)
            self.due_projects = int(result.due_projects)
            self.targets = list(result.target_project_ids)
            self.last_error = None

    def mark_failure(self, message: str) -> None:
        with self.lock:
            self.last_tick_at = _utc_now_iso()
            self.status = "degraded"
            self.failures += 1
            self.last_error = message

    def mark_stopped(self) -> None:
        with self.lock:
            self.status = "stopped"

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "startedAt": self.started_at,
                "lastTickAt": self.last_tick_at,
                "status": self.status,
                "processed": self.processed,
                "enqueued": self.enqueued,
                "claimed": self.claimed,
                "skippedDuplicates": self.skipped_duplicates,
                "dueProjects": self.due_projects,
                "targets": list(self.targets),
                "failures": self.failures,
                "lastError": self.last_error,
            }


def _build_run_request(args: argparse.Namespace) -> WorkerRunOnceRequest:
    return WorkerRunOnceRequest(
        project_ids=list(args.project_id or []),
        include_approved_tasks=not bool(args.exclude_approved_tasks),
        claim_limit=max(1, int(args.claim_limit)),
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SEO-AD AutoPilot worker service")
    parser.add_argument("--once", action="store_true", help="Process jobs once and exit.")
    parser.add_argument("--interval", type=int, default=10, help="Polling interval in seconds.")
    parser.add_argument("--max-iterations", type=int, default=0, help="Maximum loop iterations (0 means unlimited).")
    parser.add_argument("--project-id", action="append", default=[], help="Target project id. Repeatable.")
    parser.add_argument("--claim-limit", type=int, default=200, help="Worker claim limit per tick.")
    parser.add_argument("--exclude-approved-tasks", action="store_true", help="Skip approved task deploy/monitor processing.")
    parser.add_argument("--max-failures", type=int, default=0, help="Maximum tolerated run failures before exit (0 means unlimited).")
    parser.add_argument("--health-host", default=os.getenv("SEO_AD_BOT_WORKER_HEALTH_HOST", "127.0.0.1"), help="Health server host.")
    parser.add_argument(
        "--health-port",
        type=int,
        default=_safe_int(os.getenv("SEO_AD_BOT_WORKER_HEALTH_PORT", "0"), 0, minimum=0),
        help="Health server port (0 disables health endpoint).",
    )
    parser.add_argument("--pid-file", default=str(os.getenv("SEO_AD_BOT_WORKER_PID_FILE", "")).strip(), help="Optional pid file path.")
    parser.add_argument("--state-file", default=str(os.getenv("SEO_AD_BOT_WORKER_STATE_FILE", "")).strip(), help="Optional runtime state output path.")
    return parser


def _persist_text(path: str, content: str) -> None:
    if not path:
        return
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _persist_state(path: str, state: WorkerRuntimeState) -> None:
    if not path:
        return
    _persist_text(path, json.dumps(state.snapshot(), ensure_ascii=False))


def _print_result(result: WorkerRunOnceResult) -> None:
    print(
        "processed={processed} enqueued={enqueued} claimed={claimed} "
        "skippedDuplicates={skipped} dueProjects={due} targets={targets}".format(
            processed=result.processed,
            enqueued=result.enqueued,
            claimed=result.claimed,
            skipped=result.skipped_duplicates,
            due=result.due_projects,
            targets=",".join(result.target_project_ids) if result.target_project_ids else "all",
        )
    )


def _create_health_server(host: str, port: int, state: WorkerRuntimeState) -> ThreadingHTTPServer:
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            payload = state.snapshot()
            if self.path == "/healthz":
                code = 200 if payload.get("status") in {"running", "starting"} else 503
            elif self.path == "/status":
                code = 200
            else:
                code = 404
                payload = {"error": "not found"}
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return

    return ThreadingHTTPServer((host, int(port)), _Handler)


def run_service(args: argparse.Namespace, service: WorkflowService) -> int:
    request = _build_run_request(args)
    runtime_state = WorkerRuntimeState(status="running")
    stop_event = threading.Event()

    if args.pid_file:
        _persist_text(args.pid_file, str(os.getpid()))
    _persist_state(args.state_file, runtime_state)

    health_server: Optional[ThreadingHTTPServer] = None
    health_thread: Optional[threading.Thread] = None
    health_port = _safe_int(args.health_port, 0, minimum=0)
    if health_port > 0:
        health_server = _create_health_server(str(args.health_host), health_port, runtime_state)
        health_thread = threading.Thread(target=health_server.serve_forever, daemon=True)
        health_thread.start()

    def _shutdown(signum: int, _frame: Any) -> None:
        stop_event.set()
        runtime_state.mark_stopped()
        _persist_state(args.state_file, runtime_state)
        if health_server is not None:
            health_server.shutdown()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    exit_code = 0
    try:
        if args.once:
            result = service.run_worker_once(request)
            runtime_state.update(result)
            _persist_state(args.state_file, runtime_state)
            _print_result(result)
            return 0

        interval_seconds = max(1, int(args.interval))
        max_iterations = _safe_int(args.max_iterations, 0, minimum=0)
        max_failures = _safe_int(args.max_failures, 0, minimum=0)
        iteration = 0
        while not stop_event.is_set():
            try:
                result = service.run_worker_once(request)
                runtime_state.update(result)
                _persist_state(args.state_file, runtime_state)
                _print_result(result)
            except Exception as exc:
                runtime_state.mark_failure(str(exc))
                _persist_state(args.state_file, runtime_state)
                if max_failures and runtime_state.failures >= max_failures:
                    exit_code = 1
                    break
            iteration += 1
            if max_iterations and iteration >= max_iterations:
                break
            stop_event.wait(interval_seconds)
    finally:
        runtime_state.mark_stopped()
        _persist_state(args.state_file, runtime_state)
        if health_server is not None:
            health_server.shutdown()
            health_server.server_close()
        if health_thread is not None:
            health_thread.join(timeout=1)
    return exit_code


def main(argv: Sequence[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)
    service = WorkflowService()
    service.bootstrap()
    raise SystemExit(run_service(args, service))


if __name__ == "__main__":
    main()
