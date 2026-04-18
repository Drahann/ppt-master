#!/usr/bin/env python3
"""
PPT Master - SVG Auto Repair Tool

Deterministic script-based SVG repair for three categories:
  1. Pie/donut chart geometry (C7 arc fixes)
  2. Title icon position standardization
  3. SVG format/syntax error correction

Usage:
    python3 scripts/svg_auto_repair.py <project_path>
    python3 scripts/svg_auto_repair.py <project_path> --dry-run
"""

import json
import math
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from html import unescape
from pathlib import Path
from typing import Any


# ────────────────────────────────────────────────────────────────
# Repair 1: Pie / Donut Chart Geometry (C7)
# ────────────────────────────────────────────────────────────────

def _repair_arc_geometry(content: str) -> tuple[str, list[str]]:
    """Fix arc endpoint coordinates using trigonometric recalculation.

    Parses donut/pie sector paths of the form:
        M sx,sy A R,R ... ex,ey L ix,iy A r,r ... iex,iey Z
    Detects the chart center from mask circles or endpoint averaging,
    then snaps every arc endpoint to lie exactly on its declared radius.
    """
    fixes: list[str] = []

    # Detect mask circles (donut center)
    circle_pattern = re.compile(
        r'<circle[^>]*cx="([\d.]+)"[^>]*cy="([\d.]+)"[^>]*r="([\d.]+)"'
    )
    circles = circle_pattern.findall(content)

    # Full sector path regex
    sector_pattern = re.compile(
        r'(<path[^>]*\bd=")'
        r'(M\s+([\d.]+)\s*,\s*([\d.]+)\s+'
        r'A\s+([\d.]+)\s*,\s*[\d.]+\s+[\d.]+\s+([\d,]+)\s+([\d.]+)\s*,\s*([\d.]+)\s+'
        r'L\s+([\d.]+)\s*,\s*([\d.]+)\s+'
        r'A\s+([\d.]+)\s*,\s*[\d.]+\s+[\d.]+\s+([\d,]+)\s+([\d.]+)\s*,\s*([\d.]+))'
        r'(\s*Z[^"]*")',
        re.IGNORECASE,
    )

    sectors = list(sector_pattern.finditer(content))
    if len(sectors) < 2:
        return content, fixes

    # Determine chart center from mask circle or endpoint average
    chart_cx, chart_cy = None, None
    for cx_s, cy_s, cr_s in circles:
        cr = float(cr_s)
        if cr < 200:
            chart_cx, chart_cy = float(cx_s), float(cy_s)
            break

    if chart_cx is None:
        pts = []
        for m in sectors:
            pts.append((float(m.group(3)), float(m.group(4))))
            pts.append((float(m.group(7)), float(m.group(8))))
        if len(pts) >= 3:
            chart_cx = sum(p[0] for p in pts) / len(pts)
            chart_cy = sum(p[1] for p in pts) / len(pts)

    if chart_cx is None:
        return content, fixes

    TOLERANCE = 5

    def snap(px: float, py: float, r: float) -> tuple[float, float, bool]:
        dist = math.sqrt((px - chart_cx) ** 2 + (py - chart_cy) ** 2)
        if abs(dist - r) <= TOLERANCE:
            return px, py, False
        angle = math.atan2(py - chart_cy, px - chart_cx)
        return (
            round(chart_cx + r * math.cos(angle), 1),
            round(chart_cy + r * math.sin(angle), 1),
            True,
        )

    # Process in reverse to keep match positions stable
    for m in reversed(sectors):
        mx, my = float(m.group(3)), float(m.group(4))
        outer_r = float(m.group(5))
        outer_flags = m.group(6)
        oex, oey = float(m.group(7)), float(m.group(8))
        isx, isy = float(m.group(9)), float(m.group(10))
        inner_r = float(m.group(11))
        inner_flags = m.group(12)
        iex, iey = float(m.group(13)), float(m.group(14))

        nmx, nmy, c1 = snap(mx, my, outer_r)
        noex, noey, c2 = snap(oex, oey, outer_r)
        nisx, nisy, c3 = snap(isx, isy, inner_r)
        niex, niey, c4 = snap(iex, iey, inner_r)

        if not any([c1, c2, c3, c4]):
            continue

        new_d = (
            f"M {nmx},{nmy} "
            f"A {outer_r},{outer_r} 0 {outer_flags} {noex},{noey} "
            f"L {nisx},{nisy} "
            f"A {inner_r},{inner_r} 0 {inner_flags} {niex},{niey}"
        )
        full_old = m.group(0)
        full_new = m.group(1) + new_d + m.group(15)
        content = content[:m.start()] + full_new + content[m.end():]
        fixes.append(f"Arc fix: snapped sector endpoints to radius (center {chart_cx:.0f},{chart_cy:.0f})")

    # Fix mask circle radius to match inner arc radius
    arc_cmd_pattern = re.compile(
        r'A\s+([\d.]+)\s*,\s*([\d.]+)\s+[\d.]+\s+[\d,]+\s+[\d.]+\s*,\s*[\d.]+'
    )
    multi_arc_paths = re.findall(r'd="([^"]*A[^"]*A[^"]*)"', content)
    donut_inner_radii: set[float] = set()
    for path_d in multi_arc_paths:
        arcs = arc_cmd_pattern.findall(path_d)
        radii = {float(rx) for rx, _ in arcs}
        if len(radii) == 2:
            donut_inner_radii.add(min(radii))

    for cx_s, cy_s, cr_s in circles:
        cr = float(cr_s)
        for inner_r in donut_inner_radii:
            if abs(cr - inner_r) > 2 and cr < inner_r * 2:
                old = f'r="{cr_s}"'
                new = f'r="{inner_r}"'
                # Only fix the specific circle
                pattern = re.compile(
                    rf'(<circle[^>]*cx="{re.escape(cx_s)}"[^>]*cy="{re.escape(cy_s)}"[^>]*)r="{re.escape(cr_s)}"'
                )
                content, n = pattern.subn(rf'\g<1>r="{inner_r}"', content, count=1)
                if n > 0:
                    fixes.append(f"Mask circle fix: r={cr_s} → r={inner_r}")

    return content, fixes


