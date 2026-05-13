from __future__ import annotations

import json
import mimetypes
import re
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests
import time

from .base import CrawlContext
from .request_logging import append_request_log
from .storage import file_md5, write_bytes


@dataclass
class DownloadResult:
    download_id: int
    resource_id: str
    status: str
    target_path: str = ""
    file_md5: str = ""
    error: str = ""


@dataclass
class DownloadRunSummary:
    results: list[DownloadResult]
    batches: int
    queue_drained: bool
    stalled: bool = False


class DownloadService:
    TEMPLATE_STYLE_CRAWLERS = {
        "template",
        "marketing_template",
        "text_template",
        "subtitle_template",
        "material_pack",
    }

    def __init__(self, context: CrawlContext) -> None:
        self.context = context
        self.session = requests.Session()
        self.session.trust_env = False

    @property
    def repo(self):
        return self.context.repo

    @property
    def config(self):
        return self.context.config

    def run_pending(
        self,
        crawler_name: str,
        limit: int = 10,
        resource_id: str | None = None,
        url_kind: str | None = None,
        interval_seconds: float | None = None,
        include_auxiliary: bool = False,
    ) -> list[DownloadResult]:
        effective_interval_seconds = self.config.download_interval_seconds if interval_seconds is None else interval_seconds
        rows = self.repo.list_pending_downloads(
            crawler_name=crawler_name,
            limit=limit,
            resource_id=resource_id,
            url_kind=url_kind,
            include_auxiliary=include_auxiliary,
        )
        results: list[DownloadResult] = []
        self.log_event(
            crawler_name=crawler_name,
            event="download_batch_start",
            requested_limit=limit,
            pending_count=len(rows),
            resource_id_filter=resource_id or "",
            url_kind_filter=url_kind or "",
            interval_seconds=effective_interval_seconds,
            include_auxiliary=include_auxiliary,
        )
        for index, row in enumerate(rows, start=1):
            result = self.download_one(
                download_id=int(row["id"]),
                resource_id=str(row["resource_id"]),
                url=str(row["url"]),
                url_kind=str(row["url_kind"]),
                title=str(row.get("title") or ""),
                parent_resource_id=str(row.get("parent_resource_id") or ""),
                source_kind=str(row.get("source_kind") or ""),
                existing_target_path=str(row.get("target_path") or ""),
                crawler_name=crawler_name,
            )
            results.append(result)
            if effective_interval_seconds > 0 and index < len(rows):
                self.log_event(
                    crawler_name=crawler_name,
                    event="download_interval_sleep",
                    seconds=effective_interval_seconds,
                    after_download_id=result.download_id,
                    after_resource_id=result.resource_id,
                )
                time.sleep(effective_interval_seconds)
        self.log_event(
            crawler_name=crawler_name,
            event="download_batch_complete",
            requested_limit=limit,
            processed_count=len(results),
            success_count=sum(1 for result in results if result.status == "done"),
            failed_count=sum(1 for result in results if result.status != "done"),
        )
        return results

    def run_until_empty(
        self,
        crawler_name: str,
        batch_limit: int = 50,
        resource_id: str | None = None,
        url_kind: str | None = None,
        interval_seconds: float | None = None,
        include_auxiliary: bool = False,
    ) -> DownloadRunSummary:
        all_results: list[DownloadResult] = []
        batch_index = 0
        self.log_event(
            crawler_name=crawler_name,
            event="download_loop_start",
            batch_limit=batch_limit,
            resource_id_filter=resource_id or "",
            url_kind_filter=url_kind or "",
            interval_seconds=self.config.download_interval_seconds if interval_seconds is None else interval_seconds,
            include_auxiliary=include_auxiliary,
        )

        while True:
            batch_index += 1
            batch_results = self.run_pending(
                crawler_name=crawler_name,
                limit=batch_limit,
                resource_id=resource_id,
                url_kind=url_kind,
                interval_seconds=interval_seconds,
                include_auxiliary=include_auxiliary,
            )
            if not batch_results:
                self.log_event(
                    crawler_name=crawler_name,
                    event="download_loop_complete",
                    batches=batch_index - 1,
                    total_processed=len(all_results),
                    success_count=sum(1 for result in all_results if result.status == "done"),
                    failed_count=sum(1 for result in all_results if result.status != "done"),
                    queue_drained=True,
                )
                return DownloadRunSummary(
                    results=all_results,
                    batches=batch_index - 1,
                    queue_drained=True,
                )

            all_results.extend(batch_results)
            batch_success_count = sum(1 for result in batch_results if result.status == "done")
            batch_failed_count = len(batch_results) - batch_success_count
            self.log_event(
                crawler_name=crawler_name,
                event="download_loop_batch_complete",
                batch_index=batch_index,
                processed_count=len(batch_results),
                success_count=batch_success_count,
                failed_count=batch_failed_count,
            )
            if batch_success_count == 0:
                self.log_event(
                    crawler_name=crawler_name,
                    event="download_loop_stalled",
                    batches=batch_index,
                    total_processed=len(all_results),
                    failed_count=sum(1 for result in all_results if result.status != "done"),
                    reason="no_success_in_batch",
                )
                return DownloadRunSummary(
                    results=all_results,
                    batches=batch_index,
                    queue_drained=False,
                    stalled=True,
                )

    def download_one(
        self,
        download_id: int,
        resource_id: str,
        url: str,
        url_kind: str,
        title: str,
        parent_resource_id: str,
        source_kind: str,
        existing_target_path: str,
        crawler_name: str,
    ) -> DownloadResult:
        self.log_event(
            crawler_name=crawler_name,
            event="download_start",
            download_id=download_id,
            resource_id=resource_id,
            url_kind=url_kind,
            title=title,
            parent_resource_id=parent_resource_id,
            source_kind=source_kind,
            existing_target_path=existing_target_path,
            url=url,
        )
        try:
            content, content_type = self.fetch_content(
                url=url,
                crawler_name=crawler_name,
                download_id=download_id,
                resource_id=resource_id,
                url_kind=url_kind,
                title=title,
            )
            extension = self.choose_extension(
                url=url,
                content_type=content_type,
                content=content,
            )
            target_path = self.build_target_path(
                crawler_name=crawler_name,
                resource_id=resource_id,
                title=title,
                url_kind=url_kind,
                extension=extension,
                parent_resource_id=parent_resource_id,
                source_kind=source_kind,
                existing_target_path=existing_target_path,
            )
            write_bytes(target_path, content)
            md5_value = file_md5(target_path)
            self.repo.mark_download_status(
                download_id=download_id,
                status="done",
                target_path=str(target_path),
                file_md5=md5_value,
            )
            self.log_event(
                crawler_name=crawler_name,
                event="download_done",
                download_id=download_id,
                resource_id=resource_id,
                url_kind=url_kind,
                content_type=content_type,
                bytes=len(content),
                target_path=str(target_path),
                file_md5=md5_value,
            )
            return DownloadResult(
                download_id=download_id,
                resource_id=resource_id,
                status="done",
                target_path=str(target_path),
                file_md5=md5_value,
            )
        except Exception as exc:
            self.repo.mark_download_status(download_id=download_id, status="failed")
            self.log_event(
                crawler_name=crawler_name,
                event="download_failed",
                download_id=download_id,
                resource_id=resource_id,
                url_kind=url_kind,
                url=url,
                error=str(exc),
            )
            return DownloadResult(
                download_id=download_id,
                resource_id=resource_id,
                status="failed",
                error=str(exc),
            )

    def fetch_content(
        self,
        url: str,
        crawler_name: str,
        download_id: int,
        resource_id: str,
        url_kind: str,
        title: str,
    ) -> tuple[bytes, str]:
        last_error: Exception | None = None

        for attempt in range(self.config.retry_count + 1):
            started_at = time.perf_counter()
            self.log_event(
                crawler_name=crawler_name,
                event="request_start",
                download_id=download_id,
                resource_id=resource_id,
                url_kind=url_kind,
                title=title,
                attempt=attempt + 1,
                max_attempts=self.config.retry_count + 1,
                url=url,
            )
            try:
                with self.session.get(
                    url,
                    timeout=self.config.request_timeout_seconds,
                    stream=True,
                ) as response:
                    response.raise_for_status()
                    content = response.content
                    content_type = response.headers.get("Content-Type", "")
                    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                    self.log_event(
                        crawler_name=crawler_name,
                        event="request_success",
                        download_id=download_id,
                        resource_id=resource_id,
                        url_kind=url_kind,
                        attempt=attempt + 1,
                        status_code=response.status_code,
                        content_type=content_type,
                        content_length_header=response.headers.get("Content-Length", ""),
                        bytes=len(content),
                        elapsed_ms=elapsed_ms,
                        url=url,
                    )
                    return content, content_type
            except Exception as exc:
                last_error = exc
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                if attempt >= self.config.retry_count:
                    self.log_event(
                        crawler_name=crawler_name,
                        event="request_failed",
                        download_id=download_id,
                        resource_id=resource_id,
                        url_kind=url_kind,
                        attempt=attempt + 1,
                        elapsed_ms=elapsed_ms,
                        error=str(exc),
                        url=url,
                    )
                    raise
                self.log_event(
                    crawler_name=crawler_name,
                    event="request_retry",
                    download_id=download_id,
                    resource_id=resource_id,
                    url_kind=url_kind,
                    attempt=attempt + 1,
                    elapsed_ms=elapsed_ms,
                    retry_backoff_seconds=self.config.retry_backoff_seconds,
                    error=str(exc),
                    url=url,
                )
                time.sleep(self.config.retry_backoff_seconds)

        if last_error is not None:
            raise last_error
        raise RuntimeError("Download failed without an explicit error.")

    def log_event(self, crawler_name: str, event: str, **fields: object) -> None:
        normalized = {key: self.normalize_log_value(value) for key, value in fields.items()}
        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "scope": "download",
            "crawler_name": crawler_name,
            "event": event,
            **normalized,
        }
        line = json.dumps(entry, ensure_ascii=False)
        date_key = datetime.now().strftime("%Y%m%d")
        crawler_log_path = self.config.logs_dir / "downloads" / crawler_name / f"{date_key}.log"
        all_log_path = self.config.logs_dir / "downloads" / "_all" / f"{date_key}.log"
        self.append_legacy_log_line(crawler_log_path, line)
        self.append_legacy_log_line(all_log_path, line)
        append_request_log(
            self.config,
            scope="download",
            crawler_name=crawler_name,
            event=event,
            **normalized,
        )

    def append_legacy_log_line(self, path: Path, line: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(f"{line}\n")

    def normalize_log_value(self, value: object) -> object:
        if isinstance(value, Path):
            return str(value)
        return value

    def build_target_path(
        self,
        crawler_name: str,
        resource_id: str,
        title: str,
        url_kind: str,
        extension: str,
        parent_resource_id: str = "",
        source_kind: str = "",
        existing_target_path: str = "",
    ) -> Path:
        if existing_target_path:
            existing_path = Path(existing_target_path)
            if existing_path.suffix.lower() == (extension or ".bin").lower():
                return existing_path

        resource_dir = self.build_download_dir(
            crawler_name=crawler_name,
            resource_id=resource_id,
            title=title,
            parent_resource_id=parent_resource_id,
            source_kind=source_kind,
        )
        base_name = self.build_resource_base_name(title=title, resource_id=resource_id)
        filename = self.build_filename(base_name=base_name, url_kind=url_kind, extension=extension)
        return self.ensure_unique_target_path(resource_dir / filename, resource_id=resource_id)

    def build_download_dir(
        self,
        crawler_name: str,
        resource_id: str,
        title: str,
        parent_resource_id: str,
        source_kind: str,
    ) -> Path:
        base_dir = self.config.downloads_dir / crawler_name
        if crawler_name not in self.TEMPLATE_STYLE_CRAWLERS:
            return base_dir

        if parent_resource_id:
            parent_name = self.repo.get_item_title(crawler_name=crawler_name, resource_id=parent_resource_id) or parent_resource_id
            parent_dir_name = self.build_resource_base_name(title=parent_name, resource_id=parent_resource_id)
            dependency_group = self.classify_dependency_group(source_kind=source_kind)
            return base_dir / parent_dir_name / dependency_group

        main_dir_name = self.build_resource_base_name(title=title, resource_id=resource_id)
        return base_dir / main_dir_name / "main"

    def classify_dependency_group(self, source_kind: str) -> str:
        normalized = (source_kind or "").lower()
        if "font" in normalized:
            return "dependencies_fonts"
        if "flower" in normalized:
            return "dependencies_flower"
        if "subtitle" in normalized:
            return "dependencies_subtitle"
        if "text" in normalized:
            return "dependencies_text"
        if "recipe" in normalized:
            return "dependencies_recipe"
        if "dependency" in normalized:
            return "dependencies_misc"
        return "dependencies_misc"

    def build_resource_base_name(self, title: str, resource_id: str) -> str:
        cleaned = self.sanitize_filename(title)
        if cleaned:
            return cleaned
        return resource_id

    def build_filename(self, base_name: str, url_kind: str, extension: str) -> str:
        normalized_extension = extension or ".bin"
        if url_kind in {"primary_asset_0", "download_info"}:
            return f"{base_name}{normalized_extension}"
        safe_kind = self.sanitize_filename(url_kind) or "asset"
        return f"{base_name}__{safe_kind}{normalized_extension}"

    def ensure_unique_target_path(self, target_path: Path, resource_id: str) -> Path:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if not target_path.exists():
            return target_path

        stem = target_path.stem
        suffix = target_path.suffix
        for index in range(2, 10000):
            candidate = target_path.with_name(f"{stem}_{index}{suffix}")
            if not candidate.exists():
                return candidate
        raise RuntimeError(f"Unable to allocate unique filename for resource {resource_id}: {target_path}")

    def sanitize_filename(self, value: str) -> str:
        cleaned = re.sub(r"[<>:\"/\\\\|?*\x00-\x1f]", " ", value)
        cleaned = re.sub(r"\s+", " ", cleaned).strip().strip(".")
        if not cleaned:
            return ""
        reserved_names = {
            "CON",
            "PRN",
            "AUX",
            "NUL",
            "COM1",
            "COM2",
            "COM3",
            "COM4",
            "COM5",
            "COM6",
            "COM7",
            "COM8",
            "COM9",
            "LPT1",
            "LPT2",
            "LPT3",
            "LPT4",
            "LPT5",
            "LPT6",
            "LPT7",
            "LPT8",
            "LPT9",
        }
        if cleaned.upper() in reserved_names:
            cleaned = f"_{cleaned}"
        return cleaned[:120]

    def choose_extension(self, url: str, content_type: str, content: bytes) -> str:
        extension = self.guess_extension_from_content_type(content_type)
        if extension:
            return extension

        extension = self.guess_extension_from_magic(content)
        if extension:
            return extension

        return self.guess_extension_from_url(url)

    def guess_extension_from_content_type(self, content_type: str) -> str:
        normalized = content_type.split(";", 1)[0].strip().lower()
        if not normalized:
            return ""

        explicit_map = {
            "audio/mpeg": ".mp3",
            "audio/mp3": ".mp3",
            "audio/wav": ".wav",
            "audio/x-wav": ".wav",
            "audio/ogg": ".ogg",
            "audio/aac": ".aac",
            "audio/flac": ".flac",
            "audio/mp4": ".m4a",
            "video/mp4": ".mp4",
            "application/zip": ".zip",
            "application/x-zip-compressed": ".zip",
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/gif": ".gif",
            "image/webp": ".webp",
        }
        if normalized in explicit_map:
            return explicit_map[normalized]

        extension = mimetypes.guess_extension(normalized)
        if extension:
            return extension
        return ""

    def guess_extension_from_magic(self, content: bytes) -> str:
        if not content:
            return ""

        if content.startswith(b"ID3") or content[:2] == b"\xff\xfb":
            return ".mp3"
        if content.startswith(b"RIFF") and content[8:12] == b"WAVE":
            return ".wav"
        if content.startswith(b"OggS"):
            return ".ogg"
        if content.startswith(b"\x89PNG\r\n\x1a\n"):
            return ".png"
        if content.startswith((b"GIF87a", b"GIF89a")):
            return ".gif"
        if content.startswith(b"\xff\xd8\xff"):
            return ".jpg"
        if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
            return ".webp"
        if content.startswith(b"PK\x03\x04"):
            return ".zip"
        if len(content) >= 12 and content[4:8] == b"ftyp":
            return ".mp4"
        return ""

    def guess_extension_from_url(self, url: str) -> str:
        parsed = urlparse(url)
        suffix = Path(parsed.path).suffix
        if suffix:
            return suffix

        guessed, _ = mimetypes.guess_type(url)
        if guessed:
            extension = mimetypes.guess_extension(guessed)
            if extension:
                return extension
        return ".bin"
