"""Usage and observability logging."""

from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path
from typing import Any


class UsageLogger:
    """Append-only usage recorder for direct API calls."""

    def __init__(self, project_path: Path) -> None:
        logs_dir = project_path / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        self.usage_path = logs_dir / "usage.jsonl"
        self.compat_path = logs_dir / "api_ppt.log"
        self.transcript_path = logs_dir / "llm_transcript.jsonl"
        self.transcript_dir = logs_dir / "transcripts"
        self.transcript_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._transcript_counter = 0

    def log(self, label: str, **fields: Any) -> None:
        record = {
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "label": label,
            **fields,
        }
        usage = record.get("usage")
        if isinstance(usage, dict):
            record["cache"] = {
                key: usage.get(key)
                for key in (
                    "prompt_cache_hit_tokens",
                    "prompt_cache_miss_tokens",
                    "cache_read_input_tokens",
                    "cache_creation_input_tokens",
                )
                if key in usage
            }
        line = json.dumps(record, ensure_ascii=False)
        with self._lock:
            with self.usage_path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
            # Compatibility with the first automation draft and current open tabs.
            with self.compat_path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")

    def log_transcript(
        self,
        label: str,
        *,
        system: str | None = None,
        prompt: str | None = None,
        response: str | None = None,
        stdout: str | None = None,
        stderr: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Write full model-call transcript files plus a JSONL index."""
        metadata = metadata or {}
        with self._lock:
            self._transcript_counter += 1
            counter = self._transcript_counter
            safe_label = self._safe_filename(str(label))
            stem_parts = [f"{counter:04d}", safe_label]
            slide = metadata.get("slide")
            if slide:
                stem_parts.append(self._safe_filename(str(slide))[:80])
            stem = "_".join(stem_parts)

            files: dict[str, str] = {}
            for suffix, value in (
                ("system.txt", system),
                ("prompt.md", prompt),
                ("response.txt", response),
                ("stdout.txt", stdout),
                ("stderr.txt", stderr),
            ):
                if value is None:
                    continue
                path = self.transcript_dir / f"{stem}.{suffix}"
                path.write_text(self._redact(value), encoding="utf-8")
                files[suffix] = str(path.relative_to(self.transcript_path.parent))

            record = {
                "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "label": label,
                "files": files,
                "prompt_chars": len(prompt) if prompt is not None else None,
                "response_chars": len(response) if response is not None else None,
                "stdout_chars": len(stdout) if stdout is not None else None,
                "stderr_chars": len(stderr) if stderr is not None else None,
                **metadata,
            }
            with self.transcript_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    @staticmethod
    def _safe_filename(value: str) -> str:
        safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in value)
        safe = re.sub(r"_+", "_", safe).strip("._")
        return safe or "call"

    @staticmethod
    def _redact(value: str) -> str:
        text = re.sub(r"sk-[A-Za-z0-9_-]{12,}", "sk-REDACTED", value)
        text = re.sub(
            r"(?i)(api[_-]?key|auth[_-]?token|x-api-key)(['\"\s:=]+)[A-Za-z0-9._-]{12,}",
            r"\1\2REDACTED",
            text,
        )
        return text