# ────────────────────────────────────────────────────────────────
# Repair 2: Title Icon Position Standardization
# ────────────────────────────────────────────────────────────────

def _format_num(value: float) -> str:
    """Format SVG numbers without unnecessary trailing zeroes."""
    rounded = round(value, 1)
    if abs(rounded - round(rounded)) < 0.05:
        return str(int(round(rounded)))
    return f"{rounded:.1f}"


def _get_attr_float(attrs: str, name: str) -> float | None:
    match = re.search(rf'\b{name}="([\d.]+)"', attrs)
    return float(match.group(1)) if match else None


def _estimate_text_width(text: str, font_size: float) -> float:
    """Estimate the visual width of a title for icon re-anchoring."""
    clean = re.sub(r"<[^>]+>", "", unescape(text or "")).strip()
    width_units = 0.0

    for ch in clean:
        if ch.isspace():
            width_units += 0.30
        elif unicodedata.east_asian_width(ch) in {"W", "F"}:
            width_units += 0.92
        elif ch.isdigit():
            width_units += 0.56
        elif ch.isalpha() and ord(ch) < 128:
            width_units += 0.62
        elif ch in ".,:;!|/\\'\"`-()[]{}":
            width_units += 0.34
        else:
            width_units += 0.58

    return round(width_units * font_size, 1)


