#!/usr/bin/env python3
"""Thin CLI for the PPT Master automation pipeline."""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ppt_automation.config import (  # noqa: E402
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    QWEN_BASE_URL,
    QWEN_MAX_TOKENS,
    QWEN_MODEL,
    QWEN_TIMEOUT,
    REPO_ROOT,
    SVG_MODEL,
    SVG_REPAIR_MODEL,
)
from ppt_automation.pipeline import GenerationOptions, generate  # noqa: E402


def add_generate_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("generate", help="Generate a PPTX project from Markdown or JSON content.")
    parser.add_argument("input", help="Markdown file, or JSON file containing a Markdown string.")
    parser.add_argument("--json-field", default="content", help="Dot path for Markdown inside JSON input (default: content).")
    parser.add_argument("--project-name", default=None, help="Project name. Defaults to the first H1 title.")
    parser.add_argument("--projects-dir", default=str(REPO_ROOT / "projects"), help="Output projects directory.")
    parser.add_argument("--format", default="ppt169", help="Canvas format (default: ppt169).")
    parser.add_argument("--style", default="general", choices=["general", "consultant", "consultant-top"], help="Design style.")
    parser.add_argument("--cookbook", default=None, help="Theme cookbook name or path. Also reads PPT_MASTER_COOKBOOK if omitted.")
    parser.add_argument("--renderer", default="deepseek", choices=["deepseek", "local"], help="SVG renderer: deepseek uses direct Anthropic-compatible API; local is deterministic smoke mode.")
    parser.add_argument("--dry-run", action="store_true", help="Create project structure, source, manifests, plan, and prompts only.")
    parser.add_argument("--spec-only", action="store_true", help="Run live design_plan/spec_lock generation only, then stop before notes, SVG, quality check, and export.")
    parser.add_argument("--max-slides", type=int, default=None, help="Limit parsed slides for smoke runs.")
    parser.add_argument("--no-quality-check", dest="quality_check", action="store_false", help="Skip svg_quality_checker.py.")
    parser.set_defaults(quality_check=True)
    parser.add_argument("--deepseek-api-key", default=None, help="DeepSeek key; prefer DEEPSEEK_API_KEY env var.")
    parser.add_argument("--deepseek-base-url", default=DEFAULT_BASE_URL, help="Anthropic-compatible base URL.")
    parser.add_argument("--deepseek-model", default=DEFAULT_MODEL, help="Model for direct DeepSeek calls.")
    parser.add_argument("--planner-provider", default="qwen", choices=["deepseek", "qwen"], help="Provider for design_plan/spec_lock.")
    parser.add_argument("--notes-provider", default="qwen", choices=["deepseek", "qwen"], help="Provider for speaker notes.")
    parser.add_argument("--qwen-api-key", default=None, help="Qwen/DashScope key; prefer DASHSCOPE_API_KEY env var.")
    parser.add_argument("--qwen-base-url", default=QWEN_BASE_URL, help="OpenAI-compatible DashScope base URL.")
    parser.add_argument("--qwen-model", default=QWEN_MODEL, help="Qwen model for notes, or planning when --planner-provider qwen is selected.")
    parser.add_argument("--qwen-max-tokens", type=int, default=QWEN_MAX_TOKENS, help="Max output tokens for Qwen notes/planning requests.")
    parser.add_argument("--qwen-timeout", type=int, default=QWEN_TIMEOUT, help="Timeout per Qwen notes/planning request in seconds.")
    parser.add_argument("--svg-model", default=SVG_MODEL, help="DeepSeek model for direct SVG generation.")
    parser.add_argument("--svg-repair-model", default=SVG_REPAIR_MODEL, help="DeepSeek model for SVG syntax repair.")
    parser.add_argument("--svg-timeout", type=int, default=600, help="Timeout per direct SVG page request in seconds.")
    parser.add_argument("--svg-retries", type=int, default=1, help="Retries per failed direct SVG page.")
    parser.add_argument("--svg-workers", type=int, default=18, help="Parallel SVG slide workers.")
    parser.add_argument("--svg-batch-size", type=int, default=5, help="Slides per SVG batch when --svg-workers > 1.")
    parser.add_argument("--cache-prime", dest="cache_prime", action="store_true", default=None, help="Prime provider context cache with the stable deck prefix before live generation.")
    parser.add_argument("--no-cache-prime", dest="cache_prime", action="store_false", help="Disable provider context cache priming even if enabled by environment defaults.")
    parser.set_defaults(func=generate_command)


def generate_command(args: argparse.Namespace) -> None:
    try:
        result = generate(GenerationOptions.from_namespace(args))
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        sys.exit(1)
    print(result.to_json())
    sys.exit(0 if result.ok else 1)


def serve_command(args: argparse.Namespace) -> None:
    del args
    print(
        "The HTTP API service is intentionally deferred. "
        "Use `api_ppt.py generate` for the local script flow until the request/response protocol is finalized.",
        file=sys.stderr,
    )
    sys.exit(2)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="PPT Master automation local runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """\
            Examples:
              python skills/ppt-master/scripts/api_ppt.py generate input.md --project-name demo --renderer local
              python skills/ppt-master/scripts/api_ppt.py generate postppt.json --project-name demo --dry-run
              set DEEPSEEK_API_KEY=sk-...
              python skills/ppt-master/scripts/api_ppt.py generate input.md --project-name demo
            """
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_generate_parser(subparsers)
    serve = subparsers.add_parser("serve", help="Deferred placeholder for future HTTP API service.")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.set_defaults(func=serve_command)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
