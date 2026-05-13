from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import uuid
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .config import CONFIG_PATH, ensure_storage_dirs, load_config, save_config
from .crawlers import CRAWLER_MAP
from .request_logging import tail_request_logs
from .repository import Repository


ROOT_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "settings.html"
README_PATH = ROOT_DIR / "README.md"


def utc_now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_readme_commands(readme_path: Path) -> list[str]:
    if not readme_path.exists():
        return []
    text = readme_path.read_text(encoding="utf-8", errors="ignore")
    commands: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("python -m jianying_crawler.cli "):
            commands.append(stripped)
    deduped: list[str] = []
    seen: set[str] = set()
    for command in commands:
        if command in seen:
            continue
        seen.add(command)
        deduped.append(command)
    return deduped


def build_default_commands() -> list[str]:
    commands: list[str] = [
        "python -m jianying_crawler.cli init-db",
        "python -m jianying_crawler.cli migrate-sqlite",
        "python -m jianying_crawler.cli build-structure",
        "python -m jianying_crawler.cli cleanup-downloads",
    ]

    crawler_names = sorted(CRAWLER_MAP.keys())
    auxiliary_crawlers = {
        "marketing_template",
        "material_pack",
        "subtitle_template",
        "template",
        "text_template",
    }

    for crawler_name in crawler_names:
        commands.append(f"python -m jianying_crawler.cli crawl {crawler_name}")

    for crawler_name in crawler_names:
        commands.append(f"python -m jianying_crawler.cli download {crawler_name} --limit 50")
        commands.append(f"python -m jianying_crawler.cli download {crawler_name} --limit 50 --until-empty")
        if crawler_name in auxiliary_crawlers:
            commands.append(
                f"python -m jianying_crawler.cli download {crawler_name} --limit 50 --include-auxiliary --until-empty"
            )

    return commands


