from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import AppConfig
from .http_client import JianyingHttpClient, ResponseParseError, validate_response_json
from .request_logging import append_request_log
from .repository import Repository
from .storage import write_json, write_text


@dataclass
class CrawlContext:
    config: AppConfig
    client: JianyingHttpClient
    repo: Repository


class BaseCrawler:
    crawler_name = "base"

    def __init__(self, context: CrawlContext) -> None:
        self.context = context

    @property
    def config(self) -> AppConfig:
        return self.context.config

    @property
    def client(self) -> JianyingHttpClient:
        return self.context.client

    @property
    def repo(self) -> Repository:
        return self.context.repo

    def raw_dir(self) -> Path:
        return self.config.raw_dir / self.crawler_name

    def meta_dir(self) -> Path:
        return self.config.meta_dir / self.crawler_name

    def download_dir(self) -> Path:
        return self.config.downloads_dir / self.crawler_name

    def save_raw_response(self, name: str, text: str) -> Path:
        path = self.raw_dir() / name
        write_text(path, text)
        return path

    def save_json(self, name: str, data: Any) -> Path:
        path = self.meta_dir() / name
        write_json(path, data)
        return path

    def parse_response_or_save_raw(self, response: Any, raw_name: str) -> tuple[dict[str, Any], str]:
        try:
            data = validate_response_json(response)
        except ResponseParseError:
            raw_path = self.save_raw_response(raw_name, response.text)
            append_request_log(
                self.config,
                scope="crawl",
                crawler_name=self.crawler_name,
                event="response_parse_failed",
                raw_name=raw_name,
                raw_path=str(raw_path),
                status_code=getattr(response, "status_code", ""),
                error=str(response.text[:400]) if getattr(response, "text", "") else "response_parse_failed",
            )
            raise
        return data, ""

    def parse_response_with_optional_raw(self, response: Any, raw_name: str) -> tuple[dict[str, Any], str]:
        try:
            data = validate_response_json(response)
            return data, ""
        except ResponseParseError:
            raw_path = self.save_raw_response(raw_name, response.text)
            append_request_log(
                self.config,
                scope="crawl",
                crawler_name=self.crawler_name,
                event="response_parse_failed",
                raw_name=raw_name,
                raw_path=str(raw_path),
                status_code=getattr(response, "status_code", ""),
                error=str(response.text[:400]) if getattr(response, "text", "") else "response_parse_failed",
            )
            return validate_response_json(response), str(raw_path)

    def run(self) -> None:
        raise NotImplementedError
