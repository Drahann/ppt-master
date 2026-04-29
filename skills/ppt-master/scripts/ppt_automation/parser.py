"""Input parsing for automation mode."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Slide:
    index: int
    title: str
    body: str
    raw_markdown: str
    slug: str
    svg_filename: str
    kind: str = "content"
    section_title: str | None = None

    @property
    def stem(self) -> str:
        return Path(self.svg_filename).stem

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["stem"] = self.stem
        return data


@dataclass(frozen=True)
class Deck:
    title: str
    front_matter: str
    slides: list[Slide]

    def to_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "front_matter": self.front_matter,
            "slide_count": len(self.slides),
            "slides": [slide.to_dict() for slide in self.slides],
        }


def safe_project_name(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in value.strip())
    safe = re.sub(r"_+", "_", safe).strip("._")
    return safe[:80] or "deck"


def slugify(value: str, fallback: str) -> str:
    text = value.strip().lower()
    chars: list[str] = []
    for ch in text:
        if ch.isalnum() or "\u4e00" <= ch <= "\u9fff":
            chars.append(ch)
        elif ch in "-_":
            chars.append(ch)
        else:
            chars.append("_")
    slug = re.sub(r"_+", "_", "".join(chars)).strip("_-")
    return slug[:48].strip("_-") or fallback


def make_slide(
    *,
    index: int,
    title: str,
    body: str,
    raw_markdown: str,
    kind: str,
    used_slugs: set[str],
    section_title: str | None = None,
    slug_hint: str | None = None,
) -> Slide:
    base_slug = slugify(slug_hint or title, f"slide_{index:02d}")
    slug = base_slug
    counter = 2
    while slug in used_slugs:
        slug = f"{base_slug}_{counter}"
        counter += 1
    used_slugs.add(slug)
    return Slide(
        index=index,
        title=title,
        body=body,
        raw_markdown=raw_markdown,
        slug=slug,
        svg_filename=f"{index:02d}_{slug}.svg",
        kind=kind,
        section_title=section_title,
    )


def parse_markdown_deck(markdown: str, max_slides: int | None = None) -> Deck:
    """Parse Markdown into cover, content slides, and a closing slide.

    Normal content slides are level-2 headings. The `创新技术` level-2 section
    is expanded so each level-3 heading becomes its own slide.
    """
    content = markdown.replace("\r\n", "\n").replace("\r", "\n")
    h1_match = re.search(r"(?m)^#(?!#)\s+(.+?)\s*$", content)
    title = h1_match.group(1).strip() if h1_match else "Untitled Deck"

    all_h2_matches = list(re.finditer(r"(?m)^##(?!#)\s+(.+?)\s*$", content))
    if not all_h2_matches:
        raise ValueError("Markdown must contain at least one level-2 heading (`##`) for slides.")

    if max_slides is not None and max_slides <= 0:
        raise ValueError("--max-slides must be greater than 0 when provided.")

    front_matter = content[: all_h2_matches[0].start()].strip()
    content_specs: list[dict[str, str | None]] = []

    for h2_index, match in enumerate(all_h2_matches):
        h2_title = match.group(1).strip()
        h2_end = all_h2_matches[h2_index + 1].start() if h2_index + 1 < len(all_h2_matches) else len(content)
        h2_body = content[match.end() : h2_end].strip()
        if h2_title == "创新技术":
            h3_matches = list(re.finditer(r"(?m)^###(?!#)\s+(.+?)\s*$", h2_body))
            if h3_matches:
                for h3_index, h3 in enumerate(h3_matches):
                    h3_title = h3.group(1).strip()
                    body_end = h3_matches[h3_index + 1].start() if h3_index + 1 < len(h3_matches) else len(h2_body)
                    h3_body = h2_body[h3.end() : body_end].strip()
                    content_specs.append(
                        {
                            "title": h3_title,
                            "body": h3_body,
                            "raw_markdown": f"## {h2_title}\n\n### {h3_title}\n\n{h3_body}".strip(),
                            "kind": "content",
                            "section_title": h2_title,
                        }
                    )
                continue
        content_specs.append(
            {
                "title": h2_title,
                "body": h2_body,
                "raw_markdown": f"## {h2_title}\n\n{h2_body}".strip(),
                "kind": "content",
                "section_title": None,
            }
        )

    if max_slides is not None:
        content_specs = content_specs[:max_slides]

    slides: list[Slide] = []
    used_slugs: set[str] = set()
    slides.append(
        make_slide(
            index=1,
            title=title,
            body="",
            raw_markdown=f"# {title}",
            kind="cover",
            used_slugs=used_slugs,
            slug_hint="cover",
        )
    )
    for spec in content_specs:
        slides.append(
            make_slide(
                index=len(slides) + 1,
                title=str(spec["title"]),
                body=str(spec["body"] or ""),
                raw_markdown=str(spec["raw_markdown"]),
                kind=str(spec["kind"]),
                section_title=spec["section_title"],
                used_slugs=used_slugs,
            )
        )
    slides.append(
        make_slide(
            index=len(slides) + 1,
            title="谢谢",
            body=f"{title}\n\n感谢聆听",
            raw_markdown=f"## 谢谢\n\n{title}\n\n感谢聆听",
            kind="closing",
            used_slugs=used_slugs,
            slug_hint="closing",
        )
    )

    return Deck(title=title, front_matter=front_matter, slides=slides)


def read_input_markdown(path: Path, json_field: str = "content") -> str:
    """Read Markdown directly or from a JSON string field."""
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")
    if path.suffix.lower() != ".json":
        return path.read_text(encoding="utf-8")

    data = json.loads(path.read_text(encoding="utf-8"))
    value: object = data
    for part in json_field.split("."):
        if not isinstance(value, dict) or part not in value:
            raise ValueError(f"JSON field not found: {json_field}")
        value = value[part]
    if not isinstance(value, str):
        raise ValueError(f"JSON field must be a string: {json_field}")
    return value
