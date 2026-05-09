from __future__ import annotations

import io
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

import requests
from qcloud_cos import CosConfig, CosS3Client

from .config import Settings


@dataclass
class CallbackResult:
    success: bool
    error: str | None = None


def upload_to_cos(buffer: bytes, cos_path: str, settings: Settings) -> str:
    if not settings.cos_enabled:
        raise RuntimeError("COS is not configured. Missing COS_SECRET_ID / COS_SECRET_KEY / COS_BUCKET.")

    client = CosS3Client(
        CosConfig(
            Region=settings.cos_region,
            Secret_id=settings.cos_secret_id,
            Secret_key=settings.cos_secret_key,
            Token=None,
            Scheme="https",
        )
    )
    client.put_object(Bucket=settings.cos_bucket, Body=buffer, Key=cos_path)
    return cos_path


def notify_report_server(
    report_id: str,
    file_url: str | None,
    word_url: str | None,
    ppt_url: str,
    callback_url: str | None,
) -> CallbackResult:
    if not callback_url:
        return CallbackResult(success=False, error="REPORT_CALLBACK_URL not configured")

    payload = {
        "success": "success",
        "msg": "\u62a5\u544a\u4e0a\u4f20\u6210\u529f",
        "data": {
            "reportId": report_id,
            "fileUrl": normalize_to_relative(file_url or ""),
            "pptUrl": normalize_to_relative(ppt_url),
            "wordUrl": normalize_to_relative(word_url or ""),
        },
    }

    try:
        response = requests.post(callback_url, json=payload, timeout=20)
        response.raise_for_status()
        try:
            response.json()
        except json.JSONDecodeError:
            pass
        return CallbackResult(success=True)
    except Exception as exc:
        return CallbackResult(success=False, error=str(exc))


def notify_report_failure(
    report_id: str,
    file_url: str | None,
    word_url: str | None,
    error_message: str,
    callback_url: str | None,
) -> CallbackResult:
    if not callback_url:
        return CallbackResult(success=False, error="REPORT_CALLBACK_URL not configured")

    payload = {
        "success": "failed",
        "msg": "\u62a5\u544a\u751f\u6210\u5931\u8d25",
        "data": {
            "reportId": report_id,
            "fileUrl": normalize_to_relative(file_url or ""),
            "pptUrl": "",
            "wordUrl": normalize_to_relative(word_url or ""),
            "error": _safe_callback_error(error_message),
        },
    }

    try:
        response = requests.post(callback_url, json=payload, timeout=20)
        response.raise_for_status()
        try:
            response.json()
        except json.JSONDecodeError:
            pass
        return CallbackResult(success=True)
    except Exception as exc:
        return CallbackResult(success=False, error=str(exc))


def _safe_callback_error(error_message: str) -> str:
    text = str(error_message or "PPT generation failed")
    text = re.sub(r"(?i)(api[_-]?key|auth[_-]?token|x-api-key)(['\"\s:=]+)[A-Za-z0-9._-]{12,}", r"\1\2<redacted>", text)
    text = re.sub(r"sk-[A-Za-z0-9._-]{12,}", "sk-<redacted>", text)
    return text[:1000]


def normalize_to_relative(url: str) -> str:
    if not url:
        return ""
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            return parsed.path.lstrip("/")
    except Exception:
        pass
    return url.lstrip("/")


def build_result_zip(
    native_pptx_path: Path,
    notes_path: Path | None,
    title: str,
    mapped_native_pptx_path: Path | None = None,
    *,
    source_han_native_pptx_path: Path | None = None,
) -> bytes:
    safe_title = sanitize_title(title)
    notes_text = ""
    if notes_path and notes_path.exists():
        notes_text = notes_markdown_to_text(notes_path.read_text(encoding="utf-8", errors="replace"))

    mapped_native_pptx_path = mapped_native_pptx_path or source_han_native_pptx_path
    pptx_path = mapped_native_pptx_path if mapped_native_pptx_path and mapped_native_pptx_path.exists() else native_pptx_path
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{safe_title}.pptx", pptx_path.read_bytes())
        archive.writestr(f"{safe_title}_\u8bb2\u89e3\u6587\u7a3f.txt", "\ufeff" + notes_text)
    return buffer.getvalue()


def sanitize_title(title: str) -> str:
    safe = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9_-]+", "_", title).strip("_")
    return safe[:50] or "presentation"


def notes_markdown_to_text(content: str) -> str:
    text = content.replace("\r\n", "\n")
    text = re.sub(r"^#\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^##\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^###\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[-*]\s+", "- ", text, flags=re.MULTILINE)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
