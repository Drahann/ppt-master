from __future__ import annotations

import base64
import mimetypes
import re
import shutil
from pathlib import Path
from urllib.parse import unquote, urlparse

import requests


IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
DATA_URI_PATTERN = re.compile(r"^data:(?P<mime>[^;,]+);base64,(?P<data>.+)$", re.IGNORECASE)
REMOTE_SCHEMES = {"http", "https"}
MIME_TO_SUFFIX = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/svg+xml": ".svg",
}


def process_markdown_images(markdown: str, job_dir: Path) -> tuple[str, list[str]]:
    assets_dir = job_dir / "source_files"
    assets_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    index = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal index
        alt = match.group(1) or "image"
        raw_target = match.group(2).strip()
        index += 1

        if raw_target.startswith("data:"):
            local_ref = _materialize_data_uri(raw_target, alt, assets_dir, index)
            if local_ref:
                return f"![{alt}]({local_ref})"
            warnings.append(f"Failed to decode inline image near '{alt}'")
            return ""

        parsed = urlparse(raw_target)
        if parsed.scheme in REMOTE_SCHEMES:
            local_ref = _download_remote_image(raw_target, alt, assets_dir, index)
            if local_ref:
                return f"![{alt}]({local_ref})"
            warnings.append(f"Failed to download remote image: {raw_target}")
            return match.group(0)

        local_ref = _copy_local_image(raw_target, alt, assets_dir, index)
        if local_ref:
            return f"![{alt}]({local_ref})"

        warnings.append(f"Local image not found and was removed: {raw_target}")
        return ""

    processed = IMAGE_PATTERN.sub(replace, markdown)
    return processed, warnings


def _safe_stem(text: str) -> str:
    stem = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "_", text).strip("_")
    return stem[:40] or "image"


def _unique_target(assets_dir: Path, stem: str, suffix: str, index: int) -> Path:
    candidate = assets_dir / f"{index:03d}_{stem}{suffix}"
    if not candidate.exists():
        return candidate
    counter = 2
    while True:
        retry = assets_dir / f"{index:03d}_{stem}_{counter}{suffix}"
        if not retry.exists():
            return retry
        counter += 1


def _materialize_data_uri(data_uri: str, alt: str, assets_dir: Path, index: int) -> str | None:
    match = DATA_URI_PATTERN.match(data_uri)
    if not match:
        return None
    mime = match.group("mime").lower()
    suffix = MIME_TO_SUFFIX.get(mime) or mimetypes.guess_extension(mime) or ".bin"
    target = _unique_target(assets_dir, _safe_stem(alt), suffix, index)
    try:
        target.write_bytes(base64.b64decode(match.group("data")))
    except Exception:
        return None
    return f"{assets_dir.name}/{target.name}"


def _download_remote_image(url: str, alt: str, assets_dir: Path, index: int) -> str | None:
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except Exception:
        return None

    content_type = (response.headers.get("content-type") or "").split(";")[0].strip().lower()
    suffix = (
        MIME_TO_SUFFIX.get(content_type)
        or Path(unquote(urlparse(url).path)).suffix
        or mimetypes.guess_extension(content_type)
        or ".bin"
    )
    if suffix == ".jpe":
        suffix = ".jpg"

    target = _unique_target(assets_dir, _safe_stem(alt), suffix, index)
    target.write_bytes(response.content)
    return f"{assets_dir.name}/{target.name}"


def _copy_local_image(path_like: str, alt: str, assets_dir: Path, index: int) -> str | None:
    parsed = urlparse(path_like)
    resolved: Path | None = None

    if parsed.scheme == "file":
        raw_path = unquote(parsed.path)
        if re.match(r"^/[A-Za-z]:/", raw_path):
            raw_path = raw_path[1:]
        resolved = Path(raw_path)
    elif parsed.scheme:
        return None
    else:
        candidate = Path(unquote(path_like))
        if candidate.is_absolute():
            resolved = candidate
        else:
            for base in (Path.cwd(), Path.cwd().parent):
                retry = (base / candidate).resolve()
                if retry.exists() and retry.is_file():
                    resolved = retry
                    break

    if resolved is None or not resolved.exists() or not resolved.is_file():
        return None

    suffix = resolved.suffix or ".bin"
    target = _unique_target(assets_dir, _safe_stem(alt), suffix, index)
    shutil.copy2(resolved, target)
    return f"{assets_dir.name}/{target.name}"