def _repair_title_icon_position(
    content: str,
    anchor: dict[str, Any] | None,
) -> tuple[str, list[str]]:
    """Standardize title icon position based on anchor context.

    Repairs the first title icon inside the header whether it is emitted as a
    <use data-icon="..."> element or as an inline <g transform="translate(...)">
    icon group.
    """
    fixes: list[str] = []
    if anchor is None:
        return content, fixes

    geom = anchor.get("immutable_geometry", {})
    icon_rules = anchor.get("icon_rules", {})

    expected_title_x = geom.get("title_text", {}).get("x", 80)
    expected_title_y = geom.get("title_text", {}).get("y", 70)
    expected_font_size = geom.get("title_text", {}).get("font_size", 32)
    expected_y = icon_rules.get("title_icon_y") or geom.get("title_icon", {}).get("y")
    expected_w = icon_rules.get("title_icon_size") or geom.get("title_icon", {}).get("width")
    expected_h = expected_w
    expected_gap = (
        icon_rules.get("title_icon_gap_from_text")
        or geom.get("title_icon", {}).get("gap_from_title")
        or 12
    )
    content_min_y = geom.get("content_min_y", 105)

    if expected_y is None or expected_w is None:
        return content, fixes

    header_pattern = re.compile(r'(<g id="header">\s*)(.*?)(\s*</g>)', re.IGNORECASE | re.DOTALL)
    title_pattern = re.compile(
        r'(<text\b(?P<attrs>[^>]*)>(?P<title>.*?)</text>)',
        re.IGNORECASE | re.DOTALL,
    )
    use_pattern = re.compile(r'<use\b[^>]*data-icon="[^"]+"[^>]*/?>', re.IGNORECASE)
    group_pattern = re.compile(
        r'<g\b(?P<attrs>[^>]*)\btransform="translate\('
        r'(?P<x>[\d.]+),\s*(?P<y>[\d.]+)\)\s*scale\((?P<scale>[\d.]+)\)"'
        r'(?P<suffix>[^>]*)>',
        re.IGNORECASE,
    )

    def repair_header(m: re.Match) -> str:
        header_inner = m.group(2)
        title_match = None

        for candidate in title_pattern.finditer(header_inner):
            title_y = _get_attr_float(candidate.group("attrs"), "y")
            if title_y is None or title_y >= content_min_y:
                continue
            title_match = candidate
            break

        if title_match is None:
            return m.group(0)

        title_attrs = title_match.group("attrs")
        title_x = _get_attr_float(title_attrs, "x") or expected_title_x
        title_y = _get_attr_float(title_attrs, "y") or expected_title_y
        title_font_size = _get_attr_float(title_attrs, "font-size") or expected_font_size

        if title_y >= content_min_y:
            return m.group(0)

        expected_x = round(
            title_x + _estimate_text_width(title_match.group("title"), title_font_size) + expected_gap,
            1,
        )

        after_title = header_inner[title_match.end():]
        candidates: list[tuple[int, str, re.Match]] = []

        use_match = use_pattern.search(after_title)
        if use_match:
            candidates.append((use_match.start(), "use", use_match))

        group_match = group_pattern.search(after_title)
        if group_match:
            candidates.append((group_match.start(), "group", group_match))

        if not candidates:
            return m.group(0)

        _, icon_type, icon_match = min(candidates, key=lambda item: item[0])
        updated_header = header_inner
        changed = False

        if icon_type == "use":
            icon_node = icon_match.group(0)
            cur_x = _get_attr_float(icon_node, "x")
            cur_y = _get_attr_float(icon_node, "y")
            cur_w = _get_attr_float(icon_node, "width")
            cur_h = _get_attr_float(icon_node, "height")

            if cur_y is None or cur_y >= content_min_y:
                return m.group(0)

            result = icon_node
            if cur_x is not None and abs(cur_x - expected_x) > 2:
                result = re.sub(r'\bx="[\d.]+"', f'x="{_format_num(expected_x)}"', result, count=1)
                changed = True
            if abs(cur_y - expected_y) > 2:
                result = re.sub(r'\by="[\d.]+"', f'y="{_format_num(expected_y)}"', result, count=1)
                changed = True
            if cur_w is not None and abs(cur_w - expected_w) > 2:
                result = re.sub(r'\bwidth="[\d.]+"', f'width="{_format_num(expected_w)}"', result, count=1)
                changed = True
            if cur_h is not None and abs(cur_h - expected_h) > 2:
                result = re.sub(r'\bheight="[\d.]+"', f'height="{_format_num(expected_h)}"', result, count=1)
                changed = True

            if changed:
                start = title_match.end() + icon_match.start()
                end = title_match.end() + icon_match.end()
                updated_header = header_inner[:start] + result + header_inner[end:]
        else:
            cur_x = float(icon_match.group("x"))
            cur_y = float(icon_match.group("y"))
            cur_scale = icon_match.group("scale")

            if cur_y >= content_min_y:
                return m.group(0)

            if abs(cur_x - expected_x) > 2 or abs(cur_y - expected_y) > 2:
                new_open_tag = (
                    f'<g{icon_match.group("attrs")}transform="translate('
                    f'{_format_num(expected_x)}, {_format_num(expected_y)}) scale({cur_scale})"'
                    f'{icon_match.group("suffix")}>'
                )
                start = title_match.end() + icon_match.start()
                end = title_match.end() + icon_match.end()
                updated_header = header_inner[:start] + new_open_tag + header_inner[end:]
                changed = True

        if changed:
            fixes.append(
                "Title icon fix: header icon re-anchored to title width "
                f"(x={_format_num(expected_x)}, y={_format_num(expected_y)})"
            )
            return m.group(1) + updated_header + m.group(3)

        return m.group(0)

    content = header_pattern.sub(repair_header, content, count=1)
    return content, fixes


