#!/usr/bin/env python3
"""
PPT Master - SVG Quality Check Tool

Checks whether SVG files comply with project technical specifications.

Usage:
    python3 scripts/svg_quality_checker.py <svg_file>
    python3 scripts/svg_quality_checker.py <directory>
    python3 scripts/svg_quality_checker.py --all examples
"""

import sys
import re
from pathlib import Path
from typing import List, Dict, Tuple
from collections import defaultdict

try:
    from project_utils import CANVAS_FORMATS
    from error_helper import ErrorHelper
except ImportError:
    print("Warning: Unable to import dependency modules")
    CANVAS_FORMATS = {}
    ErrorHelper = None


class SVGQualityChecker:
    """SVG quality checker"""

    def __init__(self):
        self.results = []
        self.summary = {
            'total': 0,
            'passed': 0,
            'warnings': 0,
            'errors': 0
        }
        self.issue_types = defaultdict(int)

    def check_file(self, svg_file: str, expected_format: str = None) -> Dict:
        """
        Check a single SVG file

        Args:
            svg_file: SVG file path
            expected_format: Expected canvas format (e.g., 'ppt169')

        Returns:
            Check result dictionary
        """
        svg_path = Path(svg_file)

        if not svg_path.exists():
            return {
                'file': str(svg_file),
                'exists': False,
                'errors': ['File does not exist'],
                'warnings': [],
                'passed': False
            }

        result = {
            'file': svg_path.name,
            'path': str(svg_path),
            'exists': True,
            'errors': [],
            'warnings': [],
            'info': {},
            'passed': True
        }

        try:
            with open(svg_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 1. Check viewBox
            self._check_viewbox(content, result, expected_format)

            # 2. Check forbidden elements
            self._check_forbidden_elements(content, result)

            # 3. Check fonts
            self._check_fonts(content, result)

            # 4. Check width/height consistency with viewBox
            self._check_dimensions(content, result)

            # 5. Check text wrapping methods
            self._check_text_elements(content, result)

            # 6. Check image references (file existence and resolution)
            self._check_image_references(content, svg_path, result)

            # 7. Check arc/donut/pie chart geometry (C7)
            self._check_arc_geometry(content, result)

            # 8. Check element overlap (C8)
            self._check_element_overlap(content, result)

            # Determine pass/fail
            result['passed'] = len(result['errors']) == 0

        except Exception as e:
            result['errors'].append(f"Failed to read file: {e}")
            result['passed'] = False

        # Update statistics
        self.summary['total'] += 1
        if result['passed']:
            if result['warnings']:
                self.summary['warnings'] += 1
            else:
                self.summary['passed'] += 1
        else:
            self.summary['errors'] += 1

        # Categorize issue types
        for error in result['errors']:
            self.issue_types[self._categorize_issue(error)] += 1

        self.results.append(result)
        return result

    def _check_viewbox(self, content: str, result: Dict, expected_format: str = None):
        """Check viewBox attribute"""
        viewbox_match = re.search(r'viewBox="([^"]+)"', content)

        if not viewbox_match:
            result['errors'].append("Missing viewBox attribute")
            return

        viewbox = viewbox_match.group(1)
        result['info']['viewbox'] = viewbox

        # Check format
        if not re.match(r'0 0 \d+ \d+', viewbox):
            result['warnings'].append(f"Unusual viewBox format: {viewbox}")

        # Check if it matches expected format
        if expected_format and expected_format in CANVAS_FORMATS:
            expected_viewbox = CANVAS_FORMATS[expected_format]['viewbox']
            if viewbox != expected_viewbox:
                result['errors'].append(
                    f"viewBox mismatch: expected '{expected_viewbox}', got '{viewbox}'"
                )

    def _check_forbidden_elements(self, content: str, result: Dict):
        """Check forbidden elements (blocklist)"""
        content_lower = content.lower()

        # ============================================================
        # Forbidden elements blocklist - PPT incompatible
        # ============================================================

        # Clipping / masking
        # clipPath is ONLY allowed on <image> elements (converter maps to DrawingML
        # picture geometry).  On shapes it is pointless (just draw the target shape)
        # and breaks the SVG PPTX rendering.
        if '<clippath' in content_lower:
            # clip-path on non-image elements → error
            clip_on_non_image = re.search(
                r'<(?!image\b)\w+[^>]*\bclip-path\s*=', content, re.IGNORECASE)
            if clip_on_non_image:
                result['errors'].append(
                    "clip-path is only allowed on <image> elements — "
                    "for shapes, draw the target shape directly instead of clipping")
            # Check that every clip-path reference has a matching <clipPath> def
            clip_refs = re.findall(r'clip-path\s*=\s*["\']url\(#([^)]+)\)', content)
            for ref_id in clip_refs:
                if f'id="{ref_id}"' not in content and f"id='{ref_id}'" not in content:
                    result['errors'].append(
                        f"clip-path references #{ref_id} but no matching "
                        f"<clipPath id=\"{ref_id}\"> definition found")
        if '<mask' in content_lower:
            result['errors'].append("Detected forbidden <mask> element (PPT does not support SVG masks)")

        # Style system
        if '<style' in content_lower:
            result['errors'].append("Detected forbidden <style> element (use inline attributes instead)")
        if re.search(r'\bclass\s*=', content):
            result['errors'].append("Detected forbidden class attribute (use inline styles instead)")
        # id attribute: only report error when <style> also exists (id is harmful only with CSS selectors)
        # id inside <defs> for linearGradient/filter etc. is required, Inkscape also auto-adds id to elements,
        # standalone id attributes have no impact on PPT export
        if '<style' in content_lower and re.search(r'\bid\s*=', content):
            result['errors'].append(
                "Detected id attribute used with <style> (CSS selectors forbidden, use inline styles instead)"
            )
        if re.search(r'<\?xml-stylesheet\b', content_lower):
            result['errors'].append("Detected forbidden xml-stylesheet (external CSS references forbidden)")
        if re.search(r'<link[^>]*rel\s*=\s*["\']stylesheet["\']', content_lower):
            result['errors'].append("Detected forbidden <link rel=\"stylesheet\"> (external CSS references forbidden)")
        if re.search(r'@import\s+', content_lower):
            result['errors'].append("Detected forbidden @import (external CSS references forbidden)")

        # Structure / nesting
        if '<foreignobject' in content_lower:
            result['errors'].append(
                "Detected forbidden <foreignObject> element (use <tspan> for manual line breaks)")
        has_symbol = '<symbol' in content_lower
        has_use = re.search(r'<use\b', content_lower) is not None
        if has_symbol and has_use:
            result['errors'].append("Detected forbidden <symbol> + <use> complex usage (use basic shapes or simple <use> instead)")
        # marker-start / marker-end are conditionally allowed (see shared-standards.md §1.1).
        # The converter maps qualifying <marker> defs to native DrawingML <a:headEnd>/<a:tailEnd>.
        # We only warn when a marker is used without an obvious <defs> definition in the same file.
        if re.search(r'\bmarker-(?:start|end)\s*=\s*["\']url\(#([^)]+)\)', content_lower):
            if '<marker' not in content_lower:
                result['errors'].append(
                    "Detected marker-start/marker-end referencing a marker id, "
                    "but no <marker> element found in the file")

        # Text / fonts
        if '<textpath' in content_lower:
            result['errors'].append("Detected forbidden <textPath> element (path text is incompatible with PPT)")
        if '@font-face' in content_lower:
            result['errors'].append("Detected forbidden @font-face (use system font stack)")

        # Animation / interaction
        if re.search(r'<animate', content_lower):
            result['errors'].append("Detected forbidden SMIL animation element <animate*> (SVG animations are not exported)")
        if re.search(r'<set\b', content_lower):
            result['errors'].append("Detected forbidden SMIL animation element <set> (SVG animations are not exported)")
        if '<script' in content_lower:
            result['errors'].append("Detected forbidden <script> element (scripts and event handlers forbidden)")
        if re.search(r'\bon\w+\s*=', content):  # onclick, onload etc.
            result['errors'].append("Detected forbidden event attributes (e.g., onclick, onload)")

        # Other discouraged elements
        if '<iframe' in content_lower:
            result['errors'].append("Detected <iframe> element (should not appear in SVG)")
        if re.search(r'rgba\s*\(', content_lower):
            result['errors'].append("Detected forbidden rgba() color (use fill-opacity/stroke-opacity instead)")
        if re.search(r'<g[^>]*\sopacity\s*=', content_lower):
            result['errors'].append("Detected forbidden <g opacity> (set opacity on each child element individually)")
        if re.search(r'<image[^>]*\sopacity\s*=', content_lower):
            result['errors'].append("Detected forbidden <image opacity> (use overlay mask approach)")

    def _check_fonts(self, content: str, result: Dict):
        """Check font usage"""
        # Find font-family declarations
        font_matches = re.findall(
            r'font-family[:\s]*["\']([^"\']+)["\']', content, re.IGNORECASE)

        if font_matches:
            result['info']['fonts'] = list(set(font_matches))

            # Check if system UI font stack is used
            recommended_fonts = [
                'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI']

            for font_family in font_matches:
                has_recommended = any(
                    rec in font_family for rec in recommended_fonts)

                if not has_recommended:
                    result['warnings'].append(
                        f"Recommend using system UI font stack, current: {font_family}"
                    )
                    break  # Only warn once

    def _check_dimensions(self, content: str, result: Dict):
        """Check width/height consistency with viewBox"""
        width_match = re.search(r'width="(\d+)"', content)
        height_match = re.search(r'height="(\d+)"', content)

        if width_match and height_match:
            width = width_match.group(1)
            height = height_match.group(1)
            result['info']['dimensions'] = f"{width}x{height}"

            # Check consistency with viewBox
            if 'viewbox' in result['info']:
                viewbox_parts = result['info']['viewbox'].split()
                if len(viewbox_parts) == 4:
                    vb_width, vb_height = viewbox_parts[2], viewbox_parts[3]
                    if width != vb_width or height != vb_height:
                        result['warnings'].append(
                            f"width/height ({width}x{height}) does not match viewBox "
                            f"({vb_width}x{vb_height})"
                        )

    def _check_text_elements(self, content: str, result: Dict):
        """Check text elements and wrapping methods"""
        # Count text and tspan elements
        text_count = content.count('<text')
        tspan_count = content.count('<tspan')

        result['info']['text_elements'] = text_count
        result['info']['tspan_elements'] = tspan_count

        # Check for overly long single-line text (may need wrapping)
        text_matches = re.findall(r'<text[^>]*>([^<]{100,})</text>', content)
        if text_matches:
            result['warnings'].append(
                f"Detected {len(text_matches)} potentially overly long single-line text(s) (consider using tspan for wrapping)"
            )

    def _check_image_references(self, content: str, svg_path: Path, result: Dict):
        """Check image file existence and resolution vs display size."""
        # Find all <image ...> elements (capture the full tag)
        img_tag_pattern = re.compile(r'<image\b([^>]*)/?>', re.IGNORECASE)

        svg_dir = svg_path.parent
        checked = set()

        for tag_match in img_tag_pattern.finditer(content):
            attrs = tag_match.group(1)

            # Extract href (prefer href over xlink:href)
            href_match = (
                re.search(r'\bhref="(?!data:)([^"]+)"', attrs) or
                re.search(r'\bxlink:href="(?!data:)([^"]+)"', attrs)
            )
            if not href_match:
                continue

            href = href_match.group(1)
            if href in checked:
                continue
            checked.add(href)

            # Resolve path relative to SVG file directory
            img_path = (svg_dir / href).resolve()

            if not img_path.exists():
                result['errors'].append(
                    f"Image file not found: {href} (resolved to {img_path})")
                continue

            # Check resolution vs display size
            w_match = re.search(r'\bwidth="([^"]+)"', attrs)
            h_match = re.search(r'\bheight="([^"]+)"', attrs)
            display_w_str = w_match.group(1) if w_match else None
            display_h_str = h_match.group(1) if h_match else None
            if not display_w_str or not display_h_str:
                continue

            try:
                display_w = float(display_w_str)
                display_h = float(display_h_str)
            except (ValueError, TypeError):
                continue

            try:
                from PIL import Image as PILImage
                with PILImage.open(img_path) as img:
                    actual_w, actual_h = img.size

                if actual_w < display_w or actual_h < display_h:
                    result['warnings'].append(
                        f"Image {href} is {actual_w}x{actual_h} but displayed at "
                        f"{int(display_w)}x{int(display_h)} — may appear blurry")
                elif actual_w > display_w * 4 and actual_h > display_h * 4:
                    result['warnings'].append(
                        f"Image {href} is {actual_w}x{actual_h} but displayed at "
                        f"{int(display_w)}x{int(display_h)} — consider downsizing "
                        f"to reduce file size")
            except ImportError:
                pass  # PIL not available, skip resolution check
            except Exception:
                pass  # Image unreadable, skip resolution check

    def _check_arc_geometry(self, content: str, result: Dict):
        """Check arc/donut/pie chart geometry (C7).

        Parses SVG arc commands, extracts the implied circle center and radii,
        then verifies that every arc endpoint actually lies on its declared
        circle (within a tolerance).  Also checks that adjacent sectors share
        endpoints (no gaps) and that the mask-circle radius matches the inner
        arc radius.

        For every detected error, the report includes the **correct coordinate**
        calculated via trigonometry so the AI reviewer can apply a precise fix.
        """
        import math

        # Find all <path> elements that contain arc commands
        arc_path_pattern = re.compile(
            r'<path[^>]*\bd="([^"]*A\s*[\d.]+[^"]*)"', re.IGNORECASE
        )

        # Extract arc segments: M x,y A rx,ry ... x,y L x,y A rx,ry ... x,y Z
        arc_cmd_pattern = re.compile(
            r'A\s+([\d.]+)\s*,\s*([\d.]+)\s+[\d.]+\s+[\d,]+\s+([\d.]+)\s*,\s*([\d.]+)'
        )

        # Find mask circles that might be donut-chart centers
        circle_pattern = re.compile(
            r'<circle[^>]*cx="([\d.]+)"[^>]*cy="([\d.]+)"[^>]*r="([\d.]+)"'
        )
        arc_paths = arc_path_pattern.findall(content)
        if not arc_paths:
            return  # No arc-based charts on this page

        circles = circle_pattern.findall(content)
        # Collect all donut radii from multi-arc paths
        donut_inner_radii = set()
        for path_d in arc_paths:
            arcs = arc_cmd_pattern.findall(path_d)
            if len(arcs) < 2:
                continue
            radii_set = set()
            for rx_str, ry_str, _ex, _ey in arcs:
                radii_set.add(float(rx_str))
            if len(radii_set) == 2:
                donut_inner_radii.add(min(radii_set))

        # Check mask circles against detected inner radii (once per circle)
        checked_circles = set()
        for cx_str, cy_str, cr_str in circles:
            cr = float(cr_str)
            circle_key = (cx_str, cy_str, cr_str)
            if circle_key in checked_circles:
                continue
            for inner_r in donut_inner_radii:
                if abs(cr - inner_r) > 2 and cr < inner_r * 2:
                    result['errors'].append(
                        f"Donut mask circle r={cr} does not match inner arc radius {inner_r} "
                        f"\u2014 change <circle r=\"{cr}\"> to r=\"{inner_r}\" "
                        f"(gap of {abs(cr - inner_r):.0f}px will expose sector colors)"
                    )
                    checked_circles.add(circle_key)

        # Check individual sector endpoint accuracy by re-parsing full sector paths
        sector_pattern = re.compile(
            r'<path[^>]*\bd="M\s+([\d.]+)\s*,\s*([\d.]+)\s+'
            r'A\s+([\d.]+)\s*,\s*[\d.]+\s+[\d.]+\s+[\d,]+\s+([\d.]+)\s*,\s*([\d.]+)\s+'
            r'L\s+([\d.]+)\s*,\s*([\d.]+)\s+'
            r'A\s+([\d.]+)\s*,\s*[\d.]+\s+[\d.]+\s+[\d,]+\s+([\d.]+)\s*,\s*([\d.]+)',
            re.IGNORECASE,
        )

        sectors = sector_pattern.findall(content)
        if len(sectors) < 2:
            return

        # Determine chart center from the mask circle or from outer endpoints
        chart_cx, chart_cy = None, None
        for cx_str, cy_str, cr_str in circles:
            cr = float(cr_str)
            if cr < 200:  # reasonable donut inner circle
                chart_cx, chart_cy = float(cx_str), float(cy_str)
                break

        # Collect all outer endpoints to estimate center if no circle found
        if chart_cx is None:
            all_outer_pts = []
            for s in sectors:
                all_outer_pts.append((float(s[0]), float(s[1])))
                all_outer_pts.append((float(s[3]), float(s[4])))
            if len(all_outer_pts) >= 3:
                chart_cx = sum(p[0] for p in all_outer_pts) / len(all_outer_pts)
                chart_cy = sum(p[1] for p in all_outer_pts) / len(all_outer_pts)

        prev_outer_end = None
        prev_inner_end = None
        TOLERANCE = 5  # px

        for idx, sector in enumerate(sectors):
            (m_x, m_y, outer_r_str, outer_end_x, outer_end_y,
             inner_start_x, inner_start_y, inner_r_str, inner_end_x, inner_end_y) = sector

            m_x, m_y = float(m_x), float(m_y)
            outer_r_val = float(outer_r_str)
            outer_end_x, outer_end_y = float(outer_end_x), float(outer_end_y)
            inner_start_x, inner_start_y = float(inner_start_x), float(inner_start_y)
            inner_r_val = float(inner_r_str)
            inner_end_x, inner_end_y = float(inner_end_x), float(inner_end_y)

            # --- Check endpoint distances from center ---
            if chart_cx is not None:
                for label, px, py, expected_r in [
                    ("outer start (M)", m_x, m_y, outer_r_val),
                    ("outer end (A→)", outer_end_x, outer_end_y, outer_r_val),
                    ("inner start (L)", inner_start_x, inner_start_y, inner_r_val),
                    ("inner end (A→)", inner_end_x, inner_end_y, inner_r_val),
                ]:
                    dist = math.sqrt((px - chart_cx)**2 + (py - chart_cy)**2)
                    err = abs(dist - expected_r)
                    if err > TOLERANCE:
                        # Calculate correct coordinate
                        angle = math.atan2(py - chart_cy, px - chart_cx)
                        correct_x = chart_cx + expected_r * math.cos(angle)
                        correct_y = chart_cy + expected_r * math.sin(angle)
                        result['errors'].append(
                            f"Chart sector {idx + 1} {label}: ({px:.1f},{py:.1f}) is {dist:.1f}px from "
                            f"center ({chart_cx:.0f},{chart_cy:.0f}), expected {expected_r:.0f}px "
                            f"— CORRECT coordinate: ({correct_x:.1f},{correct_y:.1f})"
                        )

            # --- Check sector connectivity ---
            if prev_outer_end is not None:
                dx = abs(m_x - prev_outer_end[0])
                dy = abs(m_y - prev_outer_end[1])
                if dx > TOLERANCE or dy > TOLERANCE:
                    result['errors'].append(
                        f"Chart sector {idx + 1}: outer arc start ({m_x:.1f},{m_y:.1f}) "
                        f"does not connect to previous sector end ({prev_outer_end[0]:.1f},{prev_outer_end[1]:.1f}) "
                        f"— should be ({prev_outer_end[0]:.1f},{prev_outer_end[1]:.1f})"
                    )

            if prev_inner_end is not None:
                dx = abs(inner_start_x - prev_inner_end[0])
                dy = abs(inner_start_y - prev_inner_end[1])
                if dx > TOLERANCE or dy > TOLERANCE:
                    result['errors'].append(
                        f"Chart sector {idx + 1}: inner start (L {inner_start_x:.1f},{inner_start_y:.1f}) "
                        f"does not connect to previous sector inner end ({prev_inner_end[0]:.1f},{prev_inner_end[1]:.1f}) "
                        f"— should be ({prev_inner_end[0]:.1f},{prev_inner_end[1]:.1f})"
                    )

            prev_outer_end = (outer_end_x, outer_end_y)
            prev_inner_end = (inner_end_x, inner_end_y)

    def _check_element_overlap(self, content: str, result: Dict):
        """Check for overlapping top-level card/panel elements (C8).

        Extracts bounding boxes of major <g> blocks (identified by filter=cardShadow
        or prominent <rect>/<path> backgrounds) and checks for spatial overlap.
        """
        # Extract top-level card rectangles (both <rect> and <path> with rounded corners)
        rect_pattern = re.compile(
            r'<rect[^>]*x="([\d.]+)"[^>]*y="([\d.]+)"[^>]*width="([\d.]+)"[^>]*height="([\d.]+)"',
            re.IGNORECASE,
        )

        # Find elements with cardShadow filter (these are the visible cards)
        card_rects = []
        for match in re.finditer(
            r'<(?:rect|path)[^>]*filter="url\(#cardShadow\)"[^>]*/?>',
            content, re.IGNORECASE,
        ):
            tag = match.group(0)
            rect_match = rect_pattern.search(tag)
            if rect_match:
                x = float(rect_match.group(1))
                y = float(rect_match.group(2))
                w = float(rect_match.group(3))
                h = float(rect_match.group(4))
                card_rects.append((x, y, w, h))
            else:
                # Try to extract from path d="M x,y H x2 ... V y2 ..."
                d_match = re.search(r'd="([^"]+)"', tag)
                if d_match:
                    d = d_match.group(1)
                    m = re.match(r'M\s*([\d.]+)\s*,\s*([\d.]+)', d)
                    h_vals = re.findall(r'H\s*([\d.]+)', d)
                    v_vals = re.findall(r'V\s*([\d.]+)', d)
                    if m and h_vals and v_vals:
                        mx, my = float(m.group(1)), float(m.group(2))
                        all_x = [mx] + [float(v) for v in h_vals]
                        all_y = [my] + [float(v) for v in v_vals]
                        x = min(all_x)
                        y = min(all_y)
                        w = max(all_x) - x
                        h = max(all_y) - y
                        if w > 10 and h > 10:
                            card_rects.append((x, y, w, h))

        # Check all pairs for overlap
        OVERLAP_THRESHOLD = 20  # px — ignore small overlaps from shadows
        for i in range(len(card_rects)):
            for j in range(i + 1, len(card_rects)):
                ax, ay, aw, ah = card_rects[i]
                bx, by, bw, bh = card_rects[j]

                # Calculate overlap
                ox = max(0, min(ax + aw, bx + bw) - max(ax, bx))
                oy = max(0, min(ay + ah, by + bh) - max(ay, by))

                if ox > OVERLAP_THRESHOLD and oy > OVERLAP_THRESHOLD:
                    result['errors'].append(
                        f"Card overlap detected: card at ({ax:.0f},{ay:.0f},{aw:.0f}x{ah:.0f}) "
                        f"overlaps with card at ({bx:.0f},{by:.0f},{bw:.0f}x{bh:.0f}) "
                        f"by {ox:.0f}x{oy:.0f}px"
                    )

    def _categorize_issue(self, error_msg: str) -> str:
        """Categorize issue type"""
        if 'viewBox' in error_msg:
            return 'viewBox issues'
        elif 'foreignObject' in error_msg:
            return 'foreignObject'
        elif 'font' in error_msg.lower():
            return 'Font issues'
        elif 'arc' in error_msg.lower() or 'sector' in error_msg.lower() or 'donut' in error_msg.lower():
            return 'Chart geometry (C7)'
        elif 'overlap' in error_msg.lower():
            return 'Element overlap (C8)'
        else:
            return 'Other'

    def check_directory(self, directory: str, expected_format: str = None) -> List[Dict]:
        """
        Check all SVG files in a directory

        Args:
            directory: Directory path
            expected_format: Expected canvas format

        Returns:
            List of check results
        """
        dir_path = Path(directory)

        if not dir_path.exists():
            print(f"[ERROR] Directory does not exist: {directory}")
            return []

        # Find all SVG files
        if dir_path.is_file():
            svg_files = [dir_path]
        else:
            svg_output = dir_path / \
                'svg_output' if (
                    dir_path / 'svg_output').exists() else dir_path
            svg_files = sorted(svg_output.glob('*.svg'))

        if not svg_files:
            print(f"[WARN] No SVG files found")
            return []

        print(f"\n[SCAN] Checking {len(svg_files)} SVG file(s)...\n")

        for svg_file in svg_files:
            result = self.check_file(str(svg_file), expected_format)
            self._print_result(result)

        return self.results

    def _print_result(self, result: Dict):
        """Print check result for a single file"""
        if result['passed']:
            if result['warnings']:
                icon = "[WARN]"
                status = "Passed (with warnings)"
            else:
                icon = "[OK]"
                status = "Passed"
        else:
            icon = "[ERROR]"
            status = "Failed"

        print(f"{icon} {result['file']} - {status}")

        # Display basic info
        if result['info']:
            info_items = []
            if 'viewbox' in result['info']:
                info_items.append(f"viewBox: {result['info']['viewbox']}")
            if info_items:
                print(f"   {' | '.join(info_items)}")

        # Display errors
        if result['errors']:
            for error in result['errors']:
                print(f"   [ERROR] {error}")

        # Display warnings
        if result['warnings']:
            for warning in result['warnings'][:2]:  # Only show first 2 warnings
                print(f"   [WARN] {warning}")
            if len(result['warnings']) > 2:
                print(f"   ... and {len(result['warnings']) - 2} more warning(s)")

        print()

    def print_summary(self):
        """Print check summary"""
        print("=" * 80)
        print("[SUMMARY] Check Summary")
        print("=" * 80)

        print(f"\nTotal files: {self.summary['total']}")
        print(
            f"  [OK] Fully passed: {self.summary['passed']} ({self._percentage(self.summary['passed'])}%)")
        print(
            f"  [WARN] With warnings: {self.summary['warnings']} ({self._percentage(self.summary['warnings'])}%)")
        print(
            f"  [ERROR] With errors: {self.summary['errors']} ({self._percentage(self.summary['errors'])}%)")

        if self.issue_types:
            print(f"\nIssue categories:")
            for issue_type, count in sorted(self.issue_types.items(), key=lambda x: x[1], reverse=True):
                print(f"  {issue_type}: {count}")

        # Fix suggestions
        if self.summary['errors'] > 0 or self.summary['warnings'] > 0:
            print(f"\n[TIP] Common fixes:")
            print(f"  1. viewBox issues: Ensure consistency with canvas format (see references/canvas-formats.md)")
            print(f"  2. foreignObject: Use <text> + <tspan> for manual line breaks")
            print(f"  3. Font issues: Use system UI font stack")

    def _percentage(self, count: int) -> int:
        """Calculate percentage"""
        if self.summary['total'] == 0:
            return 0
        return int(count / self.summary['total'] * 100)

    def export_report(self, output_file: str = 'svg_quality_report.txt'):
        """Export check report"""
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("PPT Master SVG Quality Check Report\n")
            f.write("=" * 80 + "\n\n")

            for result in self.results:
                status = "[OK] Passed" if result['passed'] else "[ERROR] Failed"
                f.write(f"{status} - {result['file']}\n")
                f.write(f"Path: {result.get('path', 'N/A')}\n")

                if result['info']:
                    f.write(f"Info: {result['info']}\n")

                if result['errors']:
                    f.write(f"\nErrors:\n")
                    for error in result['errors']:
                        f.write(f"  - {error}\n")

                if result['warnings']:
                    f.write(f"\nWarnings:\n")
                    for warning in result['warnings']:
                        f.write(f"  - {warning}\n")

                f.write("\n" + "-" * 80 + "\n\n")

            # Write summary
            f.write("\n" + "=" * 80 + "\n")
            f.write("Check Summary\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Total files: {self.summary['total']}\n")
            f.write(f"Fully passed: {self.summary['passed']}\n")
            f.write(f"With warnings: {self.summary['warnings']}\n")
            f.write(f"With errors: {self.summary['errors']}\n")

        print(f"\n[REPORT] Check report exported: {output_file}")


def main() -> None:
    """Run the CLI entry point."""
    if len(sys.argv) < 2:
        print("PPT Master - SVG Quality Check Tool\n")
        print("Usage:")
        print("  python3 scripts/svg_quality_checker.py <svg_file>")
        print("  python3 scripts/svg_quality_checker.py <directory>")
        print("  python3 scripts/svg_quality_checker.py --all examples")
        print("\nExamples:")
        print("  python3 scripts/svg_quality_checker.py examples/project/svg_output/slide_01.svg")
        print("  python3 scripts/svg_quality_checker.py examples/project/svg_output")
        print("  python3 scripts/svg_quality_checker.py examples/project")
        sys.exit(0)

    checker = SVGQualityChecker()

    # Parse arguments
    target = sys.argv[1]
    expected_format = None

    if '--format' in sys.argv:
        idx = sys.argv.index('--format')
        if idx + 1 < len(sys.argv):
            expected_format = sys.argv[idx + 1]

    # Execute check
    if target == '--all':
        # Check all example projects
        base_dir = sys.argv[2] if len(sys.argv) > 2 else 'examples'
        from project_utils import find_all_projects
        projects = find_all_projects(base_dir)

        for project in projects:
            print(f"\n{'=' * 80}")
            print(f"Checking project: {project.name}")
            print('=' * 80)
            checker.check_directory(str(project))
    else:
        checker.check_directory(target, expected_format)

    # Print summary
    checker.print_summary()

    # Export report (if specified)
    if '--export' in sys.argv:
        output_file = 'svg_quality_report.txt'
        if '--output' in sys.argv:
            idx = sys.argv.index('--output')
            if idx + 1 < len(sys.argv):
                output_file = sys.argv[idx + 1]
        checker.export_report(output_file)

    # Return exit code
    if checker.summary['errors'] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
