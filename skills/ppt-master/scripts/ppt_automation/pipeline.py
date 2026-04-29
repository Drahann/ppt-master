"""End-to-end automation pipeline."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

from .config import (
    CLAUDE_FLASH_MODEL,
    CLAUDE_MODEL,
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    QWEN_BASE_URL,
    QWEN_MAX_TOKENS,
    QWEN_MODEL,
    QWEN_TIMEOUT,
    REPO_ROOT,
    TOOLS_DIR,
    normalized_format,
)
from .assets import download_and_rewrite_markdown_images
from .errors import GenerationError
from .parser import parse_markdown_deck, read_input_markdown, safe_project_name
from .planner import (
    DEEPSEEK_SYSTEM,
    build_notes_prompt,
    call_deepseek_anthropic,
    call_qwen_openai,
    generate_plan,
    prime_deepseek_cache,
    resolve_api_key,
    resolve_qwen_api_key,
)
from .project import RunResult, create_project, write_manifest, write_result, write_source
from .svg_generator import deterministic_notes, generate_svg_files, write_prompt_files
from .usage import UsageLogger


@dataclass
class GenerationOptions:
    input: str
    json_field: str = "content"
    project_name: str | None = None
    projects_dir: str = str(REPO_ROOT / "projects")
    format: str = "ppt169"
    style: str = "general"
    renderer: str = "claude"
    dry_run: bool = False
    max_slides: int | None = None
    quality_check: bool = True
    deepseek_api_key: str | None = None
    deepseek_base_url: str = DEFAULT_BASE_URL
    deepseek_model: str = DEFAULT_MODEL
    planner_provider: str = "deepseek"
    notes_provider: str = "deepseek"
    qwen_api_key: str | None = None
    qwen_base_url: str = QWEN_BASE_URL
    qwen_model: str = QWEN_MODEL
    qwen_max_tokens: int = QWEN_MAX_TOKENS
    qwen_timeout: int = QWEN_TIMEOUT
    claude_model: str = CLAUDE_MODEL
    claude_flash_model: str = CLAUDE_FLASH_MODEL
    claude_effort: str = "high"
    claude_timeout: int = 600
    claude_retries: int = 1
    svg_workers: int = 1
    svg_batch_size: int = 5
    cache_prime: bool = False

    @classmethod
    def from_namespace(cls, args: argparse.Namespace) -> "GenerationOptions":
        return cls(**{field: getattr(args, field) for field in cls.__dataclass_fields__})


def run_command(args: list[str], cwd: Path, allow_failure: bool = False) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(args, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if completed.returncode != 0 and not allow_failure:
        detail = (completed.stderr or completed.stdout).strip()
        raise GenerationError(f"Command failed: {' '.join(args)}\n{detail}")
    return completed


def run_quality_check(project_path: Path, canvas_format: str, enabled: bool) -> tuple[dict[str, int], Path | None]:
    if not enabled:
        return {"errors": 0, "warnings": 0}, None
    report_path = project_path / "svg_quality_report.txt"
    completed = run_command(
        [
            sys.executable,
            str(TOOLS_DIR / "svg_quality_checker.py"),
            str(project_path),
            "--format",
            normalized_format(canvas_format),
            "--export",
            "--output",
            str(report_path),
        ],
        cwd=REPO_ROOT,
        allow_failure=True,
    )
    (project_path / "logs" / "svg_quality_checker.stdout.txt").write_text(completed.stdout, encoding="utf-8")
    if completed.stderr:
        (project_path / "logs" / "svg_quality_checker.stderr.txt").write_text(completed.stderr, encoding="utf-8")
    return parse_quality_summary(report_path), report_path


def clean_svg_output_entities(project_path: Path) -> None:
    """Normalize HTML named entities in generated SVG files before QA/export."""

    svg_dir = project_path / "svg_output"
    if not svg_dir.exists():
        return
    completed = run_command(
        [
            sys.executable,
            str(TOOLS_DIR / "clean_svg_entities.py"),
            str(svg_dir),
            "--validate",
        ],
        cwd=REPO_ROOT,
        allow_failure=True,
    )
    (project_path / "logs" / "clean_svg_entities.stdout.txt").write_text(completed.stdout, encoding="utf-8")
    if completed.stderr:
        (project_path / "logs" / "clean_svg_entities.stderr.txt").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise GenerationError(f"SVG entity cleanup failed:\n{detail}")


def parse_quality_summary(report_path: Path) -> dict[str, int]:
    if not report_path.exists():
        return {"errors": 0, "warnings": 0}
    text = report_path.read_text(encoding="utf-8", errors="replace")
    errors = re.search(r"With errors:\s*(\d+)", text)
    warnings = re.search(r"With warnings:\s*(\d+)", text)
    return {
        "errors": int(errors.group(1)) if errors else 0,
        "warnings": int(warnings.group(1)) if warnings else 0,
    }


def run_chart_scan(project_path: Path) -> list[str]:
    svg_dir = project_path / "svg_output"
    marked: list[str] = []
    chart_like: list[str] = []
    pattern = re.compile(
        r"barGrad|bar-[0-9]|groupGrad|stackShadow|donut-sectors|sector-[0-9]|"
        r"pieChart|radarChart|areaGrad|lineGrad|dotShadow|pointShadow|hbarGrad|"
        r"waterfallGrad|paretoGrad"
    )
    for svg_file in sorted(svg_dir.glob("*.svg")):
        text = svg_file.read_text(encoding="utf-8", errors="replace")
        if "chart-plot-area" in text:
            marked.append(svg_file.name)
        if pattern.search(text):
            chart_like.append(svg_file.name)
    (project_path / "logs" / "chart_scan.txt").write_text(
        "\n".join(
            [
                "Chart calibration scan",
                f"marked chart pages: {', '.join(marked) if marked else 'none'}",
                f"chart-like pages: {', '.join(chart_like) if chart_like else 'none'}",
                "v1 does not auto-calibrate chart coordinates.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return [f"Chart-like SVG lacks chart-plot-area marker: {name}" for name in sorted(set(chart_like) - set(marked))]


def generate_notes(project_path: Path, options: GenerationOptions, logger: UsageLogger) -> None:
    if options.renderer == "local":
        deck_json = json.loads((project_path / "slide_manifest.json").read_text(encoding="utf-8"))
        from .parser import Deck, Slide

        deck = Deck(
            title=deck_json["title"],
            front_matter=deck_json.get("front_matter", ""),
            slides=[
                Slide(
                    **{
                        k: v
                        for k, v in slide.items()
                        if k
                        in {
                            "index",
                            "title",
                            "body",
                            "raw_markdown",
                            "slug",
                            "svg_filename",
                            "kind",
                            "section_title",
                        }
                    }
                )
                for slide in deck_json["slides"]
            ],
        )
        (project_path / "notes" / "total.md").write_text(deterministic_notes(deck), encoding="utf-8")
        return

    prompt = build_notes_prompt(parse_markdown_deck((project_path / "sources" / "input.md").read_text(encoding="utf-8"), options.max_slides), options.format, options.style)
    if options.notes_provider == "qwen":
        model = options.qwen_model
        text, usage = call_qwen_openai(
            api_key=resolve_qwen_api_key(options.qwen_api_key),
            base_url=options.qwen_base_url,
            model=options.qwen_model,
            prompt=prompt,
            system=DEEPSEEK_SYSTEM,
            max_tokens=options.qwen_max_tokens,
            timeout=options.qwen_timeout,
        )
    else:
        model = options.deepseek_model
        text, usage = call_deepseek_anthropic(
            api_key=resolve_api_key(options.deepseek_api_key),
            base_url=options.deepseek_base_url,
            model=options.deepseek_model,
            prompt=prompt,
            system=DEEPSEEK_SYSTEM,
            max_tokens=12000,
        )
    logger.log_transcript(
        f"{options.notes_provider}_notes",
        system=DEEPSEEK_SYSTEM,
        prompt=prompt,
        response=text,
        metadata={"model": model, "usage": usage},
    )
    (project_path / "notes" / "total.md").write_text(text.strip() + "\n", encoding="utf-8")
    logger.log(f"{options.notes_provider}_notes", usage=usage, input_chars=len(prompt), output_chars=len(text))


def postprocess_and_export(project_path: Path) -> tuple[str | None, str | None]:
    run_command([sys.executable, str(TOOLS_DIR / "total_md_split.py"), str(project_path)], cwd=REPO_ROOT)
    run_command([sys.executable, str(TOOLS_DIR / "finalize_svg.py"), str(project_path)], cwd=REPO_ROOT)
    validate_svg_directory(project_path / "svg_final")
    before = set((project_path / "exports").glob("*.pptx"))
    run_command([sys.executable, str(TOOLS_DIR / "svg_to_pptx.py"), str(project_path), "-s", "final"], cwd=REPO_ROOT)
    after = sorted(set((project_path / "exports").glob("*.pptx")) - before, key=lambda p: p.stat().st_mtime)
    native = [p for p in after if not p.stem.endswith("_svg")]
    legacy = [p for p in after if p.stem.endswith("_svg")]
    return (str(native[-1]) if native else None, str(legacy[-1]) if legacy else None)


def validate_svg_directory(svg_dir: Path) -> None:
    errors: list[str] = []
    for svg_file in sorted(svg_dir.glob("*.svg")):
        try:
            ET.parse(svg_file)
        except ET.ParseError as exc:
            errors.append(f"{svg_file.name}: {exc}")
    if errors:
        raise GenerationError("Invalid SVG XML before PPTX export:\n" + "\n".join(errors[:10]))


def generate(options: GenerationOptions) -> RunResult:
    raw_markdown = read_input_markdown(Path(options.input), options.json_field)
    initial_deck = parse_markdown_deck(raw_markdown, max_slides=options.max_slides)
    project_name = options.project_name or safe_project_name(initial_deck.title)
    canvas_format = normalized_format(options.format)
    project_path = create_project(project_name, canvas_format, Path(options.projects_dir))
    logger = UsageLogger(project_path)

    try:
        markdown, image_assets = download_and_rewrite_markdown_images(raw_markdown, project_path)
        deck = parse_markdown_deck(markdown, max_slides=options.max_slides)
        if image_assets:
            logger.log(
                "input_images",
                downloaded=sum(1 for asset in image_assets if asset.status == "downloaded"),
                ignored=sum(1 for asset in image_assets if asset.status == "ignored"),
                failed=sum(1 for asset in image_assets if asset.status == "failed"),
            )
        write_source(project_path, markdown)
        write_manifest(project_path, deck)
        if options.cache_prime and options.renderer != "local" and not options.dry_run:
            prime_deepseek_cache(
                deck=deck,
                canvas_format=canvas_format,
                style=options.style,
                api_key=options.deepseek_api_key,
                base_url=options.deepseek_base_url,
                model=options.deepseek_model,
                logger=logger,
            )
        generate_plan(
            project_path=project_path,
            project_name=project_name,
            canvas_format=canvas_format,
            style=options.style,
            deck=deck,
            renderer="local" if options.dry_run else options.renderer,
            api_key=options.deepseek_api_key,
            base_url=options.deepseek_base_url,
            model=options.deepseek_model,
            provider=options.planner_provider,
            qwen_api_key=options.qwen_api_key,
            qwen_base_url=options.qwen_base_url,
            qwen_model=options.qwen_model,
            qwen_max_tokens=options.qwen_max_tokens,
            qwen_timeout=options.qwen_timeout,
            logger=logger,
        )
        write_prompt_files(project_path, deck, canvas_format, options.style)
        if options.dry_run:
            result = RunResult(ok=True, project_path=str(project_path), slides=len(deck.slides), dry_run=True, renderer=options.renderer)
            write_result(project_path, result)
            return result

        with ThreadPoolExecutor(max_workers=1) as notes_executor:
            logger.log("notes_parallel", event="start")
            notes_future = notes_executor.submit(generate_notes, project_path, options, logger)
            generate_svg_files(
                project_path=project_path,
                deck=deck,
                canvas_format=canvas_format,
                style=options.style,
                renderer=options.renderer,
                deepseek_api_key=options.deepseek_api_key,
                deepseek_base_url=options.deepseek_base_url,
                claude_model=options.claude_model,
                claude_flash_model=options.claude_flash_model,
                claude_effort=options.claude_effort,
                claude_timeout=options.claude_timeout,
                claude_retries=options.claude_retries,
                svg_workers=options.svg_workers,
                svg_batch_size=options.svg_batch_size,
                cache_prime=options.cache_prime,
                logger=logger,
            )
            clean_svg_output_entities(project_path)
            quality, quality_report = run_quality_check(project_path, canvas_format, options.quality_check)
            warnings = run_chart_scan(project_path)
            notes_future.result()
            logger.log("notes_parallel", event="finish")
        pptx_path, svg_pptx_path = postprocess_and_export(project_path)
        result = RunResult(
            ok=bool(pptx_path and svg_pptx_path),
            project_path=str(project_path),
            pptx_path=pptx_path,
            svg_pptx_path=svg_pptx_path,
            quality_report_path=str(quality_report) if quality_report else None,
            quality=quality,
            slides=len(deck.slides),
            dry_run=False,
            renderer=options.renderer,
            warnings=warnings,
        )
        write_result(project_path, result)
        return result
    except Exception as exc:
        result = RunResult(
            ok=False,
            project_path=str(project_path),
            slides=len(initial_deck.slides),
            dry_run=options.dry_run,
            renderer=options.renderer,
            error=str(exc),
        )
        write_result(project_path, result)
        raise
