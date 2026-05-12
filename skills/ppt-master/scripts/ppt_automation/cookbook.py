"""Theme cookbook loading for the automation pipeline."""

from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass
from pathlib import Path

from .config import SKILL_DIR

COOKBOOK_DIR = SKILL_DIR / "templates" / "cookbooks"
DEFAULT_THEME_ID = "default"
RANDOM_THEME_CHOICES = (
    DEFAULT_THEME_ID,
    "figma_65cm_default",
    "figma_colorblock_modern",
    "figma_lime_serif_grid",
)


@dataclass(frozen=True)
class Cookbook:
    """Resolved cookbook content and provenance."""

    id: str
    source: str
    text: str


@dataclass(frozen=True)
class CookbookSelection:
    """Resolved theme selection for one generation run."""

    theme_id: str
    cookbook: Cookbook | None
    random: bool


def _available_cookbook_names() -> list[str]:
    if not COOKBOOK_DIR.exists():
        return []
    names = {p.stem for p in COOKBOOK_DIR.glob("*.md")}
    names.update(p.name for p in COOKBOOK_DIR.iterdir() if p.is_dir())
    return sorted(names)


def _resolve_cookbook_raw(raw: str) -> Cookbook:
    """Resolve a cookbook by absolute path, relative path, or cookbook name."""

    candidates: list[Path] = []
    path = Path(raw)
    if path.is_absolute():
        candidates.append(path)
    else:
        candidates.extend(
            [
                Path.cwd() / path,
                COOKBOOK_DIR / path,
                COOKBOOK_DIR / f"{raw}.md",
            ]
        )

    for candidate in candidates:
        resolved = candidate
        if candidate.exists() and candidate.is_dir():
            nested_candidates = [
                candidate / f"{candidate.name}.md",
                candidate / "cookbook.md",
                candidate / "README.md",
            ]
            resolved = next((item for item in nested_candidates if item.exists() and item.is_file()), candidate)
        if resolved.exists() and resolved.is_file():
            text = resolved.read_text(encoding="utf-8", errors="replace").strip()
            cookbook_id = candidate.name if candidate.is_dir() else resolved.stem
            return Cookbook(id=cookbook_id, source=str(resolved), text=text)

    available = ", ".join(_available_cookbook_names())
    suffix = f" Available cookbooks: {available}" if available else ""
    raise FileNotFoundError(f"Cookbook not found: {raw}.{suffix}")


def resolve_cookbook_selection(value: str | None) -> CookbookSelection:
    """Resolve the active theme, randomly selecting a default style when omitted."""

    raw = (value or os.environ.get("PPT_MASTER_COOKBOOK") or "").strip()
    if raw.lower() in {"", "random", "auto"}:
        selected = secrets.choice(RANDOM_THEME_CHOICES)
        if selected == DEFAULT_THEME_ID:
            return CookbookSelection(theme_id=DEFAULT_THEME_ID, cookbook=None, random=True)
        cookbook = _resolve_cookbook_raw(selected)
        return CookbookSelection(theme_id=cookbook.id, cookbook=cookbook, random=True)

    if raw.lower() in {"none", "default", "off", "false", "0"}:
        return CookbookSelection(theme_id=DEFAULT_THEME_ID, cookbook=None, random=False)

    cookbook = _resolve_cookbook_raw(raw)
    return CookbookSelection(theme_id=cookbook.id, cookbook=cookbook, random=False)


def resolve_cookbook(value: str | None) -> Cookbook | None:
    """Resolve a cookbook by absolute path, relative path, or cookbook name."""

    return resolve_cookbook_selection(value).cookbook


def render_cookbook_context(cookbook: Cookbook | None) -> str:
    """Render cookbook text for prompt injection."""

    if cookbook is None:
        return ""
    return f"""
Theme Cookbook:
- cookbook_id: {cookbook.id}

```markdown
{cookbook.text}
```
"""


def write_project_cookbook(project_path: Path, cookbook: Cookbook | None) -> None:
    """Persist the resolved cookbook into the generated project."""

    if cookbook is None:
        return
    (project_path / "cookbook.md").write_text(cookbook.text + "\n", encoding="utf-8")
    (project_path / "cookbook_source.json").write_text(
        json.dumps({"id": cookbook.id, "source": cookbook.source}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_theme_selection(project_path: Path, selection: CookbookSelection) -> None:
    """Persist the theme chosen for this generation."""

    payload = {
        "theme_id": selection.theme_id,
        "random": selection.random,
        "cookbook_id": selection.cookbook.id if selection.cookbook else None,
        "cookbook_source": selection.cookbook.source if selection.cookbook else None,
        "choices": list(RANDOM_THEME_CHOICES),
    }
    (project_path / "theme_selection.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
