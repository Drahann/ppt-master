"""Theme cookbook loading for the automation pipeline."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from .config import SKILL_DIR

COOKBOOK_DIR = SKILL_DIR / "templates" / "cookbooks"


@dataclass(frozen=True)
class Cookbook:
    """Resolved cookbook content and provenance."""

    id: str
    source: str
    text: str


def resolve_cookbook(value: str | None) -> Cookbook | None:
    """Resolve a cookbook by absolute path, relative path, or cookbook name."""

    raw = (value or os.environ.get("PPT_MASTER_COOKBOOK") or "").strip()
    if not raw:
        return None

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
        if candidate.exists() and candidate.is_file():
            text = candidate.read_text(encoding="utf-8", errors="replace").strip()
            cookbook_id = candidate.stem
            return Cookbook(id=cookbook_id, source=str(candidate), text=text)

    available = ", ".join(sorted(p.stem for p in COOKBOOK_DIR.glob("*.md"))) if COOKBOOK_DIR.exists() else ""
    suffix = f" Available cookbooks: {available}" if available else ""
    raise FileNotFoundError(f"Cookbook not found: {raw}.{suffix}")


def render_cookbook_context(cookbook: Cookbook | None) -> str:
    """Render cookbook text for prompt injection."""

    if cookbook is None:
        return ""
    return f"""
Theme Cookbook:
- cookbook_id: {cookbook.id}
- source: {cookbook.source}

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
