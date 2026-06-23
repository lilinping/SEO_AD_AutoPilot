from __future__ import annotations

import argparse
import time
from typing import Sequence

from .models import WorkerRunOnceRequest
from .service import WorkflowService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SEO-AD AutoPilot worker")
    parser.add_argument("--once", action="store_true", help="Process jobs once and exit")
    parser.add_argument("--interval", type=int, default=10, help="Polling interval in seconds")
    parser.add_argument("--max-iterations", type=int, default=0, help="Maximum loop iterations in daemon mode (0 = unlimited)")
    parser.add_argument("--project-id", action="append", default=[], help="Target project id. Repeatable.")
    parser.add_argument("--claim-limit", type=int, default=200, help="Worker claim limit per tick")
    parser.add_argument("--exclude-approved-tasks", action="store_true", help="Skip approved task deploy/monitor processing")
    return parser


def _build_run_request(args: argparse.Namespace) -> WorkerRunOnceRequest:
    return WorkerRunOnceRequest(
        project_ids=list(args.project_id or []),
        include_approved_tasks=not bool(args.exclude_approved_tasks),
        claim_limit=max(1, int(args.claim_limit)),
    )


def run_worker(args: argparse.Namespace, service: WorkflowService) -> None:
    request = _build_run_request(args)
    if args.once:
        result = service.run_worker_once(request)
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
        return

    iteration = 0
    interval_seconds = max(1, int(args.interval))
    max_iterations = max(0, int(args.max_iterations))
    while True:
        result = service.run_worker_once(request)
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
        iteration += 1
        if max_iterations and iteration >= max_iterations:
            return
        time.sleep(interval_seconds)


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    service = WorkflowService()
    service.bootstrap()
    run_worker(args, service)


if __name__ == "__main__":
    main()