def merge_commands(primary_commands: list[str], extra_commands: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for command in primary_commands + extra_commands:
        normalized = " ".join(str(command).strip().split())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        merged.append(normalized)
    return merged


def build_command_cards(commands: list[str]) -> list[dict[str, object]]:
    cards: list[dict[str, object]] = []
    for command in commands:
        cards.append(describe_command(command))
    return cards


def describe_command(command: str) -> dict[str, object]:
    normalized = normalize_command(command)
    tokens = normalized.split()
    prefix_tokens = tokens[:3]
    arg_tokens = tokens[3:]
    action = arg_tokens[0] if arg_tokens else ""
    crawler_name = ""
    for token in arg_tokens[1:]:
        if not token.startswith("--"):
            crawler_name = token
            break

    title = "CLI 命令"
    summary = "执行一条 JianYing crawler CLI 命令。"
    tags: list[str] = []
    category = "other"
    category_label = "其他命令"

    if action == "init-db":
        title = "初始化数据库"
        summary = "创建或初始化当前配置对应的数据库表结构。"
        tags = ["数据库", "初始化"]
        category = "database"
        category_label = "数据库"
    elif action == "migrate-sqlite":
        title = "迁移 SQLite 到 PostgreSQL"
        summary = "把现有 SQLite 数据迁移到 PostgreSQL。"
        tags = ["数据库", "迁移", "PostgreSQL"]
        category = "database"
        category_label = "数据库"
    elif action == "build-structure":
        title = "生成资源结构报告"
        summary = "整理当前下载目录结构，输出资源分级结构报告。"
        tags = ["结构", "报告"]
        category = "report"
        category_label = "结构与报告"
    elif action == "cleanup-downloads":
        title = "清理重复下载记录"
        summary = "清理数据库中的重复下载记录，不删除磁盘文件。"
        tags = ["下载", "清理"]
        category = "maintenance"
        category_label = "清理与维护"
    elif action == "crawl":
        human_name = humanize_crawler_name(crawler_name)
        title = f"抓取 {human_name}"
        summary = f"抓取 {human_name} 链路的分类、列表和详情，并把待下载资源写入数据库。"
        tags = ["抓取", human_name]
        category = "crawl"
        category_label = "抓取"
    elif action == "download":
        human_name = humanize_crawler_name(crawler_name)
        title = f"下载 {human_name}"
        summary = f"下载 {human_name} 链路中已经录入 pending 的资源。"
        if "--until-empty" in arg_tokens:
            summary = f"持续下载 {human_name} 链路资源，直到当前链路没有待下载记录。"
        if "--include-auxiliary" in arg_tokens:
            summary += " 包含模板依赖或辅助资源。"
        tags = ["下载", human_name]
        if "--until-empty" in arg_tokens:
            tags.append("跑空队列")
        if "--include-auxiliary" in arg_tokens:
            tags.append("含依赖")
        category = "download"
        category_label = "下载"

    return {
        "command": normalized,
        "title": title,
        "summary": summary,
        "option_label": build_command_option_label(title, arg_tokens),
        "prefix": prefix_tokens,
        "segments": build_command_segments(arg_tokens),
        "tags": tags,
        "action": action,
        "crawler_name": crawler_name,
        "category": category,
        "category_label": category_label,
    }


def build_command_option_label(title: str, arg_tokens: list[str]) -> str:
    highlights: list[str] = []
    index = 0
    while index < len(arg_tokens):
        token = arg_tokens[index]
        if token in {"--limit", "--interval-seconds", "--url-kind", "--resource-id"}:
            if index + 1 < len(arg_tokens):
                highlights.append(f"{token} {arg_tokens[index + 1]}")
                index += 1
        elif token in {"--until-empty", "--include-auxiliary"}:
            highlights.append(token)
        index += 1

    if not highlights:
        return title
    return f"{title} | {' '.join(highlights)}"


def build_command_segments(tokens: list[str]) -> list[dict[str, str]]:
    segments: list[dict[str, str]] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.startswith("--"):
            value = ""
            if index + 1 < len(tokens) and not tokens[index + 1].startswith("--"):
                value = tokens[index + 1]
                index += 1
            segments.append(
                {
                    "kind": "option",
                    "text": token if not value else f"{token} {value}",
                }
            )
        else:
            segments.append(
                {
                    "kind": "arg",
                    "text": token,
                }
            )
        index += 1
    return segments


def humanize_crawler_name(crawler_name: str) -> str:
    mapping = {
        "effect": "普通特效",
        "filter": "滤镜",
        "flower": "花字",
        "marketing_template": "营销模板",
        "material_pack": "素材包",
        "music": "音乐",
        "official_material": "官方素材",
        "sound_effect": "音效",
        "sticker": "贴纸",
        "subtitle_template": "字幕模板",
        "task_effect": "任务特效",
        "template": "模板库",
        "text_template": "文字模板",
        "transition": "转场",
    }
    return mapping.get(crawler_name, crawler_name or "未知链路")


def normalize_command(command: str) -> str:
    normalized = " ".join(command.strip().split())
    if not normalized:
        raise ValueError("命令不能为空。")
    if not normalized.startswith("python -m jianying_crawler.cli "):
        raise ValueError("只允许执行 python -m jianying_crawler.cli ... 命令。")
    return normalized


@dataclass
class JobRecord:
    job_id: str
    command: str
    created_at: str
    status: str = "queued"
    started_at: str = ""
    finished_at: str = ""
    return_code: int | None = None
    process_id: int | None = None
    stop_requested: bool = False
    output_lines: list[str] = field(default_factory=list)

    def append_output(self, text: str) -> None:
        if not text:
            return
        for line in text.splitlines():
            if line:
                self.output_lines.append(line)
        self.output_lines = self.output_lines[-400:]

    def to_dict(self) -> dict[str, object]:
        return {
            "job_id": self.job_id,
            "command": self.command,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status,
            "return_code": self.return_code,
            "process_id": self.process_id,
            "stop_requested": self.stop_requested,
            "output": "\n".join(self.output_lines),
        }


class JobManager:
    def __init__(self, workdir: Path) -> None:
        self.workdir = workdir
        self._jobs: dict[str, JobRecord] = {}
        self._processes: dict[str, subprocess.Popen[str]] = {}
        self._lock = threading.Lock()

    def create_job(self, command: str) -> JobRecord:
        record = JobRecord(
            job_id=uuid.uuid4().hex[:12],
            command=normalize_command(command),
            created_at=utc_now_text(),
        )
        with self._lock:
            self._jobs[record.job_id] = record
        thread = threading.Thread(target=self._run_job, args=(record.job_id,), daemon=True)
        thread.start()
        invalidate_status_cache()
        return record

    def _run_job(self, job_id: str) -> None:
        with self._lock:
            record = self._jobs[job_id]
            record.status = "running"
            record.started_at = utc_now_text()

        process = subprocess.Popen(
            [sys.executable, "-m", "jianying_crawler.cli", *record.command.split()[3:]],
            cwd=str(self.workdir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        with self._lock:
            current = self._jobs[job_id]
            current.process_id = process.pid
            self._processes[job_id] = process

        try:
            if process.stdout is not None:
                for line in process.stdout:
                    with self._lock:
                        current = self._jobs[job_id]
                        current.append_output(line.rstrip("\r\n"))
            return_code = process.wait()
            with self._lock:
                current = self._jobs[job_id]
                current.return_code = return_code
                current.finished_at = utc_now_text()
                if current.stop_requested:
                    current.status = "stopped"
                else:
                    current.status = "done" if return_code == 0 else "failed"
        except Exception as exc:
            with self._lock:
                current = self._jobs[job_id]
                current.append_output(f"[webapp-error] {exc}")
                current.return_code = -1
                current.finished_at = utc_now_text()
                current.status = "failed"
        finally:
            with self._lock:
                self._processes.pop(job_id, None)
            invalidate_status_cache()

    def stop_job(self, job_id: str) -> dict[str, object]:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                raise KeyError(job_id)
            process = self._processes.get(job_id)
            if process is None or record.status not in {"queued", "running"}:
                return {"job_id": job_id, "stopped": False, "reason": "not_running"}
            record.stop_requested = True
            record.append_output("[webapp] stop requested")
            pid = process.pid

        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                process.terminate()
        finally:
            with self._lock:
                record = self._jobs[job_id]
                if not record.finished_at:
                    record.finished_at = utc_now_text()
                if record.return_code is None:
                    record.return_code = -15
                record.status = "stopped"
            invalidate_status_cache()
        return {"job_id": job_id, "stopped": True, "reason": "terminated"}

    def stop_all_jobs(self) -> dict[str, object]:
        with self._lock:
            running_job_ids = [
                job_id
                for job_id, record in self._jobs.items()
                if record.status in {"queued", "running"} and job_id in self._processes
            ]
        stopped: list[str] = []
        skipped: list[str] = []
        for job_id in running_job_ids:
            result = self.stop_job(job_id)
            if result.get("stopped"):
                stopped.append(job_id)
            else:
                skipped.append(job_id)
        return {
            "stopped_job_ids": stopped,
            "skipped_job_ids": skipped,
        }

    def list_jobs(self) -> list[dict[str, object]]:
        with self._lock:
            jobs = [record.to_dict() for record in self._jobs.values()]
        jobs.sort(key=lambda item: (str(item["created_at"]), str(item["job_id"])), reverse=True)
        return jobs[:20]

    def get_job(self, job_id: str) -> dict[str, object] | None:
        with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return None
            return record.to_dict()

    def list_running_jobs(self) -> list[dict[str, object]]:
        with self._lock:
            jobs = [
                record.to_dict()
                for record in self._jobs.values()
                if record.status in {"queued", "running"}
            ]
        jobs.sort(key=lambda item: (str(item["created_at"]), str(item["job_id"])), reverse=True)
        return jobs


JOB_MANAGER = JobManager(ROOT_DIR)
STATUS_CACHE_TTL_SECONDS = 10.0
_STATUS_CACHE_LOCK = threading.Lock()
_STATUS_CACHE: dict[str, object] = {
    "timestamp": 0.0,
    "payload": None,
    "refreshing": False,
}


def invalidate_status_cache() -> None:
    with _STATUS_CACHE_LOCK:
        _STATUS_CACHE["timestamp"] = 0.0
        _STATUS_CACHE["payload"] = None
        _STATUS_CACHE["refreshing"] = False


def read_template() -> str:
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def build_page_payload(message: str = "") -> dict[str, object]:
    if not message:
        with _STATUS_CACHE_LOCK:
            cached_payload = _STATUS_CACHE.get("payload")
            cached_timestamp = float(_STATUS_CACHE.get("timestamp") or 0.0)
            refreshing = bool(_STATUS_CACHE.get("refreshing"))
        if cached_payload is not None and (datetime.now().timestamp() - cached_timestamp) < STATUS_CACHE_TTL_SECONDS:
            return dict(cached_payload)
        if cached_payload is not None and refreshing:
            return dict(cached_payload)
        with _STATUS_CACHE_LOCK:
            _STATUS_CACHE["refreshing"] = True

    try:
        config = load_config()
        ensure_storage_dirs(config)
        repo = Repository(config)
        summary = repo.get_dashboard_summary()
        commands = merge_commands(build_default_commands(), parse_readme_commands(README_PATH))
        payload = {
            "message": message,
            "config_path": str(CONFIG_PATH),
            "config_json": json.dumps(config.data, ensure_ascii=False, indent=2),
            "commands": commands,
            "command_cards": build_command_cards(commands),
            "available_crawlers": [
                {
                    "name": crawler_name,
                    "label": humanize_crawler_name(crawler_name),
                    "enabled": bool(config.enabled_crawlers.get(crawler_name, False)),
                }
                for crawler_name in sorted(CRAWLER_MAP.keys())
            ],
            "summary": summary,
            "jobs": JOB_MANAGER.list_jobs(),
            "request_logs": tail_request_logs(config, scope="all", crawler_name="_all", limit=120),
            "quick_auth": {
                "auth_cookie": str(config.data.get("auth", {}).get("cookie", "") or ""),
                "replicate_cookie": str(config.data.get("replicate_auth", {}).get("cookie", "") or ""),
                "auth_sign": str(config.data.get("auth", {}).get("sign", "") or ""),
                "auth_x_ss_stub": str(config.data.get("auth", {}).get("x_ss_stub", "") or ""),
            },
            "generated_at": utc_now_text(),
        }
        if not message:
            with _STATUS_CACHE_LOCK:
                _STATUS_CACHE["timestamp"] = datetime.now().timestamp()
                _STATUS_CACHE["payload"] = payload
        return payload
    finally:
        if not message:
            with _STATUS_CACHE_LOCK:
                _STATUS_CACHE["refreshing"] = False


class SettingsHandler(BaseHTTPRequestHandler):
    server_version = "JianyingCrawlerWeb/1.0"

    def _send_html(self, message: str = "") -> None:
        html = read_template()
        payload_json = json.dumps(build_page_payload(message), ensure_ascii=False)
        html = html.replace("{{page_payload_json}}", payload_json)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _send_json(self, data: dict[str, object], status: int = HTTPStatus.OK) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_form(self) -> dict[str, str]:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        pairs = parse_qs(body, keep_blank_values=True)
        return {key: values[0] if values else "" for key, values in pairs.items()}

    def _read_json_body(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        if not raw.strip():
            return {}
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("JSON body 必须是对象。")
        return data

    def _save_full_config(self, config_json: str) -> dict[str, object]:
        parsed = json.loads(config_json)
        if not isinstance(parsed, dict):
            raise ValueError("配置 JSON 顶层必须是对象。")
        save_config(parsed)
        return build_page_payload("配置已保存。")

    def _save_quick_auth(self, form_data: dict[str, str]) -> dict[str, object]:
        config = load_config()
        auth = dict(config.data.get("auth", {}))
        replicate_auth = dict(config.data.get("replicate_auth", {}))
        auth["cookie"] = form_data.get("auth_cookie", "")
        auth["sign"] = form_data.get("auth_sign", "")
        auth["x_ss_stub"] = form_data.get("auth_x_ss_stub", "")
        replicate_auth["cookie"] = form_data.get("replicate_cookie", "")
        config.data["auth"] = auth
        config.data["replicate_auth"] = replicate_auth
        save_config(config.data)
        return build_page_payload("Cookie 和签名配置已保存。")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html()
            return
        if parsed.path == "/api/status":
            self._send_json(build_page_payload())
            return
        if parsed.path == "/api/request-logs":
            query = parse_qs(parsed.query or "", keep_blank_values=True)
            scope = str((query.get("scope") or ["all"])[0] or "all")
            crawler_name = str((query.get("crawler") or ["_all"])[0] or "_all")
            limit_value = str((query.get("limit") or ["200"])[0] or "200")
            try:
                limit = max(1, min(500, int(limit_value)))
            except ValueError:
                limit = 200
            config = load_config()
            ensure_storage_dirs(config)
            logs = tail_request_logs(config, scope=scope, crawler_name=crawler_name, limit=limit)
            self._send_json(
                {
                    "ok": True,
                    "scope": scope,
                    "crawler_name": crawler_name,
                    "limit": limit,
                    "logs": logs,
                    "generated_at": utc_now_text(),
                }
            )
            return
        if parsed.path.startswith("/api/jobs/") and not parsed.path.endswith("/stop"):
            parts = [part for part in parsed.path.split("/") if part]
            job_id = parts[2] if len(parts) >= 3 else ""
            job = JOB_MANAGER.get_job(job_id)
            if job is None:
                self._send_json({"ok": False, "error": "任务不存在。"}, status=HTTPStatus.NOT_FOUND)
                return
            self._send_json({"ok": True, "job": job})
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/save-config":
                form_data = self._read_form()
                payload = self._save_full_config(form_data.get("config_json", "{}"))
                html = read_template().replace("{{page_payload_json}}", json.dumps(payload, ensure_ascii=False))
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html.encode("utf-8"))
                return

            if parsed.path == "/save-quick-auth":
                form_data = self._read_form()
                payload = self._save_quick_auth(form_data)
                html = read_template().replace("{{page_payload_json}}", json.dumps(payload, ensure_ascii=False))
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html.encode("utf-8"))
                return

            if parsed.path == "/api/run-command":
                data = self._read_json_body()
                command = str(data.get("command") or "")
                job = JOB_MANAGER.create_job(command)
                self._send_json({"ok": True, "job": job.to_dict()})
                return

            if parsed.path == "/api/stop-all-jobs":
                result = JOB_MANAGER.stop_all_jobs()
                self._send_json({"ok": True, **result})
                return

            if parsed.path.startswith("/api/jobs/") and parsed.path.endswith("/stop"):
                parts = [part for part in parsed.path.split("/") if part]
                if len(parts) < 4:
                    raise ValueError("Missing job id.")
                job_id = parts[2]
                result = JOB_MANAGER.stop_job(job_id)
                self._send_json({"ok": True, **result})
                return
        except Exception as exc:
            if parsed.path.startswith("/api/"):
                self._send_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._send_html(f"操作失败：{exc}")
            return

        self.send_error(HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args) -> None:
        return


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8765), SettingsHandler)
    print(f"Config file: {CONFIG_PATH}")
    print("Open: http://127.0.0.1:8765")
    try:
        webbrowser.open("http://127.0.0.1:8765")
    except Exception:
        pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
