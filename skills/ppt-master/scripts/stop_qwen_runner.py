#!/usr/bin/env python3
"""Stop qwen_ppt_runner jobs and their Qwen Code subprocess chain on Windows.

Usage:
    python3 skills/ppt-master/scripts/stop_qwen_runner.py
    python3 skills/ppt-master/scripts/stop_qwen_runner.py --match debugtxt
    python3 skills/ppt-master/scripts/stop_qwen_runner.py --include-orphans
    python3 skills/ppt-master/scripts/stop_qwen_runner.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--match",
        help="Only stop runner roots whose command line contains this substring.",
    )
    parser.add_argument(
        "--include-orphans",
        action="store_true",
        help="Also stop orphaned qwen.CMD / qwen-code node processes that are no longer attached to a runner root.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the processes that would be stopped without killing them.",
    )
    return parser.parse_args()


def run_powershell_json(command: str) -> Any:
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            command,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "PowerShell command failed")
    payload = completed.stdout.strip()
    if not payload:
        return []
    return json.loads(payload)


def list_processes() -> list[dict[str, Any]]:
    command = (
        "Get-CimInstance Win32_Process | "
        "Select-Object ProcessId,ParentProcessId,Name,CommandLine | "
        "ConvertTo-Json -Depth 4"
    )
    payload = run_powershell_json(command)
    if isinstance(payload, dict):
        return [payload]
    return payload


def normalize_process(proc: dict[str, Any]) -> dict[str, Any]:
    return {
        "pid": int(proc.get("ProcessId", 0) or 0),
        "ppid": int(proc.get("ParentProcessId", 0) or 0),
        "name": str(proc.get("Name") or ""),
        "command_line": str(proc.get("CommandLine") or ""),
    }


def is_runner_root(proc: dict[str, Any]) -> bool:
    return "qwen_ppt_runner.py" in proc["command_line"]


def is_qwen_subprocess(proc: dict[str, Any]) -> bool:
    cmd = proc["command_line"]
    return (
        "qwen.CMD" in cmd
        or "@qwen-code\\qwen-code\\cli.js" in cmd
        or "@qwen-code/qwen-code/cli.js" in cmd
    )


def collect_descendants(root_pid: int, by_parent: dict[int, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    stack = [root_pid]
    seen: set[int] = set()
    while stack:
        parent = stack.pop()
        for child in by_parent.get(parent, []):
            pid = child["pid"]
            if pid in seen:
                continue
            seen.add(pid)
            collected.append(child)
            stack.append(pid)
    return collected


def stop_pid(pid: int) -> None:
    completed = subprocess.run(
        ["taskkill", "/PID", str(pid), "/F", "/T"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode not in (0, 128):
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or f"taskkill failed for PID {pid}")


def main() -> None:
    args = parse_args()
    processes = [normalize_process(item) for item in list_processes()]
    by_parent: dict[int, list[dict[str, Any]]] = {}
    for proc in processes:
        by_parent.setdefault(proc["ppid"], []).append(proc)

    roots = [proc for proc in processes if is_runner_root(proc)]
    if args.match:
        roots = [proc for proc in roots if args.match in proc["command_line"]]

    selected: dict[int, dict[str, Any]] = {proc["pid"]: proc for proc in roots}
    for root in roots:
        for child in collect_descendants(root["pid"], by_parent):
            selected[child["pid"]] = child

    if args.include_orphans:
        for proc in processes:
            if proc["pid"] in selected:
                continue
            if not is_qwen_subprocess(proc):
                continue
            if args.match and args.match not in proc["command_line"]:
                continue
            selected[proc["pid"]] = proc

    selected_list = sorted(selected.values(), key=lambda item: (item["ppid"], item["pid"]))
    payload = {
        "dry_run": args.dry_run,
        "match": args.match,
        "include_orphans": args.include_orphans,
        "count": len(selected_list),
        "processes": selected_list,
    }

    if args.dry_run or not selected_list:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    for proc in sorted(selected_list, key=lambda item: item["pid"], reverse=True):
        stop_pid(proc["pid"])

    payload["stopped"] = True
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pragma: no cover - operational script
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2))
        sys.exit(1)
