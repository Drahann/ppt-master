"""Input asset downloading and Markdown image URL normalization."""

from __future__ import annotations

import json
import mimetypes
import re
import shutil
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path


MARKDOWN_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
HTML_IMG_RE = re.compile(r"<img\b[^>]*\bsrc=[\"']([^\"']+)[\"'][^>]*>", re.I)


@dataclass
class ImageAsset:
    original_url: str
    filename: str
    alt: str
    status: str
    reason: str = ""


def _split_markdown_target(target: str) -> str:
    stripped = target.strip()
    if not stripped:
        return ""
    if stripped[0] in {"'", '"'}:
        quote = stripped[0]
        end = stripped.find(quote, 1)
        return stripped[1:end] if end > 0 else stripped.strip(quote)
    return stripped.split()[0]


def _safe_name(value: str, fallback: str) -> str:
    chars: list[str] = []
    for ch in value.strip():
        if ch.isalnum() or "\u4e00" <= ch <= "\u9fff":
            chars.append(ch)
        elif ch in "-_.":
            chars.append(ch)
        else:
            chars.append("_")
    name = re.sub(r"_+", "_", "".join(chars)).strip("._")
    return name[:48] or fallback


def _is_downloadable_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _is_ignored_root_path(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return not parsed.scheme and url.strip().startswith("/")


def _extension_from(url: str, content_type: str | None) -> str:
    path = urllib.parse.urlparse(url).path
    suffix = Path(path).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        return suffix
    if content_type:
        guessed = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if guessed in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
            return guessed
    return ".png"


def _unique_output_path(output_dir: Path, filename: str) -> Path:
    output_path = output_dir / filename
    if not output_path.exists():
        return output_path
    stem = output_path.stem
    suffix = output_path.suffix
    counter = 2
    while True:
        candidate = output_dir / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _download(url: str, output_dir: Path, filename_base: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "ppt-master/automation"})
    with urllib.request.urlopen(request, timeout=45) as response:
        content_type = response.headers.get("content-type")
        ext = _extension_from(url, content_type)
        output_path = _unique_output_path(output_dir, f"{filename_base}{ext}")
        data = response.read(15 * 1024 * 1024 + 1)
        if len(data) > 15 * 1024 * 1024:
            raise ValueError("image exceeds 15MB download limit")
        output_path.write_bytes(data)
        return output_path.name


def _resolve_local_path(url: str, project_path: Path, source_base_dir: Path | None) -> Path | None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme == "file":
        raw_path = urllib.parse.unquote(parsed.path)
        if re.match(r"^/[A-Za-z]:/", raw_path):
            raw_path = raw_path[1:]
        candidate = Path(raw_path)
        return candidate if candidate.exists() and candidate.is_file() else None
    if parsed.scheme:
        return None

    candidate = Path(urllib.parse.unquote(url))
    candidates: list[Path]
    if candidate.is_absolute():
        candidates = [candidate]
    else:
        candidates = []
        if source_base_dir is not None:
            candidates.append(source_base_dir / candidate)
        candidates.extend(
            [
                project_path / candidate,
                project_path.parent / candidate,
                Path.cwd() / candidate,
                Path.cwd().parent / candidate,
            ]
        )
    for item in candidates:
        try:
            resolved = item.resolve()
        except OSError:
            continue
        if resolved.exists() and resolved.is_file():
            return resolved
    return None


def _copy_local_image(
    url: str,
    alt: str,
    image_dir: Path,
    project_path: Path,
    source_base_dir: Path | None,
    index: int,
) -> tuple[str | None, ImageAsset]:
    source = _resolve_local_path(url, project_path, source_base_dir)
    if source is None:
        return None, ImageAsset(original_url=url, filename="", alt=alt, status="missing", reason="local image not found")
    suffix = source.suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
        suffix = mimetypes.guess_extension(mimetypes.guess_type(source.name)[0] or "") or source.suffix or ".bin"
    safe_source_name = _safe_name(source.stem, f"image_{index:02d}")
    output_path = _unique_output_path(image_dir, f"{safe_source_name}{suffix}")
    shutil.copy2(source, output_path)
    asset = ImageAsset(original_url=url, filename=output_path.name, alt=alt, status="copied")
    return f"../images/{output_path.name}", asset


def download_and_rewrite_markdown_images(
    markdown: str,
    project_path: Path,
    source_base_dir: Path | None = None,
) -> tuple[str, list[ImageAsset]]:
    """Materialize Markdown images into project/images and rewrite source URLs."""

    image_dir = project_path / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    assets: list[ImageAsset] = []
    index = 0

    def handle_url(raw_url: str, alt: str) -> tuple[str | None, ImageAsset | None]:
        nonlocal index
        url = raw_url.strip()
        if _is_ignored_root_path(url):
            asset = ImageAsset(original_url=url, filename="", alt=alt, status="ignored", reason="root/local path")
            assets.append(asset)
            return None, asset
        index += 1
        if not _is_downloadable_url(url):
            rewritten, asset = _copy_local_image(url, alt, image_dir, project_path, source_base_dir, index)
            if asset.status != "missing":
                assets.append(asset)
                return rewritten, asset
            assets.append(asset)
            return raw_url, None
        base = _safe_name(f"{index:02d}_{alt}", f"image_{index:02d}")
        try:
            filename = _download(url, image_dir, base)
            asset = ImageAsset(original_url=url, filename=filename, alt=alt, status="downloaded")
            assets.append(asset)
            return f"../images/{filename}", asset
        except (OSError, ValueError, urllib.error.URLError, urllib.error.HTTPError) as exc:
            asset = ImageAsset(original_url=url, filename="", alt=alt, status="failed", reason=str(exc))
            assets.append(asset)
            return raw_url, asset

    def replace_markdown(match: re.Match[str]) -> str:
        alt = match.group(1).strip()
        target = match.group(2)
        url = _split_markdown_target(target)
        rewritten, asset = handle_url(url, alt)
        if asset and asset.status == "ignored":
            return f"<!-- ignored local image: {alt or url} -->"
        if rewritten and rewritten != target:
            return f"![{alt}]({rewritten})"
        return match.group(0)

    rewritten = MARKDOWN_IMAGE_RE.sub(replace_markdown, markdown)

    def replace_html(match: re.Match[str]) -> str:
        url = match.group(1).strip()
        rewritten_url, asset = handle_url(url, "")
        if asset and asset.status == "ignored":
            return "<!-- ignored local image -->"
        if rewritten_url and rewritten_url != url:
            return f'<img src="{rewritten_url}" />'
        return match.group(0)

    rewritten = HTML_IMG_RE.sub(replace_html, rewritten)
    if assets:
        (image_dir / "image_manifest.json").write_text(
            json.dumps([asdict(asset) for asset in assets], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        lines = ["# Image Resource List", ""]
        for asset in assets:
            lines.append(f"- {asset.status}: {asset.filename or asset.original_url} | alt={asset.alt} | reason={asset.reason}")
        (image_dir / "image_manifest.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return rewritten, assets
