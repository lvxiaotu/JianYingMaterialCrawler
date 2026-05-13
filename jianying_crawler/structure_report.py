from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import AppConfig
from .db import connect
from .storage import write_json, write_text


BUCKETS_WITH_CRAWLERS = ("raw", "meta", "downloads")
ROOT_BUCKETS = ("raw", "meta", "downloads", "logs", "state")


def build_structure_report(config: AppConfig) -> Path:
    structure_dir = config.structure_dir
    by_crawler_dir = structure_dir / "by_crawler"
    by_crawler_dir.mkdir(parents=True, exist_ok=True)

    bucket_roots = {
        "raw": config.raw_dir,
        "meta": config.meta_dir,
        "downloads": config.downloads_dir,
        "logs": config.logs_dir,
        "state": config.state_dir,
    }

    bucket_reports: dict[str, dict[str, Any]] = {}
    crawler_file_indexes: dict[str, dict[str, list[str]]] = defaultdict(dict)
    crawler_reports: dict[str, dict[str, Any]] = {}

    for bucket_name, bucket_root in bucket_roots.items():
        if bucket_name in BUCKETS_WITH_CRAWLERS:
            report, file_indexes = scan_crawler_bucket(bucket_root)
            for crawler_name, file_list in file_indexes.items():
                crawler_file_indexes[crawler_name][bucket_name] = file_list
        else:
            report = scan_directory(bucket_root, sample_limit=20)
        bucket_reports[bucket_name] = report

    db_summary = collect_database_summary(config)
    crawler_names = sorted(
        set(crawler_file_indexes.keys())
        | set(bucket_reports["raw"].get("crawlers", {}).keys())
        | set(bucket_reports["meta"].get("crawlers", {}).keys())
        | set(bucket_reports["downloads"].get("crawlers", {}).keys())
        | set(db_summary.get("crawlers", {}).keys())
    )

    for crawler_name in crawler_names:
        crawler_report = build_crawler_report(
            config=config,
            crawler_name=crawler_name,
            bucket_reports=bucket_reports,
            crawler_file_indexes=crawler_file_indexes,
            db_summary=db_summary,
        )
        crawler_reports[crawler_name] = crawler_report
        crawler_dir = by_crawler_dir / crawler_name
        crawler_dir.mkdir(parents=True, exist_ok=True)
        write_json(crawler_dir / "overview.json", crawler_report)
        write_text(crawler_dir / "overview.md", render_crawler_markdown(crawler_report))
        for bucket_name in BUCKETS_WITH_CRAWLERS:
            lines = crawler_file_indexes.get(crawler_name, {}).get(bucket_name, [])
            if not lines:
                lines = ["# empty"]
            write_text(crawler_dir / f"{bucket_name}_files.txt", "\n".join(lines) + "\n")

    root_report = {
        "generated_at": now_iso(),
        "storage_root": str(config.storage_dir),
        "structure_root": str(structure_dir),
        "database_target": config.database_target,
        "canonical_layout": canonical_layout(config),
        "root_tree": build_ascii_tree(config.storage_dir, max_depth=2, max_entries_per_dir=30),
        "buckets": bucket_reports,
        "database": db_summary,
        "crawlers": crawler_reports,
    }
    write_json(structure_dir / "resource_structure.json", root_report)
    write_text(structure_dir / "resource_structure.md", render_root_markdown(root_report))
    write_json(by_crawler_dir / "index.json", {"crawlers": crawler_names})
    write_text(by_crawler_dir / "index.txt", "\n".join(crawler_names) + ("\n" if crawler_names else ""))
    return structure_dir


