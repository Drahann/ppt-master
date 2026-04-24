#!/usr/bin/env python3
"""Async stress harness for ppt-master.

This submits N async jobs to /api/generate-ppt, polls /api/jobs/{job_id}
until each job reaches a terminal state, snapshots /metrics during the run,
and writes per-job plus aggregate summaries under tmp/.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import threading
import time
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_BASE_URL = "http://localhost:3001"
DEFAULT_POSTPPT_CANDIDATES = (
    REPO_ROOT / "postppt.json",
    REPO_ROOT.parent / "postppt.json",
    Path.home() / "AIPPT_CLI" / "ppt-master" / "postppt.json",
    Path.home() / "AIPPT_CLI" / "rag-agent" / "rag-agent" / "postppt.json",
)
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


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def print_flush(message: str) -> None:
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


def resolve_postppt_path(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if path.exists():
            return path
        raise FileNotFoundError(f"postppt.json not found: {path}")
    for candidate in DEFAULT_POSTPPT_CANDIDATES:
        if candidate.exists():
            return candidate.resolve()
    raise FileNotFoundError("postppt.json not found in default locations")


def load_postppt(postppt_path: Path) -> tuple[dict[str, Any], str]:
    payload = json.loads(postppt_path.read_text(encoding="utf-8"))
    content = str(payload.get("content") or "")
    if not content.strip():
        raise RuntimeError(f"content missing in {postppt_path}")
    return payload, content


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


def build_payload(
    *,
    report_id: str,
    title: str,
    content: str,
    batch_mode: str,
    batch_size: int,
    parallel_batch_workers: int,
    batch_partition: str,
    spec_model: str,
    notes_model: str,
    response_mode: str,
    callback_mode: str,
) -> dict[str, Any]:
    return {
        "report_id": report_id,
        "title": title,
        "content": content,
        "batchMode": batch_mode,
        "batchSize": batch_size,
        "parallelBatchWorkers": parallel_batch_workers,
        "batchPartition": batch_partition,
        "specModel": spec_model,
        "notesModel": notes_model,
        "responseMode": response_mode,
        "callbackMode": callback_mode,
    }


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    index = (len(ordered) - 1) * p
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    fraction = index - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def compact_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    jobs = metrics.get("jobs") or {}
    llm_budget = metrics.get("llmBudget") or {}
    svg_budget = metrics.get("svgBudget") or {}
    llm_slots = metrics.get("llmSlots") or {}
    svg_slots = llm_slots.get("svg") or {}
    system = metrics.get("system") or {}
    return {
        "captured_at": metrics.get("captured_at"),
        "active_jobs": jobs.get("active_count"),
        "completed_jobs": jobs.get("total_completed"),
        "failed_jobs": jobs.get("total_failed"),
        "active_avg_elapsed_seconds": jobs.get("active_avg_elapsed_seconds"),
        "live_spec_tpm_60s": llm_budget.get("live_spec_tpm_60s"),
        "live_svg_tpm_60s": llm_budget.get("live_svg_tpm_60s"),
        "live_notes_tpm_60s": llm_budget.get("live_notes_tpm_60s"),
        "live_svg_events_60s": llm_budget.get("live_svg_events_60s"),
        "svg_dynamic_limit": llm_budget.get("dynamic_svg_limit"),
        "svg_slot_active": svg_slots.get("active"),
        "svg_slot_limit": svg_slots.get("limit"),
        "svg_slot_waiting": svg_slots.get("waiting"),
        "svg_active_leases": svg_budget.get("active_leases"),
        "svg_denied_starts": svg_budget.get("denied_starts"),
        "svg_granted_starts": svg_budget.get("granted_starts"),
        "child_processes": system.get("child_processes"),
        "cpu_percent": system.get("cpu_percent"),
        "mem_rss_mb": system.get("mem_rss_mb"),
    }


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve_log_dir() -> Path:
    suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    candidates = [
        REPO_ROOT / "tmp",
        Path(tempfile.gettempdir()),
    ]
    custom_root = os.getenv("PPT_STRESS_LOG_ROOT")
    if custom_root and custom_root.strip():
        candidates.insert(0, Path(custom_root).expanduser())

    for root in candidates:
        try:
            root.mkdir(parents=True, exist_ok=True)
            log_dir = root / f"ppt_async_stress_{suffix}"
            log_dir.mkdir(parents=True, exist_ok=True)
            return log_dir
        except OSError:
            continue

    raise RuntimeError(
        "Unable to create a writable stress log directory. "
        "Set PPT_STRESS_LOG_ROOT to a writable path and retry."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Async stress harness for ppt-master")
    parser.add_argument("concurrency", type=int, nargs="?", default=3, help="number of concurrent jobs to submit")
    parser.add_argument("base_url", nargs="?", default=DEFAULT_BASE_URL, help="base URL, e.g. http://localhost:3001")
    parser.add_argument("postppt_json", nargs="?", default=None, help="optional postppt.json path")
    parser.add_argument("--poll-seconds", type=int, default=env_int("POLL_SECONDS", 10, minimum=1))
    parser.add_argument("--metrics-seconds", type=int, default=env_int("METRICS_SECONDS", 30, minimum=1))
    parser.add_argument("--job-timeout-seconds", type=int, default=env_int("JOB_TIMEOUT_SECONDS", 7200, minimum=60))
    parser.add_argument("--min-success", type=int, default=env_int("MIN_SUCCESS", 0, minimum=0))
    args = parser.parse_args()

    batch_mode = env_str("BATCH_MODE", "parallel")
    batch_size = env_int("BATCH_SIZE", 8, minimum=1)
    parallel_batch_workers = env_int("PARALLEL_BATCH_WORKERS", 7, minimum=1)
    batch_partition = env_str("BATCH_PARTITION", "fixed")
    spec_model = env_str("SPEC_MODEL", "qwen3.6-plus")
    notes_model = env_str("NOTES_MODEL", "qwen3.6-flash")
    stagger_seconds = env_int("STAGGER_SECONDS", 0, minimum=0)
    response_mode = env_str("RESPONSE_MODE", "async")
    callback_mode = env_str("CALLBACK_MODE", "none")

    if response_mode != "async":
        raise RuntimeError("stress_test_async.py expects RESPONSE_MODE=async")

    base_url = args.base_url.rstrip("/")
    api_url = f"{base_url}/api/generate-ppt"
    metrics_url = f"{base_url}/metrics"

    postppt_path = resolve_postppt_path(args.postppt_json)
    postppt_payload, content = load_postppt(postppt_path)
    source_title = extract_title(postppt_payload, "async stress")

    health_status, health_payload = http_json(f"{base_url}/healthz", timeout=10)
    if health_status != 200:
        raise RuntimeError(f"Service health check failed: HTTP {health_status} {health_payload}")

    log_dir = resolve_log_dir()
    metrics_jsonl_path = log_dir / "metrics.jsonl"

    print_flush("=" * 72)
    print_flush("ppt-master async stress harness")
    print_flush(f"start:       {now_text()}")
    print_flush(f"concurrency: {args.concurrency}")
    print_flush(f"api:         {api_url}")
    print_flush(f"metrics:     {metrics_url}")
    print_flush(f"content:     {postppt_path}")
    print_flush(f"title:       {source_title}")
    print_flush(f"batch:       {batch_mode} / size={batch_size} / workers={parallel_batch_workers} / partition={batch_partition}")
    print_flush(f"mode:        response={response_mode} / callback={callback_mode}")
    print_flush(f"log dir:     {log_dir}")
    print_flush("=" * 72)

    stop_metrics = threading.Event()

    def metrics_sampler() -> None:
        while not stop_metrics.is_set():
            try:
                status, payload = http_json(metrics_url, timeout=10)
                if status == 200 and isinstance(payload, dict):
                    snapshot = compact_metrics(payload)
                    with metrics_jsonl_path.open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps(snapshot, ensure_ascii=False) + "\n")
                    print_flush(
                        f"[metrics {snapshot.get('captured_at')}] "
                        f"active_jobs={snapshot.get('active_jobs')} "
                        f"live_spec_tpm_60s={snapshot.get('live_spec_tpm_60s')} "
                        f"live_svg_tpm_60s={snapshot.get('live_svg_tpm_60s')} "
                        f"live_notes_tpm_60s={snapshot.get('live_notes_tpm_60s')} "
                        f"svg_active_leases={snapshot.get('svg_active_leases')} "
                        f"svg_denied_starts={snapshot.get('svg_denied_starts')}"
                    )
            except Exception as exc:
                print_flush(f"[metrics] failed: {exc}")
            stop_metrics.wait(args.metrics_seconds)

    metrics_thread = threading.Thread(target=metrics_sampler, name="ppt-stress-metrics", daemon=True)
    metrics_thread.start()

    job_records: dict[str, dict[str, Any]] = {}

    def submit_task(index: int) -> tuple[str, dict[str, Any]]:
        report_id = f"async_stress_{int(time.time())}_{index}"
        payload = build_payload(
            report_id=report_id,
            title=f"{source_title} async stress task {index}",
            content=content,
            batch_mode=batch_mode,
            batch_size=batch_size,
            parallel_batch_workers=parallel_batch_workers,
            batch_partition=batch_partition,
            spec_model=spec_model,
            notes_model=notes_model,
            response_mode=response_mode,
            callback_mode=callback_mode,
        )
        started_at = time.time()
        status, body = http_json(api_url, method="POST", payload=payload, timeout=60)
        if status != 200 or not isinstance(body, dict):
            raise RuntimeError(f"submit failed for task {index}: HTTP {status} body={body}")
        job_id = str(body.get("job_id") or "").strip()
        polling_url = str(body.get("pollingUrl") or "").strip()
        if not job_id or not polling_url:
            raise RuntimeError(f"submit missing job_id/pollingUrl for task {index}: {body}")
        task_dir = log_dir / f"task_{index:02d}"
        task_dir.mkdir(parents=True, exist_ok=True)
        write_json(task_dir / "request.json", payload)
        write_json(task_dir / "submit_response.json", body)
        record = {
            "task_index": index,
            "report_id": report_id,
            "job_id": job_id,
            "polling_url": urllib.parse.urljoin(base_url + "/", polling_url.lstrip("/")),
            "submit_elapsed_seconds": round(time.time() - started_at, 2),
            "submitted_at": iso_now(),
            "task_dir": str(task_dir),
        }
        print_flush(
            f"[submit task {index:02d}] job_id={job_id} submit_elapsed={record['submit_elapsed_seconds']}s polling={record['polling_url']}"
        )
        return job_id, record

    try:
        print_flush("[submit] creating async jobs")
        with ThreadPoolExecutor(max_workers=max(1, min(args.concurrency, 8))) as executor:
            future_map = {}
            for index in range(1, args.concurrency + 1):
                future = executor.submit(submit_task, index)
                future_map[future] = index
                if stagger_seconds > 0 and index < args.concurrency:
                    time.sleep(stagger_seconds)
            for future in future_map:
                job_id, record = future.result()
                job_records[job_id] = record

        pending = set(job_records.keys())
        last_states: dict[str, str] = {}
        started_polling = time.time()

        print_flush("[poll] waiting for terminal states")
        while pending:
            completed_this_round: list[str] = []
            for job_id in list(pending):
                record = job_records[job_id]
                status_code, body = http_json(record["polling_url"], timeout=30)
                if status_code != 200 or not isinstance(body, dict):
                    print_flush(f"[poll {job_id}] HTTP {status_code} body={body}")
                    continue
                task_dir = Path(record["task_dir"])
                write_json(task_dir / "latest_job_record.json", body)
                state = str(body.get("status") or body.get("stage") or "unknown")
                if last_states.get(job_id) != state:
                    print_flush(f"[poll task {record['task_index']:02d}] job_id={job_id} state={state}")
                    last_states[job_id] = state
                if state in TERMINAL_STATES:
                    record["terminal_record"] = body
                    record["terminal_state"] = state
                    record["finished_at"] = iso_now()
                    completed_this_round.append(job_id)
            for job_id in completed_this_round:
                pending.discard(job_id)
            if not pending:
                break
            if time.time() - started_polling > args.job_timeout_seconds:
                raise RuntimeError(
                    f"Polling timed out after {args.job_timeout_seconds}s with {len(pending)} jobs still pending"
                )
            time.sleep(args.poll_seconds)

        terminal_records = []
        for job_id, record in sorted(job_records.items(), key=lambda item: item[1]["task_index"]):
            terminal = record.get("terminal_record") or {}
            result = terminal.get("result") if isinstance(terminal.get("result"), dict) else {}
            created_at = float(terminal.get("created_at") or 0)
            started_at = float(terminal.get("started_at") or 0)
            finished_at = float(terminal.get("finished_at") or 0)
            queue_wait = round(max(0.0, started_at - created_at), 1) if created_at and started_at else 0.0
            total_elapsed = round(max(0.0, finished_at - created_at), 1) if created_at and finished_at else 0.0
            run_elapsed = round(max(0.0, finished_at - started_at), 1) if started_at and finished_at else 0.0
            terminal_records.append(
                {
                    "task_index": record["task_index"],
                    "report_id": record["report_id"],
                    "job_id": job_id,
                    "status": record.get("terminal_state"),
                    "queue_wait_seconds": queue_wait,
                    "run_elapsed_seconds": run_elapsed,
                    "total_elapsed_seconds": total_elapsed,
                    "slideCount": (result or {}).get("slideCount"),
                    "pptUrl": (result or {}).get("pptUrl"),
                    "error": terminal.get("error"),
                }
            )

        write_json(log_dir / "summary.json", {"generated_at": iso_now(), "jobs": terminal_records})

        total_elapsed_values = [float(item["total_elapsed_seconds"]) for item in terminal_records if item["total_elapsed_seconds"]]
        success_count = sum(1 for item in terminal_records if item["status"] == "succeeded")
        failed_count = sum(1 for item in terminal_records if item["status"] != "succeeded")

        print_flush("")
        print_flush("=" * 72)
        print_flush("summary")
        print_flush(f"success={success_count} failed={failed_count} total={len(terminal_records)}")
        min_success = args.min_success if args.min_success > 0 else len(terminal_records)
        print_flush(f"min_success_required={min_success}")
        if total_elapsed_values:
            print_flush(
                "elapsed_total_seconds "
                f"p50={round(statistics.median(total_elapsed_values),1)} "
                f"p90={round(percentile(total_elapsed_values, 0.9),1)} "
                f"p99={round(percentile(total_elapsed_values, 0.99),1)}"
            )
        for item in terminal_records:
            print_flush(
                f"[task {item['task_index']:02d}] {item['status']} "
                f"queue={item['queue_wait_seconds']}s run={item['run_elapsed_seconds']}s total={item['total_elapsed_seconds']}s "
                f"slides={item['slideCount']} error={item['error']}"
            )
        print_flush(f"artifacts: {log_dir}")
        print_flush("=" * 72)

        return 0 if success_count >= min_success else 1
    finally:
        stop_metrics.set()
        metrics_thread.join(timeout=5)


if __name__ == "__main__":
    sys.exit(main())
