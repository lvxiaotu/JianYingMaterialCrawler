from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import AppConfig


REQUEST_LOG_SCOPES = ("crawl", "download")


def normalize_log_value(value: object) -> object:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(key): normalize_log_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [normalize_log_value(item) for item in value]
    return str(value)


def append_request_log(
    config: AppConfig,
    scope: str,
    crawler_name: str,
    event: str,
    **fields: object,
) -> None:
    if scope not in REQUEST_LOG_SCOPES:
        raise ValueError(f"Unsupported request log scope: {scope}")

    now = datetime.now()
    entry = {
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        "scope": scope,
        "crawler_name": crawler_name or "_unknown",
        "event": event,
    }
    for key, value in fields.items():
        entry[key] = normalize_log_value(value)

    line = json.dumps(entry, ensure_ascii=False)
    date_key = now.strftime("%Y%m%d")
    crawler_path = config.logs_dir / "requests" / scope / (crawler_name or "_unknown") / f"{date_key}.log"
    all_path = config.logs_dir / "requests" / scope / "_all" / f"{date_key}.log"
    append_log_line(crawler_path, line)
    append_log_line(all_path, line)


def append_log_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"{line}\n")


def tail_request_logs(
    config: AppConfig,
    scope: str | None = None,
    crawler_name: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    selected_scope = (scope or "all").strip().lower()
    selected_crawler = (crawler_name or "_all").strip() or "_all"

    scopes = list(REQUEST_LOG_SCOPES) if selected_scope in {"", "all", "*"} else [selected_scope]
    lines: list[str] = []

    for scope_name in scopes:
        if scope_name not in REQUEST_LOG_SCOPES:
            continue
        target_dir = config.logs_dir / "requests" / scope_name / selected_crawler
        lines.extend(read_latest_log_lines(target_dir, limit))

        # 兼容旧下载日志目录，避免改造前后的日志都能在前端看到
        if scope_name == "download":
            legacy_dir = config.logs_dir / "downloads" / selected_crawler
            lines.extend(read_latest_log_lines(legacy_dir, limit))

    parsed: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_line in reversed(lines):
        stripped = raw_line.strip()
        if not stripped or stripped in seen:
            continue
        seen.add(stripped)
        try:
            entry = json.loads(stripped)
        except json.JSONDecodeError:
            entry = {
                "timestamp": "",
                "scope": scope or "unknown",
                "crawler_name": crawler_name or "",
                "event": "raw_line",
                "message": stripped,
            }

        if selected_scope not in {"", "all", "*"} and str(entry.get("scope") or "").lower() != selected_scope:
            continue
        if selected_crawler != "_all" and str(entry.get("crawler_name") or "") != selected_crawler:
            continue
        parsed.append(entry)

    parsed.sort(key=lambda item: str(item.get("timestamp") or ""))
    return parsed[-limit:]


def read_latest_log_lines(directory: Path, limit: int) -> list[str]:
    if not directory.exists():
        return []

    files = sorted(directory.glob("*.log"), key=lambda item: item.name, reverse=True)
    if not files:
        return []

    lines: list[str] = []
    for file_path in files[:3]:
        try:
            file_lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        if file_lines:
            lines.extend(file_lines[-limit:])
        if len(lines) >= limit * 2:
            break
    return lines[-limit:]
