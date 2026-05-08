#!/usr/bin/env python3
"""Normalize non-XML HTML named entities in SVG text.

Claude-style SVG output occasionally contains HTML-only named entities such as
``&minus;`` or ``&nbsp;``. XML parsers only accept the five predefined XML
entities plus numeric references, so this helper converts HTML named entities to
Unicode characters and escapes any remaining bare ampersands.
"""

from __future__ import annotations

import argparse
import re
import sys
from html.entities import html5
from pathlib import Path
from xml.etree import ElementTree as ET

XML_PREDEFINED_ENTITIES = {"amp", "lt", "gt", "quot", "apos"}
NAMED_ENTITY_RE = re.compile(r"&([A-Za-z][A-Za-z0-9]+);")
BARE_AMP_RE = re.compile(r"&(?!amp;|lt;|gt;|quot;|apos;|#[0-9]+;|#x[0-9A-Fa-f]+;)")
BARE_LT_RE = re.compile(r"<(?!/?[A-Za-z_][\w:.-]*(?:\s|/?>)|!--|\?xml|!\[CDATA\[)")
COMMENT_RE = re.compile(r"<!--(.*?)-->", re.S)
SPAN_OPEN_RE = re.compile(r"<span\b([^>]*)>", re.I)
SPAN_CLOSE_RE = re.compile(r"</span\s*>", re.I)
BROKEN_INLINE_OPEN_RE = re.compile(r"<\s+(text|tspan)\b", re.I)
BROKEN_INLINE_QUESTION_OPEN_RE = re.compile(r"\?\s+(tspan\b(?=[^<>]*>))", re.I)
BROKEN_INLINE_CLOSE_RE = re.compile(r"(?<!<)/\s*(text|tspan)\s*>", re.I)
ATTR_PAIR_RE = re.compile(r"(?=\b([A-Za-z_:][-A-Za-z0-9_:.]*)\s*=\s*(['\"])(.*?)\2)")
CSS_PAIR_RE = re.compile(r"\b([A-Za-z][-A-Za-z0-9]*)\s*:\s*([^;\"'>\s]+)")
TSPAN_SAFE_ATTRS = {
    "baseline-shift",
    "dx",
    "dy",
    "fill",
    "fill-opacity",
    "font-family",
    "font-size",
    "font-style",
    "font-weight",
    "letter-spacing",
    "opacity",
    "stroke",
    "stroke-width",
    "text-decoration",
    "x",
    "y",
}


def clean_xml_comments(text: str) -> str:
    """Make model-written SVG comments legal XML comments."""

    def replace_comment(match: re.Match[str]) -> str:
        body = match.group(1).replace("--", "-")
        if body.endswith("-"):
            body += " "
        return f"<!--{body}-->"

    return COMMENT_RE.sub(replace_comment, text)


def _clean_tspan_attr_value(value: str) -> str:
    return value.strip().strip("\"'").rstrip(";")


def _span_attrs_to_tspan_attrs(attr_text: str) -> str:
    attrs: dict[str, str] = {}

    for name, _quote, value in ATTR_PAIR_RE.findall(attr_text):
        normalized_name = name.lower()
        if normalized_name == "tspan":
            continue
        if normalized_name in TSPAN_SAFE_ATTRS:
            attrs[normalized_name] = _clean_tspan_attr_value(value)

    for name, value in CSS_PAIR_RE.findall(attr_text):
        normalized_name = name.lower()
        if normalized_name in TSPAN_SAFE_ATTRS:
            attrs[normalized_name] = _clean_tspan_attr_value(value)

    return " ".join(f'{name}="{value}"' for name, value in attrs.items() if value)


def repair_span_tspan_tags(text: str) -> str:
    """Convert model-written HTML span/tspan hybrids into valid SVG tspans."""

    def replace_open(match: re.Match[str]) -> str:
        attrs = _span_attrs_to_tspan_attrs(match.group(1))
        return f"<tspan {attrs}>" if attrs else "<tspan>"

    repaired = SPAN_OPEN_RE.sub(replace_open, text)
    return SPAN_CLOSE_RE.sub("</tspan>", repaired)


def repair_broken_inline_svg_tags(text: str) -> str:
    """Repair common model damage around SVG text/tspan tag delimiters."""

    repaired = BROKEN_INLINE_OPEN_RE.sub(lambda match: f"<{match.group(1)}", text)
    repaired = BROKEN_INLINE_QUESTION_OPEN_RE.sub(lambda match: f"?<{match.group(1)}", repaired)
    return BROKEN_INLINE_CLOSE_RE.sub(lambda match: f"</{match.group(1)}>", repaired)


def _html_entity_value(name: str) -> str | None:
    if name == "nbsp":
        return " "
    return html5.get(f"{name};")


def clean_svg_entities(text: str) -> str:
    """Return SVG/XML-safe text with HTML named entities normalized."""

    def replace_named(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in XML_PREDEFINED_ENTITIES:
            return match.group(0)
        value = _html_entity_value(name)
        if value is None:
            return f"&amp;{name};"
        return value

    cleaned = repair_span_tspan_tags(repair_broken_inline_svg_tags(clean_xml_comments(text)))
    cleaned = NAMED_ENTITY_RE.sub(replace_named, cleaned)
    cleaned = BARE_AMP_RE.sub("&amp;", cleaned)
    return BARE_LT_RE.sub("&lt;", cleaned)


def iter_svg_files(path: Path, recursive: bool) -> list[Path]:
    if path.is_file():
        return [path] if path.suffix.lower() == ".svg" else []
    if not path.is_dir():
        return []
    pattern = "**/*.svg" if recursive else "*.svg"
    return sorted(path.glob(pattern))


def process_file(path: Path, *, dry_run: bool, validate: bool) -> bool:
    original = path.read_text(encoding="utf-8", errors="replace")
    cleaned = clean_svg_entities(original)
    changed = cleaned != original
    if validate:
        ET.fromstring(cleaned)
    if changed and not dry_run:
        path.write_text(cleaned, encoding="utf-8")
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Normalize HTML named entities in SVG files.")
    parser.add_argument("path", help="SVG file or directory containing SVG files.")
    parser.add_argument("-r", "--recursive", action="store_true", help="Scan directories recursively.")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing files.")
    parser.add_argument("--validate", action="store_true", help="Validate cleaned SVG XML before writing.")
    args = parser.parse_args(argv)

    files = iter_svg_files(Path(args.path), args.recursive)
    if not files:
        print(f"No SVG files found: {args.path}", file=sys.stderr)
        return 1

    changed = 0
    for svg_file in files:
        try:
            if process_file(svg_file, dry_run=args.dry_run, validate=args.validate):
                changed += 1
                print(f"cleaned: {svg_file}")
        except Exception as exc:
            print(f"failed: {svg_file}: {exc}", file=sys.stderr)
            return 2

    print(f"checked={len(files)} changed={changed} dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