def build_crawler_report(
    config: AppConfig,
    crawler_name: str,
    bucket_reports: dict[str, dict[str, Any]],
    crawler_file_indexes: dict[str, dict[str, list[str]]],
    db_summary: dict[str, Any],
) -> dict[str, Any]:
    directories: dict[str, Any] = {}
    for bucket_name in BUCKETS_WITH_CRAWLERS:
        bucket_report = bucket_reports[bucket_name]
        crawler_bucket = bucket_report.get("crawlers", {}).get(crawler_name)
        if crawler_bucket is None:
            path = getattr(config, f"{bucket_name}_dir") / crawler_name
            crawler_bucket = {
                "path": str(path),
                "exists": path.exists(),
                "file_count": 0,
                "dir_count": 0,
                "total_size": 0,
                "sample_files": [],
                "extensions": {},
                "latest_modified": "",
                "immediate_dir_count": 0,
                "immediate_file_count": 0,
            }
        directories[bucket_name] = crawler_bucket

    db_crawler = db_summary.get("crawlers", {}).get(crawler_name, {})
    downloaded_files = directories["downloads"]["file_count"]
    return {
        "generated_at": now_iso(),
        "crawler_name": crawler_name,
        "paths": {
            "raw": str(config.raw_dir / crawler_name),
            "meta": str(config.meta_dir / crawler_name),
            "downloads": str(config.downloads_dir / crawler_name),
            "structure": str(config.structure_dir / "by_crawler" / crawler_name),
        },
        "directories": directories,
        "database": db_crawler,
        "indexes": {
            "raw_files": str(config.structure_dir / "by_crawler" / crawler_name / "raw_files.txt"),
            "meta_files": str(config.structure_dir / "by_crawler" / crawler_name / "meta_files.txt"),
            "downloads_files": str(config.structure_dir / "by_crawler" / crawler_name / "downloads_files.txt"),
        },
        "status_snapshot": {
            "has_raw": directories["raw"]["file_count"] > 0,
            "has_meta": directories["meta"]["file_count"] > 0,
            "has_downloads": downloaded_files > 0,
            "db_items": int(db_crawler.get("items", 0) or 0),
            "db_download_records": int(db_crawler.get("downloads_total", 0) or 0),
            "disk_downloaded_files": downloaded_files,
        },
        "samples": {
            "raw": directories["raw"]["sample_files"],
            "meta": directories["meta"]["sample_files"],
            "downloads": directories["downloads"]["sample_files"],
        },
        "file_index_sizes": {
            bucket_name: len(crawler_file_indexes.get(crawler_name, {}).get(bucket_name, []))
            for bucket_name in BUCKETS_WITH_CRAWLERS
        },
    }


def scan_crawler_bucket(bucket_root: Path) -> tuple[dict[str, Any], dict[str, list[str]]]:
    bucket_root.mkdir(parents=True, exist_ok=True)
    crawler_reports: dict[str, Any] = {}
    crawler_file_indexes: dict[str, list[str]] = {}

    total_files = 0
    total_dirs = 0
    total_size = 0
    latest_modified = ""

    direct_dirs = sorted([path for path in bucket_root.iterdir() if path.is_dir()], key=lambda path: path.name.lower())
    direct_files = sorted([path for path in bucket_root.iterdir() if path.is_file()], key=lambda path: path.name.lower())

    root_summary = {
        "path": str(bucket_root),
        "exists": bucket_root.exists(),
        "file_count": 0,
        "dir_count": len(direct_dirs),
        "total_size": 0,
        "sample_files": [],
        "extensions": {},
        "latest_modified": "",
        "immediate_dir_count": len(direct_dirs),
        "immediate_file_count": len(direct_files),
        "crawlers": crawler_reports,
        "root_files": [],
    }

    root_extension_counts: defaultdict[str, int] = defaultdict(int)
    for file_path in direct_files:
        stat = file_path.stat()
        relative = file_path.name
        root_summary["file_count"] += 1
        root_summary["total_size"] += stat.st_size
        root_summary["root_files"].append(relative)
        if len(root_summary["sample_files"]) < 20:
            root_summary["sample_files"].append(relative)
        root_extension_counts[file_path.suffix.lower() or "<no_ext>"] += 1
        latest_modified = max_timestamp(latest_modified, stat.st_mtime)

    for crawler_dir in direct_dirs:
        crawler_summary, file_index = scan_directory_with_index(crawler_dir, sample_limit=15)
        crawler_latest_mtime = crawler_summary.get("_latest_mtime", "")
        crawler_reports[crawler_dir.name] = cleanup_report(dict(crawler_summary))
        crawler_file_indexes[crawler_dir.name] = file_index
        total_files += crawler_summary["file_count"]
        total_dirs += crawler_summary["dir_count"]
        total_size += crawler_summary["total_size"]
        latest_modified = max_timestamp(latest_modified, crawler_latest_mtime)

    root_summary["file_count"] += total_files
    root_summary["dir_count"] += total_dirs
    root_summary["total_size"] += total_size
    root_summary["extensions"] = dict(sorted(root_extension_counts.items(), key=lambda item: (-item[1], item[0]))[:10])
    root_summary["latest_modified"] = latest_modified
    return cleanup_report(root_summary), crawler_file_indexes


def scan_directory(path: Path, sample_limit: int = 15) -> dict[str, Any]:
    summary, _ = scan_directory_with_index(path, sample_limit=sample_limit)
    return summary