# ────────────────────────────────────────────────────────────────
# Repair 3: SVG Format / Syntax Errors
# ────────────────────────────────────────────────────────────────

def _repair_svg_syntax(content: str) -> tuple[str, list[str]]:
    """Fix common SVG syntax issues that break PPT export.

    Covers:
    - Unescaped < > in text content → &lt; &gt;
    - Unescaped & in text content → &amp;
    - rgba() → rgb() + fill-opacity/stroke-opacity
    - <g opacity> / <image opacity> → remove
    """
    fixes: list[str] = []

    # --- Fix unescaped < > & in text content ---
    def escape_text_node(m: re.Match) -> str:
        text = m.group(1)
        original = text
        # Fix unescaped & first (but not existing entities)
        text = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[0-9a-fA-F]+;)', '&amp;', text)
        # Fix unescaped < (a real < in text content, not a tag start)
        text = re.sub(r'<(?![a-zA-Z/!?])', '&lt;', text)
        # Fix unescaped > in text
        text = re.sub(r'(?<!["\'/a-zA-Z0-9\-])>', '&gt;', text)
        if text != original:
            fixes.append(f"Syntax fix: escaped < > & in text content")
        return '>' + text + '<'

    content = re.sub(r'>([^<]+)<', escape_text_node, content)

    # --- Fix rgba() colors ---
    rgba_pattern = re.compile(
        r'(fill|stroke)\s*=\s*"rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)"'
    )

    def rgba_replacer(m: re.Match) -> str:
        prop = m.group(1)
        r, g, b = m.group(2), m.group(3), m.group(4)
        a = m.group(5)
        fixes.append(f"Syntax fix: rgba({r},{g},{b},{a}) → rgb + {prop}-opacity")
        return f'{prop}="rgb({r},{g},{b})" {prop}-opacity="{a}"'

    content = rgba_pattern.sub(rgba_replacer, content)

    # --- Fix <g opacity="..."> ---
    g_opacity_pattern = re.compile(r'<g(\s[^>]*)\sopacity="([\d.]+)"([^>]*)>')

    def g_opacity_replacer(m: re.Match) -> str:
        before = m.group(1)
        opacity_val = m.group(2)
        after = m.group(3)
        fixes.append(f"Syntax fix: removed <g opacity=\"{opacity_val}\">")
        return f'<g{before}{after}>'

    content = g_opacity_pattern.sub(g_opacity_replacer, content)

    # --- Fix <image opacity="..."> ---
    img_opacity_pattern = re.compile(r'(<image\s[^>]*)\sopacity="[\d.]+"([^>]*/?>)')
    count_img = len(img_opacity_pattern.findall(content))
    if count_img > 0:
        content = img_opacity_pattern.sub(r'\1\2', content)
        fixes.append(f"Syntax fix: removed opacity from {count_img} <image> element(s)")

    return content, fixes


def _validate_svg_xml(content: str) -> str | None:
    """Return a parse error string if the SVG is not well-formed XML."""
    try:
        ET.fromstring(content)
        return None
    except ET.ParseError as exc:
        return str(exc)


def _repair_xml_structure(content: str) -> tuple[str, list[str], str | None]:
    """Repair common XML hard errors and report any remaining parse failure."""
    fixes: list[str] = []
    parse_error = _validate_svg_xml(content)
    if parse_error is None:
        return content, fixes, None

    original_error = parse_error

    broken_closing_tags = [
        "svg",
        "defs",
        "g",
        "text",
        "tspan",
        "path",
        "rect",
        "circle",
        "ellipse",
        "line",
        "polyline",
        "polygon",
        "use",
        "image",
        "clipPath",
        "mask",
        "linearGradient",
        "radialGradient",
        "stop",
        "filter",
        "marker",
        "feGaussianBlur",
        "feOffset",
        "feFlood",
        "feComposite",
        "feMerge",
        "feMergeNode",
    ]
    closing_tag_pattern = re.compile(
        rf'(?<!<)/\s*({"|".join(map(re.escape, broken_closing_tags))})\s*>',
        re.IGNORECASE,
    )
    content, count_broken = closing_tag_pattern.subn(r'</\1>', content)
    if count_broken > 0:
        fixes.append(f"XML fix: restored {count_broken} malformed closing tag(s)")

    control_char_pattern = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")
    content, count_controls = control_char_pattern.subn("", content)
    if count_controls > 0:
        fixes.append(f"XML fix: removed {count_controls} invalid control character(s)")

    parse_error = _validate_svg_xml(content)
    if parse_error is None:
        if not fixes:
            fixes.append("XML fix: validated well-formed SVG after fallback checks")
        return content, fixes, None

    if fixes:
        fixes.append(f"XML validation warning: still invalid after fallback repairs ({parse_error})")
    else:
        fixes.append(f"XML validation warning: malformed SVG ({original_error})")

    return content, fixes, parse_error


