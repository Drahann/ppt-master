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
    CLAUDE_FLASH_MODEL,
    CLAUDE_MODEL,
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    QWEN_BASE_URL,
    QWEN_MAX_TOKENS,
    QWEN_MODEL,
    REPO_ROOT,
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
    parser.add_argument("--renderer", default="claude", choices=["claude", "local"], help="SVG renderer: claude uses DeepSeek-backed Claude Code; local is deterministic smoke mode.")
    parser.add_argument("--dry-run", action="store_true", help="Create project structure, source, manifests, plan, and prompts only.")
    parser.add_argument("--max-slides", type=int, default=None, help="Limit parsed slides for smoke runs.")
    parser.add_argument("--no-quality-check", dest="quality_check", action="store_false", help="Skip svg_quality_checker.py.")
    parser.set_defaults(quality_check=True)
    parser.add_argument("--deepseek-api-key", default=None, help="DeepSeek key; prefer DEEPSEEK_API_KEY env var.")
    parser.add_argument("--deepseek-base-url", default=DEFAULT_BASE_URL, help="Anthropic-compatible base URL.")
    parser.add_argument("--deepseek-model", default=DEFAULT_MODEL, help="Model for direct DeepSeek calls.")
    parser.add_argument("--planner-provider", default="deepseek", choices=["deepseek", "qwen"], help="Provider for design_plan/spec_lock.")
    parser.add_argument("--notes-provider", default="deepseek", choices=["deepseek", "qwen"], help="Provider for speaker notes.")
    parser.add_argument("--qwen-api-key", default=None, help="Qwen/DashScope key; prefer DASHSCOPE_API_KEY env var.")
    parser.add_argument("--qwen-base-url", default=QWEN_BASE_URL, help="OpenAI-compatible DashScope base URL.")
    parser.add_argument("--qwen-model", default=QWEN_MODEL, help="Qwen model for planning and notes.")
    parser.add_argument("--qwen-max-tokens", type=int, default=QWEN_MAX_TOKENS, help="Max output tokens for Qwen planning/notes.")
    parser.add_argument("--claude-model", default=CLAUDE_MODEL, help="Model env value for Claude Code.")
    parser.add_argument("--claude-flash-model", default=CLAUDE_FLASH_MODEL, help="Haiku/subagent model env value for Claude Code.")
    parser.add_argument("--claude-effort", default="high", choices=["low", "medium", "high", "max"], help="CLAUDE_CODE_EFFORT_LEVEL for SVG generation.")
    parser.add_argument("--claude-timeout", type=int, default=600, help="Timeout per Claude SVG page in seconds.")
    parser.add_argument("--claude-retries", type=int, default=1, help="Retries per failed Claude SVG page.")
    parser.add_argument("--svg-workers", type=int, default=1, help="Parallel SVG batch workers. Default keeps sequential behavior.")
    parser.add_argument("--svg-batch-size", type=int, default=5, help="Slides per SVG batch when --svg-workers > 1.")
    parser.add_argument("--cache-prime", action="store_true", help="Prime provider context cache with the stable deck prefix before live generation.")
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
