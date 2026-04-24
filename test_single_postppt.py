#!/usr/bin/env python3
"""Submit one ppt-master generation job using ../postppt.json.

Examples:
  python test_single_postppt.py --dry-run
  python test_single_postppt.py --base-url http://localhost:3001
  python test_single_postppt.py --response-mode sync --callback-mode none
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_POSTPPT_PATH = REPO_ROOT.parent / "postppt.json"
DEFAULT_BASE_URL = "http://localhost:3001"
TERMINAL_STATES = {"succeeded", "failed", "cancelled"}


def env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip() or default


def env_int(name: str, default: int, *, minimum: int = 0) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return max(minimum, int(raw))
    except ValueError:
        return default


def iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def print_flush(message: str = "") -> None:
    print(message, flush=True)


def http_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: int = 30,
) -> tuple[int, dict[str, Any] | str]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(getattr(response, "status", 200))
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = exc.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"HTTP request failed for {url}: {exc}") from exc
    try:
        return status, json.loads(body)
    except json.JSONDecodeError:
        return status, body


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve_log_dir() -> Path:
    candidates = [REPO_ROOT / "tmp", Path(tempfile.gettempdir())]
    custom_root = os.getenv("PPT_SINGLE_LOG_ROOT")
    if custom_root and custom_root.strip():
        candidates.insert(0, Path(custom_root).expanduser())

    for root in candidates:
        try:
            root.mkdir(parents=True, exist_ok=True)
            log_dir = root / f"ppt_single_postppt_{timestamp()}"
            log_dir.mkdir(parents=True, exist_ok=True)
            return log_dir
        except OSError:
            continue
    raise RuntimeError("Unable to create log directory. Set PPT_SINGLE_LOG_ROOT to a writable path.")


def load_source_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"postppt.json not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"postppt.json must contain a JSON object: {path}")
    content = str(payload.get("content") or "")
    if not content.strip():
        raise RuntimeError(f"content missing in {path}")
    return payload


def extract_title(payload: dict[str, Any], fallback: str) -> str:
    raw_title = payload.get("title")
    if isinstance(raw_title, str):
        title = raw_title.strip()
        if title:
            return title
    if isinstance(raw_title, list):
        for item in raw_title:
            if isinstance(item, dict):
                title = str(item.get("sub_answer") or "").strip()
                if title:
                    return title
        flattened = " - ".join(str(item).strip() for item in raw_title if str(item).strip())
        if flattened:
            return flattened
    elif raw_title is not None:
        title = str(raw_title).strip()
        if title:
            return title

    for line in str(payload.get("content") or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            title = stripped[2:].strip()
            if title:
                return title
    return fallback


def build_request_payload(args: argparse.Namespace, source_payload: dict[str, Any]) -> dict[str, Any]:
    payload = dict(source_payload)
    explicit_report_id = args.report_id.strip()
    if explicit_report_id:
        payload["report_id"] = explicit_report_id
    elif not args.preserve_report_id:
        payload["report_id"] = f"single_postppt_{timestamp()}"
    elif not str(payload.get("report_id") or "").strip():
        payload["report_id"] = f"single_postppt_{timestamp()}"

    payload["responseMode"] = args.response_mode
    payload["callbackMode"] = args.callback_mode
    payload["batchMode"] = args.batch_mode
    payload["batchSize"] = args.batch_size
    payload["parallelBatchWorkers"] = args.parallel_batch_workers
    payload["batchPartition"] = args.batch_partition
    if args.spec_model:
        payload["specModel"] = args.spec_model
    if args.notes_model:
        payload["notesModel"] = args.notes_model
    return payload


def summarize_terminal(record: dict[str, Any]) -> dict[str, Any]:
    result = record.get("result") if isinstance(record.get("result"), dict) else {}
    created_at = float(record.get("created_at") or 0)
    started_at = float(record.get("started_at") or 0)
    finished_at = float(record.get("finished_at") or 0)
    return {
        "status": record.get("status") or record.get("stage"),
        "queue_wait_seconds": round(max(0.0, started_at - created_at), 1) if created_at and started_at else 0.0,
        "run_elapsed_seconds": round(max(0.0, finished_at - started_at), 1) if started_at and finished_at else 0.0,
        "total_elapsed_seconds": round(max(0.0, finished_at - created_at), 1) if created_at and finished_at else 0.0,
        "slideCount": result.get("slideCount"),
        "pptUrl": result.get("pptUrl"),
        "error": record.get("error"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Submit one ppt-master job using ../postppt.json")
    parser.add_argument("--base-url", default=env_str("PPT_API_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--postppt-json", default=str(DEFAULT_POSTPPT_PATH))
    parser.add_argument("--response-mode", choices=["sync", "async"], default=env_str("RESPONSE_MODE", "async"))
    parser.add_argument("--callback-mode", choices=["auto", "defer", "none"], default=env_str("CALLBACK_MODE", "none"))
    parser.add_argument("--report-id", default=env_str("REPORT_ID", ""))
    parser.add_argument("--preserve-report-id", action="store_true", help="reuse report_id from postppt.json")
    parser.add_argument(
        "--batch-mode",
        choices=["auto", "always", "never", "parallel"],
        default=env_str("BATCH_MODE", "parallel"),
    )
    parser.add_argument("--batch-size", type=int, default=env_int("BATCH_SIZE", 8, minimum=1))
    parser.add_argument("--parallel-batch-workers", type=int, default=env_int("PARALLEL_BATCH_WORKERS", 3, minimum=1))
    parser.add_argument("--batch-partition", default=env_str("BATCH_PARTITION", "anchor_even"))
    parser.add_argument("--spec-model", default=env_str("SPEC_MODEL", "qwen3.6-plus"))
    parser.add_argument("--notes-model", default=env_str("NOTES_MODEL", "qwen3.6-flash"))
    parser.add_argument("--poll-seconds", type=int, default=env_int("POLL_SECONDS", 10, minimum=1))
    parser.add_argument("--job-timeout-seconds", type=int, default=env_int("JOB_TIMEOUT_SECONDS", 7200, minimum=60))
    parser.add_argument("--no-poll", action="store_true", help="submit async job and exit without polling")
    parser.add_argument("--dry-run", action="store_true", help="write request JSON without calling the API")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    api_url = f"{base_url}/api/generate-ppt"
    postppt_path = Path(args.postppt_json).expanduser().resolve()
    source_payload = load_source_payload(postppt_path)
    request_payload = build_request_payload(args, source_payload)
    log_dir = resolve_log_dir()
    write_json(log_dir / "request.json", request_payload)

    print_flush("=" * 72)
    print_flush("ppt-master single postppt test")
    print_flush(f"cwd:        {Path.cwd()}")
    print_flush(f"repo root:  {REPO_ROOT}")
    print_flush(f"postppt:    {postppt_path}")
    print_flush(f"api:        {api_url}")
    print_flush(f"report_id:  {request_payload['report_id']}")
    print_flush(f"title:      {extract_title(request_payload, request_payload['report_id'])}")
    print_flush(f"mode:       response={args.response_mode} callback={args.callback_mode}")
    print_flush(
        f"batch:      {args.batch_mode} size={args.batch_size} "
        f"workers={args.parallel_batch_workers} partition={args.batch_partition}"
    )
    print_flush(f"log dir:    {log_dir}")
    print_flush("=" * 72)

    if args.dry_run:
        print_flush("[dry-run] wrote request.json; no API call was made")
        return 0

    health_status, health_payload = http_json(f"{base_url}/healthz", timeout=10)
    if health_status != 200:
        write_json(log_dir / "health_response.json", health_payload)
        raise RuntimeError(f"Service health check failed: HTTP {health_status} {health_payload}")

    print_flush("[submit] sending single generation request")
    started_at = time.time()
    status, body = http_json(api_url, method="POST", payload=request_payload, timeout=60)
    submit_elapsed = round(time.time() - started_at, 2)
    write_json(log_dir / "submit_response.json", body)
    if status != 200 or not isinstance(body, dict):
        raise RuntimeError(f"Submit failed: HTTP {status} body={body}")
    print_flush(f"[submit] HTTP {status} elapsed={submit_elapsed}s")

    if args.response_mode == "sync":
        summary = {
            "generated_at": iso_now(),
            "http_status": status,
            "submit_elapsed_seconds": submit_elapsed,
            "success": body.get("success"),
            "slideCount": body.get("slideCount"),
            "pptUrl": body.get("pptUrl"),
            "error": body.get("error"),
        }
        write_json(log_dir / "summary.json", summary)
        print_flush(f"[sync] success={summary['success']} slides={summary['slideCount']} pptUrl={summary['pptUrl']}")
        print_flush(f"artifacts: {log_dir}")
        return 0 if body.get("success") else 1

    job_id = str(body.get("job_id") or "").strip()
    polling_url = str(body.get("pollingUrl") or "").strip()
    if not job_id or not polling_url:
        raise RuntimeError(f"Async submit response missing job_id/pollingUrl: {body}")

    absolute_polling_url = urllib.parse.urljoin(base_url + "/", polling_url.lstrip("/"))
    print_flush(f"[async] job_id={job_id} polling={absolute_polling_url}")
    if args.no_poll:
        write_json(
            log_dir / "summary.json",
            {"generated_at": iso_now(), "job_id": job_id, "polling_url": absolute_polling_url},
        )
        print_flush(f"artifacts: {log_dir}")
        return 0

    print_flush("[poll] waiting for terminal state")
    last_state = ""
    started_polling = time.time()
    while True:
        status_code, job_record = http_json(absolute_polling_url, timeout=30)
        if status_code != 200 or not isinstance(job_record, dict):
            print_flush(f"[poll] HTTP {status_code} body={job_record}")
        else:
            write_json(log_dir / "latest_job_record.json", job_record)
            state = str(job_record.get("status") or job_record.get("stage") or "unknown")
            if state != last_state:
                print_flush(f"[poll] state={state}")
                last_state = state
            if state in TERMINAL_STATES:
                summary = summarize_terminal(job_record)
                summary["generated_at"] = iso_now()
                summary["job_id"] = job_id
                summary["polling_url"] = absolute_polling_url
                write_json(log_dir / "terminal_job_record.json", job_record)
                write_json(log_dir / "summary.json", summary)
                print_flush(
                    f"[done] status={summary['status']} queue={summary['queue_wait_seconds']}s "
                    f"run={summary['run_elapsed_seconds']}s total={summary['total_elapsed_seconds']}s "
                    f"slides={summary['slideCount']} error={summary['error']}"
                )
                print_flush(f"pptUrl: {summary['pptUrl']}")
                print_flush(f"artifacts: {log_dir}")
                return 0 if state == "succeeded" else 1

        if time.time() - started_polling > args.job_timeout_seconds:
            raise RuntimeError(f"Polling timed out after {args.job_timeout_seconds}s for job_id={job_id}")
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    sys.exit(main())