def scan_directory_with_index(path: Path, sample_limit: int = 15) -> tuple[dict[str, Any], list[str]]:
    summary = {
        "path": str(path),
        "exists": path.exists(),
        "file_count": 0,
        "dir_count": 0,
        "total_size": 0,
        "sample_files": [],
        "extensions": {},
        "latest_modified": "",
        "immediate_dir_count": 0,
        "immediate_file_count": 0,
        "_latest_mtime": "",
    }
    if not path.exists():
        return summary, []

    file_index: list[str] = []
    extension_counts: defaultdict[str, int] = defaultdict(int)
    immediate_entries = list(path.iterdir())
    summary["immediate_dir_count"] = sum(1 for item in immediate_entries if item.is_dir())
    summary["immediate_file_count"] = sum(1 for item in immediate_entries if item.is_file())

    latest_mtime = ""
    for current_root, dir_names, file_names in os.walk(path):
        dir_names.sort()
        file_names.sort()
        summary["dir_count"] += len(dir_names)

        current_path = Path(current_root)
        for file_name in file_names:
            file_path = current_path / file_name
            relative = file_path.relative_to(path).as_posix()
            stat = file_path.stat()
            summary["file_count"] += 1
            summary["total_size"] += stat.st_size
            if len(summary["sample_files"]) < sample_limit:
                summary["sample_files"].append(relative)
            extension_counts[file_path.suffix.lower() or "<no_ext>"] += 1
            file_index.append(relative)
            latest_mtime = max_timestamp(latest_mtime, stat.st_mtime)

    summary["extensions"] = dict(sorted(extension_counts.items(), key=lambda item: (-item[1], item[0]))[:10])
    summary["latest_modified"] = latest_mtime
    summary["_latest_mtime"] = latest_mtime
    return summary, file_index


def collect_database_summary(config: AppConfig) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "available": True,
        "backend": "postgresql" if config.use_postgres else "sqlite",
        "target": config.database_target,
        "tables": {},
        "crawlers": {},
    }

    try:
        with connect(config) as conn:
            summary["tables"] = {
                "items": scalar_query(conn, "SELECT COUNT(*) FROM items"),
                "downloads": scalar_query(conn, "SELECT COUNT(*) FROM downloads"),
                "categories": scalar_query(conn, "SELECT COUNT(*) FROM categories"),
                "dependencies": scalar_query(conn, "SELECT COUNT(*) FROM dependencies"),
                "crawl_state": scalar_query(conn, "SELECT COUNT(*) FROM crawl_state"),
            }

            crawler_stats: dict[str, dict[str, Any]] = defaultdict(
                lambda: {
                    "items": 0,
                    "categories": 0,
                    "states": 0,
                    "downloads_total": 0,
                    "downloads_done": 0,
                    "downloads_pending": 0,
                    "downloads_failed": 0,
                }
            )

            for row in fetch_rows(conn, "SELECT crawler_name, COUNT(*) AS count FROM items GROUP BY crawler_name"):
                crawler_stats[str(row["crawler_name"])]["items"] = int(row["count"] or 0)

            for row in fetch_rows(conn, "SELECT crawler_name, COUNT(*) AS count FROM categories GROUP BY crawler_name"):
                crawler_stats[str(row["crawler_name"])]["categories"] = int(row["count"] or 0)

            for row in fetch_rows(conn, "SELECT crawler_name, COUNT(*) AS count FROM crawl_state GROUP BY crawler_name"):
                crawler_stats[str(row["crawler_name"])]["states"] = int(row["count"] or 0)

            download_sql = """
                SELECT
                    i.crawler_name AS crawler_name,
                    COUNT(DISTINCT d.id) AS downloads_total,
                    SUM(CASE WHEN d.status = 'done' THEN 1 ELSE 0 END) AS downloads_done,
                    SUM(CASE WHEN d.status = 'pending' THEN 1 ELSE 0 END) AS downloads_pending,
                    SUM(CASE WHEN d.status = 'failed' THEN 1 ELSE 0 END) AS downloads_failed
                FROM downloads d
                JOIN items i ON i.resource_id = d.resource_id
                GROUP BY i.crawler_name
            """
            for row in fetch_rows(conn, download_sql):
                bucket = crawler_stats[str(row["crawler_name"])]
                bucket["downloads_total"] = int(row["downloads_total"] or 0)
                bucket["downloads_done"] = int(row["downloads_done"] or 0)
                bucket["downloads_pending"] = int(row["downloads_pending"] or 0)
                bucket["downloads_failed"] = int(row["downloads_failed"] or 0)

            summary["crawlers"] = {name: dict(values) for name, values in sorted(crawler_stats.items())}
    except Exception as exc:
        summary["available"] = False
        summary["error"] = str(exc)

    return summary