# ────────────────────────────────────────────────────────────────
# Main Orchestrator
# ────────────────────────────────────────────────────────────────

def repair_svg_file(
    svg_path: Path,
    anchor: dict[str, Any] | None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Repair a single SVG file. Returns a report dict."""
    report: dict[str, Any] = {
        "file": svg_path.name,
        "repairs": [],
        "skipped": False,
        "valid_xml": True,
    }

    try:
        content = svg_path.read_text(encoding="utf-8")
    except Exception as e:
        report["skipped"] = True
        report["error"] = str(e)
        return report

    original = content
    all_fixes: list[str] = []

    # Repair 1: Arc geometry
    content, fixes = _repair_arc_geometry(content)
    all_fixes.extend(fixes)

    # Repair 2: Title icon position
    content, fixes = _repair_title_icon_position(content, anchor)
    all_fixes.extend(fixes)

    # Repair 3: SVG syntax
    content, fixes = _repair_svg_syntax(content)
    all_fixes.extend(fixes)

    # Repair 4: XML structure validation / fallback repair
    content, fixes, parse_error = _repair_xml_structure(content)
    all_fixes.extend(fixes)
    if parse_error:
        report["valid_xml"] = False
        report["validation_error"] = parse_error

    report["repairs"] = all_fixes

    if content != original and not dry_run:
        svg_path.write_text(content, encoding="utf-8")
        report["modified"] = True
    else:
        report["modified"] = False

    return report


def repair_project(project_path: Path, dry_run: bool = False) -> dict[str, Any]:
    """Repair all SVGs in a project's svg_output/ directory."""
    if project_path.name in {"svg_output", "svg_final"} and project_path.is_dir():
        svg_dir = project_path
        project_root = project_path.parent
    else:
        project_root = project_path
        svg_dir = project_root / "svg_output"
        if not svg_dir.exists():
            svg_dir = project_root / "svg_final"
        if not svg_dir.exists():
            print(f"[ERROR] svg_output/ or svg_final/ not found in {project_path}")
            return {"error": "svg directory not found", "files": []}

    # Load anchor context if available
    anchor_path = project_root / "runner" / "svg_anchor_context.json"
    anchor: dict[str, Any] | None = None
    if anchor_path.exists():
        try:
            anchor = json.loads(anchor_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    svg_files = sorted(svg_dir.glob("*.svg"))
    if not svg_files:
        print(f"[WARN] No SVG files found in {svg_dir.name}/")
        return {"files": []}

    mode = "DRY RUN" if dry_run else "REPAIR"
    print(f"\n[{mode}] Processing {len(svg_files)} SVG file(s) in {svg_dir}...\n")

    file_reports: list[dict[str, Any]] = []
    total_repairs = 0

    for svg_file in svg_files:
        report = repair_svg_file(svg_file, anchor, dry_run)
        file_reports.append(report)

        n = len(report["repairs"])
        total_repairs += n

        if n > 0:
            status = "FIXED" if report.get("modified") else "WOULD FIX"
            print(f"  [{status}] {report['file']} — {n} repair(s)")
            for fix in report["repairs"]:
                print(f"         · {fix}")
        else:
            print(f"  [OK] {report['file']}")

    print(f"\n[SUMMARY] {total_repairs} total repair(s) across {len(svg_files)} file(s)")
    if dry_run and total_repairs > 0:
        print("[INFO] Dry run mode — no files were modified. Remove --dry-run to apply fixes.")

    # Save repair report
    report_path = project_root / "runner" / "svg_repair_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_data = {
        "mode": mode.lower(),
        "total_files": len(svg_files),
        "total_repairs": total_repairs,
        "files": file_reports,
    }
    report_path.write_text(
        json.dumps(report_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[REPORT] Repair report saved to {report_path}")

    return report_data


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    project_path = Path(sys.argv[1]).expanduser().resolve()
    dry_run = "--dry-run" in sys.argv

    result = repair_project(project_path, dry_run)
    sys.exit(1 if result.get("error") else 0)


if __name__ == "__main__":
    main()
