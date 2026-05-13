from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config" / "settings.json"


def strip_json_comments(text: str) -> str:
    result: list[str] = []
    in_string = False
    escape = False
    index = 0
    length = len(text)

    while index < length:
        char = text[index]
        next_char = text[index + 1] if index + 1 < length else ""

        if in_string:
            result.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            index += 1
            continue

        if char == '"':
            in_string = True
            result.append(char)
            index += 1
            continue

        if char == "/" and next_char == "/":
            index += 2
            while index < length and text[index] not in "\r\n":
                index += 1
            continue

        if char == "/" and next_char == "*":
            index += 2
            while index + 1 < length and not (text[index] == "*" and text[index + 1] == "/"):
                index += 1
            index += 2
            continue

        result.append(char)
        index += 1

    return "".join(result)


@dataclass
class AppConfig:
    data: dict[str, Any]

    @property
    def storage_dir(self) -> Path:
        return Path(self.data["storage_dir"])

    @property
    def database_path(self) -> Path:
        return Path(self.data["database_path"])

    @property
    def database_url(self) -> str:
        return str(os.getenv("JY_DATABASE_URL") or self.data.get("database_url") or "").strip()

    @property
    def use_postgres(self) -> bool:
        return self.database_url.startswith(("postgresql://", "postgres://"))

    @property
    def database_target(self) -> str:
        if self.use_postgres:
            return self.database_url
        return str(self.database_path)

    @property
    def raw_dir(self) -> Path:
        return Path(self.data["raw_dir"])

    @property
    def meta_dir(self) -> Path:
        return Path(self.data["meta_dir"])

    @property
    def downloads_dir(self) -> Path:
        return Path(self.data["downloads_dir"])

    @property
    def logs_dir(self) -> Path:
        return Path(self.data["logs_dir"])

    @property
    def state_dir(self) -> Path:
        return Path(self.data["state_dir"])

    @property
    def structure_dir(self) -> Path:
        configured = self.data.get("structure_dir")
        if configured:
            return Path(configured)
        return self.storage_dir / "structure"

    @property
    def default_query(self) -> dict[str, str]:
        return dict(self.data.get("default_query", {}))

    @property
    def default_headers(self) -> dict[str, str]:
        return dict(self.data.get("default_headers", {}))

    @property
    def auth(self) -> dict[str, str]:
        return dict(self.data.get("auth", {}))

    @property
    def replicate_auth(self) -> dict[str, Any]:
        return dict(self.data.get("replicate_auth", {}))

    @property
    def concurrency(self) -> int:
        return int(self.data.get("concurrency", 4))

    @property
    def request_timeout_seconds(self) -> int:
        return int(self.data.get("request_timeout_seconds", 30))

    @property
    def retry_count(self) -> int:
        return int(self.data.get("retry_count", 2))

    @property
    def retry_backoff_seconds(self) -> int:
        return int(self.data.get("retry_backoff_seconds", 2))

    @property
    def download_interval_seconds(self) -> float:
        return float(self.data.get("download_interval_seconds", 1.0))

    @property
    def enabled_crawlers(self) -> dict[str, bool]:
        return dict(self.data.get("enabled_crawlers", {}))


def load_config() -> AppConfig:
    with CONFIG_PATH.open("r", encoding="utf-8") as fh:
        return AppConfig(json.loads(strip_json_comments(fh.read())))


def save_config(new_data: dict[str, Any]) -> AppConfig:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8") as fh:
        json.dump(new_data, fh, ensure_ascii=False, indent=2)
    return AppConfig(new_data)


def ensure_storage_dirs(config: AppConfig) -> None:
    paths = [
        config.storage_dir,
        config.raw_dir,
        config.meta_dir,
        config.downloads_dir,
        config.logs_dir,
        config.state_dir,
        config.structure_dir,
    ]
    if not config.use_postgres:
        paths.append(config.database_path.parent)

    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