def scalar_query(conn: Any, sql: str) -> int:
    row = conn.execute(sql).fetchone()
    if row is None:
        return 0
    if isinstance(row, dict):
        return int(next(iter(row.values())) or 0)
    try:
        return int(row[0] or 0)
    except (KeyError, TypeError):
        if hasattr(row, "keys"):
            return int(row[row.keys()[0]] or 0)
    return 0


def fetch_rows(conn: Any, sql: str) -> list[dict[str, Any]]:
    rows = conn.execute(sql).fetchall()
    return [row_to_dict(row) for row in rows]


def row_to_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    return dict(row)


def canonical_layout(config: AppConfig) -> dict[str, Any]:
    return {
        "raw": {
            "path_pattern": str(config.raw_dir / "<crawler_name>" / "<api-response>.json"),
            "description": "API 原始响应，便于回放和排错。",
        },
        "meta": {
            "path_pattern": str(config.meta_dir / "<crawler_name>" / "<normalized-record>.json"),
            "description": "清洗后的结构化元数据，适合后续分析和入库对照。",
        },
        "downloads": {
            "path_pattern": str(config.downloads_dir / "<crawler_name>" / "<resource_id>" / "<url_kind><ext>"),
            "description": "最终素材文件，扩展名按响应 Content-Type / 文件特征自动判定。",
        },
        "logs": {
            "path_pattern": str(config.logs_dir / "<runtime-log>.log"),
            "description": "运行日志输出目录。",
        },
        "state": {
            "path_pattern": str(config.state_dir / "<state-files>"),
            "description": "断点状态与本地 SQLite 数据库目录；若切到 PostgreSQL，这里仍可保留本地状态文件。",
        },
        "structure": {
            "path_pattern": str(config.structure_dir / "<report-files>"),
            "description": "自动生成的目录结构索引和链路级清单。",
        },
    }


def build_ascii_tree(root: Path, max_depth: int = 2, max_entries_per_dir: int = 25) -> list[str]:
    lines = [str(root)]

    def walk(path: Path, prefix: str, depth: int) -> None:
        if depth >= max_depth or not path.exists() or not path.is_dir():
            return

        entries = sorted(path.iterdir(), key=lambda item: (item.is_file(), item.name.lower()))
        if len(entries) > max_entries_per_dir:
            hidden_count = len(entries) - max_entries_per_dir
            entries = entries[:max_entries_per_dir]
        else:
            hidden_count = 0

        for index, entry in enumerate(entries):
            is_last = index == len(entries) - 1 and hidden_count == 0
            branch = "\\-- " if is_last else "+-- "
            name = entry.name + ("/" if entry.is_dir() else "")
            lines.append(prefix + branch + name)
            next_prefix = prefix + ("    " if is_last else "|   ")
            if entry.is_dir():
                walk(entry, next_prefix, depth + 1)

        if hidden_count:
            lines.append(prefix + "\\-- " + f"... ({hidden_count} more entries)")

    walk(root, "", 0)
    return lines


def render_root_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# JianYing Resource Structure",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Storage root: `{report['storage_root']}`",
        f"- Structure root: `{report['structure_root']}`",
        f"- Database target: `{report['database_target']}`",
        "",
        "## Canonical Layout",
    ]
    for name, bucket in report["canonical_layout"].items():
        lines.append(f"- `{name}`: `{bucket['path_pattern']}`")
        lines.append(f"  {bucket['description']}")

    lines.extend(
        [
            "",
            "## Current Root Tree",
            "```text",
            *report["root_tree"],
            "```",
            "",
            "## Bucket Summary",
            "| Bucket | Files | Dirs | Size | Latest Modified |",
            "| --- | ---: | ---: | ---: | --- |",
        ]
    )
    for bucket_name in ROOT_BUCKETS:
        bucket = report["buckets"][bucket_name]
        lines.append(
            f"| `{bucket_name}` | {bucket['file_count']} | {bucket['dir_count']} | {human_size(bucket['total_size'])} | {bucket['latest_modified'] or '-'} |"
        )

    lines.extend(
        [
            "",
            "## Database Summary",
        ]
    )
    database = report["database"]
    if database.get("available"):
        lines.extend(
            [
                f"- Backend: `{database['backend']}`",
                f"- Items: `{database['tables'].get('items', 0)}`",
                f"- Downloads: `{database['tables'].get('downloads', 0)}`",
                f"- Categories: `{database['tables'].get('categories', 0)}`",
                f"- Dependencies: `{database['tables'].get('dependencies', 0)}`",
                f"- Crawl State: `{database['tables'].get('crawl_state', 0)}`",
            ]
        )
    else:
        lines.append(f"- Database summary unavailable: `{database.get('error', 'unknown error')}`")

    lines.extend(
        [
            "",
            "## Crawler Summary",
            "| Crawler | Raw | Meta | Downloads(on disk) | Items(DB) | Categories | Download Records | Done/Pending/Failed | States |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: |",
        ]
    )
    for crawler_name, crawler_report in sorted(report["crawlers"].items()):
        db = crawler_report.get("database", {})
        lines.append(
            "| "
            + f"`{crawler_name}` | "
            + f"{crawler_report['directories']['raw']['file_count']} | "
            + f"{crawler_report['directories']['meta']['file_count']} | "
            + f"{crawler_report['directories']['downloads']['file_count']} | "
            + f"{int(db.get('items', 0) or 0)} | "
            + f"{int(db.get('categories', 0) or 0)} | "
            + f"{int(db.get('downloads_total', 0) or 0)} | "
            + f"{int(db.get('downloads_done', 0) or 0)}/{int(db.get('downloads_pending', 0) or 0)}/{int(db.get('downloads_failed', 0) or 0)} | "
            + f"{int(db.get('states', 0) or 0)} |"
        )

    lines.extend(
        [
            "",
            "## Generated Catalog",
            "- `resource_structure.json`: machine-readable overall summary",
            "- `by_crawler/<crawler_name>/overview.json`: per-chain summary",
            "- `by_crawler/<crawler_name>/raw_files.txt`: raw response file list",
            "- `by_crawler/<crawler_name>/meta_files.txt`: normalized metadata file list",
            "- `by_crawler/<crawler_name>/downloads_files.txt`: downloaded file list",
        ]
    )
    return "\n".join(lines) + "\n"


def render_crawler_markdown(report: dict[str, Any]) -> str:
    db = report.get("database", {})
    lines = [
        f"# {report['crawler_name']}",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Raw dir: `{report['paths']['raw']}`",
        f"- Meta dir: `{report['paths']['meta']}`",
        f"- Downloads dir: `{report['paths']['downloads']}`",
        "",
        "## Directory Summary",
        "| Bucket | Exists | Files | Dirs | Size | Latest Modified |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for bucket_name in BUCKETS_WITH_CRAWLERS:
        bucket = report["directories"][bucket_name]
        lines.append(
            f"| `{bucket_name}` | {str(bucket['exists']).lower()} | {bucket['file_count']} | {bucket['dir_count']} | {human_size(bucket['total_size'])} | {bucket['latest_modified'] or '-'} |"
        )

    lines.extend(
        [
            "",
            "## Database Summary",
            f"- Items: `{int(db.get('items', 0) or 0)}`",
            f"- Categories: `{int(db.get('categories', 0) or 0)}`",
            f"- States: `{int(db.get('states', 0) or 0)}`",
            f"- Download records: `{int(db.get('downloads_total', 0) or 0)}`",
            f"- Download done/pending/failed: `{int(db.get('downloads_done', 0) or 0)}/{int(db.get('downloads_pending', 0) or 0)}/{int(db.get('downloads_failed', 0) or 0)}`",
            "",
            "## Sample Files",
        ]
    )
    for bucket_name in BUCKETS_WITH_CRAWLERS:
        samples = report["samples"].get(bucket_name, [])
        lines.append(f"### {bucket_name}")
        if samples:
            lines.extend([f"- `{sample}`" for sample in samples])
        else:
            lines.append("- empty")

    lines.extend(
        [
            "",
            "## Index Files",
            f"- Raw list: `{report['indexes']['raw_files']}`",
            f"- Meta list: `{report['indexes']['meta_files']}`",
            f"- Downloads list: `{report['indexes']['downloads_files']}`",
        ]
    )
    return "\n".join(lines) + "\n"


def cleanup_report(report: dict[str, Any]) -> dict[str, Any]:
    report.pop("_latest_mtime", None)
    return report


def max_timestamp(current_value: str, mtime: Any) -> str:
    if not mtime:
        return current_value
    if isinstance(mtime, str):
        candidate = mtime
    else:
        candidate = datetime.fromtimestamp(float(mtime)).astimezone().isoformat(timespec="seconds")
    if not current_value or candidate > current_value:
        return candidate
    return current_value


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def human_size(size: int) -> str:
    value = float(size)
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{size} B"
